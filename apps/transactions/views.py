from django.db.models import Sum
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from datetime import datetime, date
import calendar
from django.shortcuts import render
from .models import Transaction
from django.db.models.functions import ExtractMonth
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from .models import Merchant, Category
from .forms import TransactionForm, MerchantForm, CategoryForm, ExcelUploadForm
from apps.businesses.models import Account, Business

from django.http import HttpResponse
from .utils import generate_transaction_template, process_transaction_excel, export_transactions_to_excel
from django.views.decorators.http import require_POST

# ============================================================
# Category
# ============================================================

@login_required
def category_list(request):
    """카테고리 목록 (시스템 + 사용자)"""
    system_categories = Category.objects.filter(is_system=True)
    user_categories = Category.objects.filter(user=request.user)
    from itertools import chain
    all_categories = sorted(
        chain(system_categories, user_categories),
        key=lambda x: (x.type, x.name)
    )
    return render(request, 'transactions/category_list.html', {'categories': all_categories})

@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.is_system = False
            if Category.objects.filter(user=request.user, name=category.name).exists():
                messages.error(request, '이미 같은 이름의 카테고리가 있습니다.')
                return render(request, 'transactions/category_form.html', {'form': form})
            category.save()
            messages.success(request, f"'{category.name}' 카테고리가 생성되었습니다.")
            return redirect('transactions:category_list')
    else:
        form = CategoryForm()
    return render(request, 'transactions/category_form.html', {'form': form, 'title': '카테고리 추가'})

@login_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.is_system:
        messages.error(request, '기본 카테고리는 수정할 수 없습니다.')
        return redirect('transactions:category_list')
    if category.user != request.user:
        messages.error(request, '권한이 없습니다.')
        return redirect('transactions:category_list')
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{category.name}' 카테고리가 수정되었습니다.")
            return redirect('transactions:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'transactions/category_form.html', {'form': form, 'category': category, 'title': '카테고리 수정'})

@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.is_system:
        messages.error(request, '기본 카테고리는 삭제할 수 없습니다.')
        return redirect('transactions:category_list')
    if category.user != request.user:
        messages.error(request, '권한이 없습니다.')
        return redirect('transactions:category_list')
    transaction_count = category.transactions.filter(is_active=True).count()
    if transaction_count > 0:
        messages.error(request, f'사용 중인 카테고리는 삭제할 수 없습니다. (거래 {transaction_count}건)')
        return redirect('transactions:category_list')
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f"'{category_name}' 카테고리가 삭제되었습니다.")
        return redirect('transactions:category_list')
    return render(request, 'transactions/category_confirm_delete.html', {'category': category})

# ============================================================
# Merchant CRUD
# ============================================================

