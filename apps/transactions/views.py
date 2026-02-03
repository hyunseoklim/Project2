from django.db.models import Sum
from django.views.generic import TemplateView
from datetime import datetime, date
import calendar

from .models import Transaction

class VATReportView(TemplateView):
    template_name = 'transactions/vat_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 1. 연도/분기 설정
        year = int(self.request.GET.get('year', datetime.now().year))
        quarter = int(self.request.GET.get('quarter', (datetime.now().month - 1) // 3 + 1))

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

        # 월별 집계 로직 추가 
        months_in_quarter = range(start_month, end_month + 1)
        monthly_stats = []

        for m in months_in_quarter:
            # 해당 월의 데이터만 필터링
            month_qs = base_qs.filter(
                occurred_at__year=year,  
                occurred_at__month=m
            )
            
            m_sales_vat = month_qs.income().aggregate(vat=Sum('vat_amount'))['vat'] or 0
            m_purchase_vat = month_qs.expense().aggregate(vat=Sum('vat_amount'))['vat'] or 0
            
            monthly_stats.append({
                'month': m,
                'sales_vat': m_sales_vat,
                'purchase_vat': m_purchase_vat,
                'net_vat': m_sales_vat - m_purchase_vat
            })

        # 6. 컨텍스트 데이터 전달
        context.update({
            'year': year,
            'quarter': quarter,
            'start_date': start_date,
            'end_date': end_date,
            'sales': sales_summary,
            'purchase': purchase_summary,
            'estimated_tax': estimated_tax,
            'monthly_stats': monthly_stats,  # 추가됨
            'transaction_list': base_qs.order_by('-occurred_at'),
        })
        return context