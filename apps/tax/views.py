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
from django.db.models.functions import TruncMonth

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
    # 1. DB에서 월별로 그룹화하여 합계를 한 번에 가져오기
    monthly_stats = transactions.values(
        month_date=TruncMonth('occurred_at')
    ).annotate(
        income=Sum('amount', filter=Q(tx_type='IN')),
        expense=Sum('amount', filter=Q(tx_type='OUT'))
    ).order_by('month_date')

    # 2. 가져온 데이터를 바탕으로 파이썬 리스트 만들기
    monthly_data = []
    cumulative_income = Decimal('0')
    cumulative_expense = Decimal('0')

    for stat in monthly_stats:
        cumulative_income += stat['income'] or Decimal('0')
        cumulative_expense += stat['expense'] or Decimal('0')
        
        net_income = cumulative_income - cumulative_expense
        taxable = max(net_income - deduction_amount, Decimal('0'))
        tax_result = calculate_tax(taxable)
        
        monthly_data.append({
            'month': stat['month_date'].month,
            'income': net_income,
            'tax': tax_result['total']
        })

    # === 마지막 데이터 기준 예상 세금 추출 ===
    last_month_tax = Decimal('0')
    if monthly_data:
        # 리스트의 마지막 항목(-1)에서 tax 값을 가져옵니다.
        last_month_tax = monthly_data[-1]['tax']

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
        'last_month_tax': last_month_tax,
        'bracket_info': bracket_info,
    }
    
    logger.info(
        f"종합소득세 계산: user={user.id}, year={selected_year}, "
        f"income={total_income}, tax={actual_result['total']}, "
        f"recommended={recommended}"
    )
    
    return render(request, 'tax/income_tax_report.html', context)