@login_required
def merchant_list(request):
    view_type = request.GET.get('view', 'all')
    base_qs = Merchant.active.filter(user=request.user).annotate(
        transaction_count=Count('transactions', filter=Q(transactions__is_active=True))
    )
    if view_type == 'frequent':
        merchants = base_qs.filter(transaction_count__gt=0).order_by('-transaction_count')[:10]
    else:
        merchants = base_qs.order_by('-created_at')
    return render(request, 'transactions/merchant_list.html', {'merchants': merchants, 'view_type': view_type})

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
    """상세 조회 (수정 폼 포함)"""
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)
    
    # 수정 요청이 올 경우 처리 (상세 페이지에서 수정까지 가능하게)
    if request.method == 'POST':
        form = MerchantForm(request.POST, instance=merchant, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{merchant.name}' 정보가 수정되었습니다.")
            return redirect('transactions:merchant_detail', pk=merchant.pk)
    else:
        form = MerchantForm(instance=merchant, user=request.user)

    recent_transactions = Transaction.active.filter(merchant=merchant, user=request.user).order_by('-occurred_at')[:20]
    stats = Transaction.active.filter(merchant=merchant, user=request.user).aggregate(
        total_count=Count('id'), total_amount=Sum('amount'), total_vat=Sum('vat_amount')
    )
    return render(request, 'transactions/merchant_detail.html', {
        'merchant': merchant, 'form': form, 'recent_transactions': recent_transactions, 'stats': stats,
    })

@login_required
def merchant_update(request, pk):
    """오류 방지를 위한 업데이트 뷰 유지 (detail로 리다이렉트)"""
    return redirect('transactions:merchant_detail', pk=pk)

@login_required
def merchant_delete(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)
    if request.method == 'POST':
        merchant.soft_delete()
        messages.success(request, f"'{merchant.name}' 거래처가 삭제되었습니다.")
        return redirect('transactions:merchant_list')
    return render(request, 'transactions/merchant_confirm_delete.html', {'merchant': merchant})

@login_required
def merchant_frequently_used(request):
    from django.db.models import Count
    merchants = Merchant.active.filter(user=request.user).annotate(
        transaction_count=Count('transactions', filter=Q(transactions__is_active=True))
    ).filter(transaction_count__gt=0).order_by('-transaction_count')[:10]
    return render(request, 'transactions/merchant_frequently_used.html', {'merchants': merchants})

# ============================================================
# Transaction CRUD
# ============================================================

@login_required
def transaction_list(request):
    transactions = Transaction.active.filter(user=request.user).with_relations()
    search = request.GET.get('search', '')
    if search:
        transactions = transactions.filter(Q(merchant__name__icontains=search) | Q(merchant_name__icontains=search) | Q(memo__icontains=search))
    tx_type = request.GET.get('tx_type', '')
    if tx_type: transactions = transactions.filter(tx_type=tx_type)
    business_id = request.GET.get('business', '')
    if business_id: transactions = transactions.filter(business_id=business_id)
    account_id = request.GET.get('account', '')
    if account_id: transactions = transactions.filter(account_id=account_id)
    category_id = request.GET.get('category', '')
    if category_id: transactions = transactions.filter(category_id=category_id)
    date_from, date_to = request.GET.get('date_from', ''), request.GET.get('date_to', '')
    if date_from: transactions = transactions.filter(occurred_at__gte=date_from)
    if date_to: transactions = transactions.filter(occurred_at__lte=date_to)
    stats = transactions.aggregate(total_income=Sum('amount', filter=Q(tx_type='IN')), total_expense=Sum('amount', filter=Q(tx_type='OUT')), total_vat=Sum('vat_amount'), count=Count('id'))
    paginator = Paginator(transactions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj, 'stats': stats, 
        'businesses': Business.objects.filter(user=request.user, is_active=True),
        'accounts': Account.objects.filter(user=request.user, is_active=True),
        'categories': Category.objects.all().order_by('type', 'order'),
    }
    return render(request, 'transactions/transaction_list.html', context)

@login_required
def transaction_create(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, '거래가 등록되었습니다.')
            return redirect('transactions:transaction_detail', pk=transaction.pk)
        else:
            messages.error(request, '입력 정보가 올바르지 않습니다.')
    else:
        form = TransactionForm(initial={'occurred_at': timezone.now(), 'tx_type': 'OUT', 'tax_type': 'taxable', 'is_business': True}, user=request.user)
    return render(request, 'transactions/transaction_form.html', {'form': form, 'title': '거래 등록'})

@login_required
def transaction_detail(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)
    return render(request, 'transactions/transaction_detail.html', {'transaction': transaction})

@login_required
def transaction_update(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '거래가 수정되었습니다.')
            return redirect('transactions:transaction_detail', pk=transaction.pk)
    else:
        form = TransactionForm(instance=transaction, user=request.user)
    return render(request, 'transactions/transaction_form.html', {'form': form, 'transaction': transaction, 'title': '거래 수정'})

@login_required
def transaction_delete(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user, is_active=True)
    if request.method == 'POST':
        transaction.soft_delete()
        messages.success(request, '거래가 삭제되었습니다.')
        return redirect('transactions:transaction_list')
    return render(request, 'transactions/transaction_confirm_delete.html', {'transaction': transaction})

class VATReportView(LoginRequiredMixin, TemplateView):
    template_name = 'transactions/vat_report.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        current_year, current_quarter = datetime.now().year, (datetime.now().month - 1) // 3 + 1
        year = int(self.request.GET.get('year', current_year))
        quarter = int(self.request.GET.get('quarter', current_quarter))
        month = self.request.GET.get('month', None)
        if month: month = int(month)
        start_month, end_month = (quarter - 1) * 3 + 1, quarter * 3 
        last_day = calendar.monthrange(year, end_month)[1]
        base_qs = Transaction.active.with_relations().filter(user=user, is_business=True, occurred_at__year=year, occurred_at__month__in=range(start_month, end_month + 1), tax_type='taxable')
        sales_summary = base_qs.income().aggregate(total_sales=Sum('amount'), total_sales_vat=Sum('vat_amount'))
        purchase_summary = base_qs.expense().aggregate(total_purchase=Sum('amount'), total_purchase_vat=Sum('vat_amount'))
        monthly_data = base_qs.annotate(m=ExtractMonth('occurred_at')).values('m', 'tx_type').annotate(vat_sum=Sum('vat_amount')).order_by('m')
        monthly_stats = []
        for m in range(start_month, end_month + 1):
            m_sales = next((item['vat_sum'] for item in monthly_data if item['m'] == m and item['tx_type'] == 'IN'), 0) or 0
            m_purchase = next((item['vat_sum'] for item in monthly_data if item['m'] == m and item['tx_type'] == 'OUT'), 0) or 0
            monthly_stats.append({'month': m, 'sales_vat': m_sales, 'purchase_vat': m_purchase, 'net_vat': m_sales - m_purchase})
        transaction_qs = base_qs.filter(occurred_at__month=month) if month else base_qs
        page_obj = Paginator(transaction_qs.order_by('-occurred_at'), 20).get_page(self.request.GET.get('page'))
        context.update({'year': year, 'quarter': quarter, 'month': month, 'sales': sales_summary, 'purchase': purchase_summary, 'estimated_tax': (sales_summary['total_sales_vat'] or 0) - (purchase_summary['total_purchase_vat'] or 0), 'monthly_stats': monthly_stats, 'page_obj': page_obj})
        return context

@login_required
def download_transactions(request):
    queryset = Transaction.active.filter(user=request.user).order_by('-occurred_at')
    excel_file = process_transaction_excel(queryset)
    response = HttpResponse(excel_file.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="transactions.xlsx"'
    return response

@login_required
def download_excel_template(request):
    excel_file = generate_transaction_template()
    response = HttpResponse(excel_file.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="transaction_template.xlsx"'
    return response

@login_required
def upload_transactions_excel(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                process_transaction_excel(request.FILES['excel_file'], request.user)
                return redirect('transactions:transaction_list')
            except Exception as e:
                messages.error(request, f"저장 실패: {e}")
    else: form = ExcelUploadForm()
    return render(request, 'transactions/excel_upload.html', {'form': form})

def transaction_export_view(request):
    queryset = Transaction.active.filter(user=request.user).select_related('business', 'account', 'category')
    excel_file = export_transactions_to_excel(queryset)
    response = HttpResponse(excel_file.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="transactions_{datetime.now().strftime("%Y%m%d")}.xlsx"'
    return response