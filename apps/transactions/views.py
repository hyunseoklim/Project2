from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime

from .models import Transaction, Merchant, Category, Attachment
from apps.businesses.models import Business, Account


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
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        business_number = request.POST.get('business_number', '')
        contact = request.POST.get('contact', '')
        category_id = request.POST.get('category')
        memo = request.POST.get('memo', '')

        category = Category.objects.filter(pk=category_id).first() if category_id else None

        Merchant.objects.create(
            user=request.user,
            name=name,
            business_number=business_number,
            contact=contact,
            category=category,
            memo=memo,
        )
        messages.success(request, f"'{name}' 거래처가 생성되었습니다.")
        return redirect('transactions:merchant_list')

    return render(request, 'transactions/merchant_form.html', {'categories': categories})


@login_required
def merchant_detail(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)
    return render(request, 'transactions/merchant_detail.html', {'merchant': merchant})


@login_required
def merchant_update(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)
    categories = Category.objects.all()

    if request.method == 'POST':
        merchant.name = request.POST.get('name', merchant.name)
        merchant.business_number = request.POST.get('business_number', merchant.business_number)
        merchant.contact = request.POST.get('contact', merchant.contact)
        category_id = request.POST.get('category')
        merchant.category = Category.objects.filter(pk=category_id).first() if category_id else None
        merchant.memo = request.POST.get('memo', merchant.memo)
        merchant.save()
        messages.success(request, f"'{merchant.name}' 거래처가 수정되었습니다.")
        return redirect('transactions:merchant_detail', pk=merchant.pk)

    return render(request, 'transactions/merchant_form.html', {
        'merchant': merchant,
        'categories': categories,
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
    transactions = Transaction.active.filter(user=request.user).with_relations()

    # 필터
    tx_type = request.GET.get('tx_type')
    business_id = request.GET.get('business')
    category_id = request.GET.get('category')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if tx_type:
        transactions = transactions.filter(tx_type=tx_type)
    if business_id:
        transactions = transactions.filter(business_id=business_id)
    if category_id:
        transactions = transactions.filter(category_id=category_id)
    if start_date:
        transactions = transactions.filter(occurred_at__gte=start_date)
    if end_date:
        transactions = transactions.filter(occurred_at__lte=end_date + ' 23:59:59')

    businesses = Business.active.filter(user=request.user)
    categories = Category.objects.all()

    context = {
        'transactions': transactions,
        'businesses': businesses,
        'categories': categories,
        'selected_tx_type': tx_type,
        'selected_business': business_id,
        'selected_category': category_id,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
    }
    return render(request, 'transactions/transaction_list.html', context)


@login_required
def transaction_create(request):
    businesses = Business.active.filter(user=request.user)
    accounts = Account.active.filter(user=request.user)
    merchants = Merchant.active.filter(user=request.user)
    categories = Category.objects.all()

    if request.method == 'POST':
        try:
            tx_type = request.POST.get('tx_type')
            business_id = request.POST.get('business')
            account_id = request.POST.get('account')
            merchant_id = request.POST.get('merchant')
            merchant_name = request.POST.get('merchant_name', '')
            category_id = request.POST.get('category')
            tax_type = request.POST.get('tax_type', 'taxable')
            amount = request.POST.get('amount')
            occurred_at = request.POST.get('occurred_at')
            memo = request.POST.get('memo', '')

            transaction = Transaction(
                user=request.user,
                business_id=business_id if business_id else None,
                account_id=account_id,
                merchant_id=merchant_id if merchant_id else None,
                merchant_name=merchant_name,
                category_id=category_id,
                tx_type=tx_type,
                tax_type=tax_type,
                amount=amount,
                occurred_at=occurred_at,
                memo=memo,
            )
            transaction.save()
            messages.success(request, "거래가 등록되었습니다.")
            return redirect('transactions:transaction_list')

        except Exception as e:
            messages.error(request, f"오류 발생: {e}")

    context = {
        'businesses': businesses,
        'accounts': accounts,
        'merchants': merchants,
        'categories': categories,
    }
    return render(request, 'transactions/transaction_form.html', context)


@login_required
def transaction_detail(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)
    return render(request, 'transactions/transaction_detail.html', {'transaction': tx})


@login_required
def transaction_update(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)
    businesses = Business.active.filter(user=request.user)
    accounts = Account.active.filter(user=request.user)
    merchants = Merchant.active.filter(user=request.user)
    categories = Category.objects.all()

    if request.method == 'POST':
        try:
            tx.tx_type = request.POST.get('tx_type', tx.tx_type)
            tx.business_id = request.POST.get('business') or None
            tx.account_id = request.POST.get('account', tx.account_id)
            tx.merchant_id = request.POST.get('merchant') or None
            tx.merchant_name = request.POST.get('merchant_name', tx.merchant_name)
            tx.category_id = request.POST.get('category', tx.category_id)
            tx.tax_type = request.POST.get('tax_type', tx.tax_type)
            tx.amount = request.POST.get('amount', tx.amount)
            tx.occurred_at = request.POST.get('occurred_at', tx.occurred_at)
            tx.memo = request.POST.get('memo', tx.memo)
            tx.save()
            messages.success(request, "거래가 수정되었습니다.")
            return redirect('transactions:transaction_detail', pk=tx.pk)

        except Exception as e:
            messages.error(request, f"오류 발생: {e}")

    context = {
        'transaction': tx,
        'businesses': businesses,
        'accounts': accounts,
        'merchants': merchants,
        'categories': categories,
    }
    return render(request, 'transactions/transaction_form.html', context)


@login_required
def transaction_delete(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)

    if request.method == 'POST':
        tx.soft_delete()
        messages.success(request, "거래가 삭제되었습니다.")
        return redirect('transactions:transaction_list')

    return render(request, 'transactions/transaction_confirm_delete.html', {'transaction': tx})