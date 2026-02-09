"""
종합소득세 계산 뷰
"""
import logging
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Count
from django.shortcuts import render

from apps.transactions.models import Transaction
from .forms import IncomeTaxCalculationForm
from .utils import (
    calculate_tax,
    calculate_simple_expense_method,
    get_category_tax_impact,
    calculate_next_bracket_distance,
)

logger = logging.getLogger(__name__)


@login_required
def income_tax_report(request):
    """
    종합소득세 간단 리포트
    
    기능:
    - 실제 지출 방식 계산
    - 단순경비율 방식 비교
    - 카테고리별 절세 효과
    - 월별 누적 추이
    """
    user = request.user
    current_year = datetime.now().year
    
    # GET 파라미터 또는 기본값
    selected_year = int(request.GET.get('year', current_year - 1))
    business_type = request.GET.get('business_type', '')
    
    try:
        deduction_amount = Decimal(request.GET.get('deduction_amount', '1500000'))
    except:
        deduction_amount = Decimal('1500000')
    
    # 폼 생성
    form = IncomeTaxCalculationForm(
        initial={
            'year': selected_year,
            'business_type': business_type,
            'deduction_amount': deduction_amount
        }
    )
    
    # === 1. 거래 데이터 집계 ===
    transactions = Transaction.active.filter(
        user=user,
        occurred_at__year=selected_year,
        is_business=True
    )
    
    summary = transactions.aggregate(
        total_income=Sum('amount', filter=Q(tx_type='IN')),
        total_expense=Sum('amount', filter=Q(tx_type='OUT')),
        transaction_count=Count('id')
    )
    
    total_income = summary['total_income'] or Decimal('0')
    total_expense = summary['total_expense'] or Decimal('0')
    transaction_count = summary['transaction_count'] or 0
    
    # 거래가 없으면 안내
    if transaction_count == 0:
        messages.info(request, f'{selected_year}년 사업용 거래 내역이 없습니다.')
        context = {
            'form': form,
            'selected_year': selected_year,
            'has_data': False
        }
        return render(request, 'tax/income_tax_report.html', context)
    
    # === 2. 실제 지출 방식 계산 ===
    actual_income_amount = total_income - total_expense
    actual_taxable = max(actual_income_amount - deduction_amount, Decimal('0'))
    actual_result = calculate_tax(actual_taxable)
    
    # === 3. 단순경비율 방식 계산 ===
    simple_result = None
    simple_tax_result = None
    
    if business_type:
        simple_calc = calculate_simple_expense_method(total_income, business_type)
        
        if simple_calc and simple_calc.get('can_use'):
            simple_income_amount = simple_calc['income_amount']
            simple_taxable = max(simple_income_amount - deduction_amount, Decimal('0'))
            simple_tax_result = calculate_tax(simple_taxable)
            
            simple_result = {
                **simple_calc,
                'income_amount': simple_income_amount,
                'taxable': simple_taxable,
                'tax_result': simple_tax_result
            }
    
    # === 4. 추천 방법 결정 ===
    recommended = 'actual'
    savings = Decimal('0')
    
    if simple_result and simple_tax_result:
        if simple_tax_result['total'] < actual_result['total']:
            recommended = 'simple'
            savings = actual_result['total'] - simple_tax_result['total']
        else:
            savings = simple_tax_result['total'] - actual_result['total']
    
    # === 5. 카테고리별 절세 효과 ===
    categories = transactions.filter(tx_type='OUT').values(
        'category__name'
    ).annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    categories_dict = {
        cat['category__name']: cat['total']
        for cat in categories
    }
    
    # 실제 적용 세율 사용
    avg_tax_rate = actual_result['rate'] if actual_result['rate'] > 0 else Decimal('0.15')
    category_impact = get_category_tax_impact(categories_dict, avg_tax_rate)
    
    # === 6. 월별 누적 추이 ===
    monthly_data = []
    cumulative_income = Decimal('0')
    cumulative_expense = Decimal('0')
    
    for month in range(1, 13):
        month_txs = transactions.filter(occurred_at__month=month)
        
        if month_txs.exists():
            month_summary = month_txs.aggregate(
                income=Sum('amount', filter=Q(tx_type='IN')),
                expense=Sum('amount', filter=Q(tx_type='OUT'))
            )
            
            cumulative_income += month_summary['income'] or Decimal('0')
            cumulative_expense += month_summary['expense'] or Decimal('0')
            
            net_income = cumulative_income - cumulative_expense
            taxable = max(net_income - deduction_amount, Decimal('0'))
            tax_result = calculate_tax(taxable)
            
            monthly_data.append({
                'month': month,
                'income': net_income,
                'tax': tax_result['total']
            })
    
    # === 7. 다음 세율 구간까지 거리 ===
    bracket_info = calculate_next_bracket_distance(actual_taxable)

    
    # === Context 구성 ===
    context = {
        'form': form,
        'selected_year': selected_year,
        'has_data': True,
        
        # 기본 정보
        'total_income': total_income,
        'total_expense': total_expense,
        'transaction_count': transaction_count,
        'deduction_amount': deduction_amount,
        
        # 실제 지출 방식
        'actual_income_amount': actual_income_amount,
        'actual_taxable': actual_taxable,
        'actual_result': actual_result,
        
        # 단순경비율 방식
        'simple_result': simple_result,
        'business_type': business_type,
        
        # 비교 & 추천
        'recommended': recommended,
        'savings': savings,
        
        # 상세 분석
        'category_impact': category_impact[:10],  # 상위 10개
        'monthly_data': monthly_data,
        'bracket_info': bracket_info,
    }
    
    logger.info(
        f"종합소득세 계산: user={user.id}, year={selected_year}, "
        f"income={total_income}, tax={actual_result['total']}, "
        f"recommended={recommended}"
    )
    
    return render(request, 'tax/income_tax_report.html', context)

