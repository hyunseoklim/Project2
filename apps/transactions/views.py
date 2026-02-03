from django.db.models import Sum
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from datetime import datetime, date
import calendar
from django.shortcuts import render
from .models import Transaction
from django.db.models.functions import ExtractYear, ExtractMonth
from django.contrib.auth.decorators import login_required
from django.db.models import Q


from .models import Transaction


class VATReportView(LoginRequiredMixin, TemplateView):
    template_name = 'transactions/vat_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 1. 연도/분기 설정 (예외처리 추가)
        current_year = datetime.now().year
        current_quarter = (datetime.now().month - 1) // 3 + 1
        
        # year 파라미터 파싱 및 검증
        try:
            year = int(self.request.GET.get('year', current_year))
            if year < 2000 or year > 2100:
                year = current_year
        except (ValueError, TypeError):
            year = current_year
        
        # quarter 파라미터 파싱 및 검증
        try:
            quarter = int(self.request.GET.get('quarter', current_quarter))
            if not 1 <= quarter <= 4:
                quarter = current_quarter
        except (ValueError, TypeError):
            quarter = current_quarter
        
        # month 파라미터 (특정 월 보기)
        try:
            month = self.request.GET.get('month', None)
            if month:
                month = int(month)
                if not 1 <= month <= 12:
                    month = None
        except (ValueError, TypeError):
            month = None

        # 2. 날짜 범위 계산
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        last_day = calendar.monthrange(year, end_month)[1]
        
        start_date = date(year, start_month, 1)
        end_date = date(year, end_month, last_day)

        # 3. 기초 쿼리셋
        base_qs = Transaction.active.filter(
            user=user, 
            is_business=True,
            occurred_at__date__range=[start_date, end_date],
            tax_type='taxable'
        )

        # 4. 전체 합계 계산
        sales_summary = base_qs.income().aggregate(
            total_sales=Sum('amount'),
            total_sales_vat=Sum('vat_amount')
        )
        purchase_summary = base_qs.expense().aggregate(
            total_purchase=Sum('amount'),
            total_purchase_vat=Sum('vat_amount')
        )

        # 5. 최종 세액 계산
        total_sales_vat = sales_summary['total_sales_vat'] or 0
        total_purchase_vat = purchase_summary['total_purchase_vat'] or 0
        estimated_tax = total_sales_vat - total_purchase_vat

        
        # 6. 월별 집계 로직 (최적화 버전)
        monthly_data = base_qs.annotate(
        m=ExtractMonth('occurred_at')
        ).values('m', 'tx_type').annotate(
            vat_sum=Sum('vat_amount')
        ).order_by('m')

        # 데이터를 템플릿에서 쓰기 좋게 가공
        monthly_stats = []
        for m in range(start_month, end_month + 1):
            m_sales = next((item['vat_sum'] for item in monthly_data if item['m'] == m and item['tx_type'] == 'IN'), 0)
            m_purchase = next((item['vat_sum'] for item in monthly_data if item['m'] == m and item['tx_type'] == 'OUT'), 0)
            
            monthly_stats.append({
                'month': m,
                'sales_vat': m_sales,
                'purchase_vat': m_purchase,
                'net_vat': m_sales - m_purchase
        })
            
        # 7. 거래 내역 필터링 (특정 월 선택 시)
        if month:
            transaction_qs = base_qs.filter(occurred_at__month=month)
        else:
            transaction_qs = base_qs
        
        # 8. 페이지네이션 (20개씩)
        paginator = Paginator(transaction_qs.order_by('-occurred_at'), 20)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # 9. 컨텍스트 데이터 전달
        context.update({
            'year': year,
            'quarter': quarter,
            'month': month,  # 선택된 월
            'start_date': start_date,
            'end_date': end_date,
            'sales': sales_summary,
            'purchase': purchase_summary,
            'estimated_tax': estimated_tax,
            'monthly_stats': monthly_stats,
            'page_obj': page_obj,  # 페이지네이션 객체
        })
        return context
    

@login_required
def transaction_list(request):
    """거래 목록 (개선 버전)"""
    user = request.user
    
    # 1. 기본 쿼리셋 (사용자별, 활성화된 거래만)
    transactions = Transaction.active.filter(user=user).with_relations()
    
    # 2. 연도/월 필터 (예외처리 추가)
    year = request.GET.get('year')
    month = request.GET.get('month')
    
    if year:
        try:
            year_int = int(year)
            if 2000 <= year_int <= 2100:
                transactions = transactions.filter(occurred_at__year=year_int)
                year = year_int  # 정상적인 값으로 변환
        except (ValueError, TypeError):
            year = None
    
    if month:
        try:
            month_int = int(month)
            if 1 <= month_int <= 12:
                transactions = transactions.filter(occurred_at__month=month_int)
                month = month_int  # 정상적인 값으로 변환
        except (ValueError, TypeError):
            month = None
    
    # 3. 정렬
    transactions = transactions.order_by('-occurred_at')
    
    # 4. 페이지네이션 (20개씩)
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 5. 연도 선택지 (DB에서 실제 존재하는 연도만)
    year_list = Transaction.active.filter(user=user).dates('occurred_at', 'year', order='DESC')
    year_list = [d.year for d in year_list]
    
    



    # 6. 통계 (선택적)
    from django.db.models import Sum, Count

    total_income = transactions.filter(tx_type='IN').aggregate(total=Sum('amount'))['total'] or 0
    total_expense = transactions.filter(tx_type='OUT').aggregate(total=Sum('amount'))['total'] or 0
    net_profit = total_income - total_expense  

    stats = {
        'total_count': transactions.count(),
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,  
    }
    
    context = {
        'page_obj': page_obj,
        'year_list': year_list,
        'selected_year': year,
        'selected_month': month,
        'stats': stats,
    }
    
    return render(request, 'transactions/list.html', context)
