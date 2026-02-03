from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone

from .models import Transaction, Merchant, Category
from .forms import TransactionForm, MerchantForm
from apps.businesses.models import Account, Business


# ============================================================
# Category
# ============================================================

@login_required
def category_list(request):
    categories = Category.objects.all().order_by('type', 'order', 'name')
    return render(request, 'transactions/category_list.html', {'categories': categories})


# ============================================================
# Merchant CRUD
# ============================================================

@login_required
def merchant_list(request):
    merchants = Merchant.active.filter(user=request.user)
    return render(request, 'transactions/merchant_list.html', {'merchants': merchants})


@login_required
def merchant_create(request):
    if request.method == 'POST':
        form = MerchantForm(request.POST, user=request.user)
        if form.is_valid():
            merchant = form.save(commit=False)
            merchant.user = request.user
            merchant.save()
            messages.success(request, f"'{merchant.name}' 거래처가 생성되었습니다.")
            return redirect('transactions:merchant_list')
    else:
        form = MerchantForm(user=request.user)

    return render(request, 'transactions/merchant_form.html', {'form': form})


@login_required
def merchant_detail(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)
    return render(request, 'transactions/merchant_detail.html', {'merchant': merchant})


@login_required
def merchant_update(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)

    if request.method == 'POST':
        form = MerchantForm(request.POST, instance=merchant, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{merchant.name}' 거래처가 수정되었습니다.")
            return redirect('transactions:merchant_detail', pk=merchant.pk)
    else:
        form = MerchantForm(instance=merchant, user=request.user)

    return render(request, 'transactions/merchant_form.html', {
        'form': form,
        'merchant': merchant,
    })


@login_required
def merchant_delete(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)

    if request.method == 'POST':
        merchant.soft_delete()
        messages.success(request, f"'{merchant.name}' 거래처가 삭제되었습니다.")
        return redirect('transactions:merchant_list')

    return render(request, 'transactions/merchant_confirm_delete.html', {'merchant': merchant})


# ============================================================
# Transaction CRUD
# ============================================================

@login_required
def transaction_list(request):
    """거래 목록"""
    transactions = Transaction.active.filter(user=request.user).with_relations()

    # 검색 필터
    search = request.GET.get('search', '')
    if search:
        transactions = transactions.filter(
            Q(merchant__name__icontains=search) |
            Q(merchant_name__icontains=search) |
            Q(memo__icontains=search)
        )

    # 거래 유형 필터
    tx_type = request.GET.get('tx_type', '')
    if tx_type:
        transactions = transactions.filter(tx_type=tx_type)

    # 사업장 필터
    business_id = request.GET.get('business', '')
    if business_id:
        transactions = transactions.filter(business_id=business_id)

    # 계좌 필터
    account_id = request.GET.get('account', '')
    if account_id:
        transactions = transactions.filter(account_id=account_id)

    # 카테고리 필터
    category_id = request.GET.get('category', '')
    if category_id:
        transactions = transactions.filter(category_id=category_id)

    # 날짜 범위 필터
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        transactions = transactions.filter(occurred_at__gte=date_from)
    if date_to:
        transactions = transactions.filter(occurred_at__lte=date_to)

    # 통계 계산
    stats = transactions.aggregate(
        total_income=Sum('amount', filter=Q(tx_type='IN')),
        total_expense=Sum('amount', filter=Q(tx_type='OUT')),
        total_vat=Sum('vat_amount'),
        count=Count('id')
    )

    # 페이지네이션
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'businesses': Business.objects.filter(user=request.user, is_active=True),
        'accounts': Account.objects.filter(user=request.user, is_active=True),
        'categories': Category.objects.all().order_by('type', 'order'),
    }
    return render(request, 'transactions/transaction_list.html', context)


@login_required
def transaction_create(request):
    """거래 생성"""
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, '거래가 등록되었습니다.')
            return redirect('transactions:transaction_detail', pk=transaction.pk)
    else:
        initial = {
            'occurred_at': timezone.now(),
            'tx_type': 'OUT',
            'tax_type': 'taxable',
            'is_business': True,
        }
        form = TransactionForm(initial=initial, user=request.user)

    context = {
        'form': form,
        'title': '거래 등록',
    }
    return render(request, 'transactions/transaction_form.html', context)


@login_required
def transaction_detail(request, pk):
    """거래 상세"""
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)
    return render(request, 'transactions/transaction_detail.html', {'transaction': transaction})


@login_required
def transaction_update(request, pk):
    """거래 수정"""
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)

    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '거래가 수정되었습니다.')
            return redirect('transactions:transaction_detail', pk=transaction.pk)
    else:
        form = TransactionForm(instance=transaction, user=request.user)

    context = {
        'form': form,
        'transaction': transaction,
        'title': '거래 수정',
    }
    return render(request, 'transactions/transaction_form.html', context)


@login_required
def transaction_delete(request, pk):
    """거래 삭제 (소프트 삭제)"""
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)

    if request.method == 'POST':
        transaction.soft_delete()
        messages.success(request, '거래가 삭제되었습니다.')
        return redirect('transactions:transaction_list')

    return render(request, 'transactions/transaction_confirm_delete.html', {'transaction': transaction})