# from django.shortcuts import render
# from django.contrib.auth.decorators import login_required
# from django.db.models import Sum, Q
# from datetime import date

# from apps.transactions.models import Transaction


# @login_required
# def vat_preparation(request):
#     """부가세 신고 준비 (분기별)"""
#     year = int(request.GET.get('year', date.today().year))
#     quarter = int(request.GET.get('quarter', (date.today().month - 1) // 3 + 1))

#     # 분기 날짜 범위
#     quarter_months = {
#         1: (1, 3),
#         2: (4, 6),
#         3: (7, 9),
#         4: (10, 12),
#     }
#     start_month, end_month = quarter_months[quarter]
#     start_date = date(year, start_month, 1)
#     if end_month == 12:
#         end_date = date(year, 12, 31)
#     else:
#         end_date = date(year, end_month + 1, 1).replace(day=1) - __import__('datetime').timedelta(days=1)

#     base_qs = Transaction.active.filter(
#         user=request.user,
#         occurred_at__gte=start_date,
#         occurred_at__lte=end_date,
#         is_business=True,
#     )

#     # 매출세액 (수입 과세)
#     sales_tax = base_qs.filter(tx_type='IN', tax_type='taxable').aggregate(
#         total_amount=Sum('amount'),
#         total_vat=Sum('vat_amount'),
#     )

#     # 매입세액 (지출 과세)
#     purchase_tax = base_qs.filter(tx_type='OUT', tax_type='taxable').aggregate(
#         total_amount=Sum('amount'),
#         total_vat=Sum('vat_amount'),
#     )

#     # 면세 수입
#     tax_free_sales = base_qs.filter(tx_type='IN', tax_type='tax_free').aggregate(
#         total_amount=Sum('amount'),
#     )

#     # 영세율 수입
#     zero_rated_sales = base_qs.filter(tx_type='IN', tax_type='zero_rated').aggregate(
#         total_amount=Sum('amount'),
#     )

#     # 납부세액 계산
#     sales_vat = sales_tax['total_vat'] or 0
#     purchase_vat = purchase_tax['total_vat'] or 0
#     tax_payable = sales_vat - purchase_vat

#     context = {
#         'year': year,
#         'quarter': quarter,
#         'start_date': start_date,
#         'end_date': end_date,
#         'sales_tax': sales_tax,
#         'purchase_tax': purchase_tax,
#         'tax_free_sales': tax_free_sales,
#         'zero_rated_sales': zero_rated_sales,
#         'sales_vat': sales_vat,
#         'purchase_vat': purchase_vat,
#         'tax_payable': tax_payable,
#     }
#     return render(request, 'tax/vat_preparation.html', context)


# @login_required
# def income_preparation(request):
#     """종합소득세 준비 (연간)"""
#     year = int(request.GET.get('year', date.today().year))

#     start_date = date(year, 1, 1)
#     end_date = date(year, 12, 31)

#     base_qs = Transaction.active.filter(
#         user=request.user,
#         occurred_at__gte=start_date,
#         occurred_at__lte=end_date,
#         is_business=True,
#     )

#     # 총 수입
#     total_income = base_qs.filter(tx_type='IN').aggregate(
#         total=Sum('amount'),
#     )['total'] or 0

#     # 총 지출 (필요경비)
#     total_expense = base_qs.filter(tx_type='OUT').aggregate(
#         total=Sum('amount'),
#     )['total'] or 0

#     # 카테고리별 지출
#     category_expenses = base_qs.filter(tx_type='OUT').values(
#         'category__name', 'category__expense_type'
#     ).annotate(
#         total=Sum('amount'),
#     ).order_by('-total')

#     net_income = total_income - total_expense

#     context = {
#         'year': year,
#         'total_income': total_income,
#         'total_expense': total_expense,
#         'net_income': net_income,
#         'category_expenses': category_expenses,
#     }
#     return render(request, 'tax/income_preparation.html', context)