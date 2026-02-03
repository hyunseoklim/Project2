from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from datetime import date

from apps.transactions.models import Transaction


@login_required
def vat_preparation(request):
    """부가세 신고 준비 (분기별)"""
    year = int(request.GET.get('year', date.today().year))
    quarter = int(request.GET.get('quarter', (date.today().month - 1) // 3 + 1))

    # 분기 날짜 범위
    quarter_months = {
        1: (1, 3),
        2: (4, 6),
        3: (7, 9),
        4: (10, 12),
    }
    start_month, end_month = quarter_months[quarter]
    start_date = date(year, start_month, 1)
    if end_month == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, end_month + 1, 1).replace(day=1) - __import__('datetime').timedelta(days=1)

    base_qs = Transaction.active.filter(
        user=request.user,
        occurred_at__gte=start_date,
        occurred_at__lte=end_date,
        is_business=True,
    )

    # 매출세액 (수입 과세)
    sales_tax = base_qs.filter(tx_type='IN', tax_type='taxable').aggregate(
        total_amount=Sum('amount'),
        total_vat=Sum('vat_amount'),
    )

    # 매입세액 (지출 과세)
    purchase_tax = base_qs.filter(tx_type='OUT', tax_type='taxable').aggregate(
        total_amount=Sum('amount'),
        total_vat=Sum('vat_amount'),
    )

    # 면세 수입
    tax_free_sales = base_qs.filter(tx_type='IN', tax_type='tax_free').aggregate(
        total_amount=Sum('amount'),
    )

    # 영세율 수입
    zero_rated_sales = base_qs.filter(tx_type='IN', tax_type='zero_rated').aggregate(
        total_amount=Sum('amount'),
    )

    # 납부세액 계산
    sales_vat = sales_tax['total_vat'] or 0
    purchase_vat = purchase_tax['total_vat'] or 0
    tax_payable = sales_vat - purchase_vat

    context = {
        'year': year,
        'quarter': quarter,
        'start_date': start_date,
        'end_date': end_date,
        'sales_tax': sales_tax,
        'purchase_tax': purchase_tax,
        'tax_free_sales': tax_free_sales,
        'zero_rated_sales': zero_rated_sales,
        'sales_vat': sales_vat,
        'purchase_vat': purchase_vat,
        'tax_payable': tax_payable,
    }
    return render(request, 'tax/vat_preparation.html', context)


@login_required
def income_preparation(request):
    """종합소득세 준비 (연간)"""
    year = int(request.GET.get('year', date.today().year))

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    base_qs = Transaction.active.filter(
        user=request.user,
        occurred_at__gte=start_date,
        occurred_at__lte=end_date,
        is_business=True,
    )

    # 총 수입
    total_income = base_qs.filter(tx_type='IN').aggregate(
        total=Sum('amount'),
    )['total'] or 0

    # 총 지출 (필요경비)
    total_expense = base_qs.filter(tx_type='OUT').aggregate(
        total=Sum('amount'),
    )['total'] or 0

    # 카테고리별 지출
    category_expenses = base_qs.filter(tx_type='OUT').values(
        'category__name', 'category__expense_type'
    ).annotate(
        total=Sum('amount'),
    ).order_by('-total')

    net_income = total_income - total_expense

    context = {
        'year': year,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_income': net_income,
        'category_expenses': category_expenses,
    }
    return render(request, 'tax/income_preparation.html', context)