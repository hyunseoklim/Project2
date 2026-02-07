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

from django.http import FileResponse, Http404
from .models import Attachment
from .forms import AttachmentForm
import mimetypes


from django.http import HttpResponse
from .utils import generate_transaction_template, process_transaction_excel, export_transactions_to_excel
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Category
# ============================================================

# @login_required
# def category_list(request):
#     categories = Category.objects.all().order_by('type', 'order', 'name')
#     return render(request, 'transactions/category_list.html', {'categories': categories})

@login_required
def category_list(request):
    """카테고리 목록 (시스템 + 사용자)"""
    system_categories = Category.objects.filter(is_system=True)
    user_categories = Category.objects.filter(user=request.user)
    
    # 합치기
    from itertools import chain
    all_categories = sorted(
        chain(system_categories, user_categories),
        key=lambda x: (x.type, x.name)
    )
    
    return render(request, 'transactions/category_list.html', {
        'categories': all_categories
    })


@login_required
def category_create(request):
    """사용자 카테고리 생성"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.is_system = False
            
            # 같은 이름 체크
            if Category.objects.filter(user=request.user, name=category.name).exists():
                messages.error(request, '이미 같은 이름의 카테고리가 있습니다.')
                return render(request, 'transactions/category_form.html', {'form': form})
            
            category.save()
            messages.success(request, f"'{category.name}' 카테고리가 생성되었습니다.")
            return redirect('transactions:category_list')
    else:
        form = CategoryForm()
    
    return render(request, 'transactions/category_form.html', {
        'form': form,
        'title': '카테고리 추가',
    })


@login_required
def category_update(request, pk):
    """카테고리 수정"""
    category = get_object_or_404(Category, pk=pk)
    
    # 권한 체크
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
    
    return render(request, 'transactions/category_form.html', {
        'form': form,
        'category': category,
        'title': '카테고리 수정',
    })


@login_required
def category_delete(request, pk):
    """카테고리 삭제"""
    category = get_object_or_404(Category, pk=pk)
    
    # 권한 체크
    if category.is_system:
        messages.error(request, '기본 카테고리는 삭제할 수 없습니다.')
        return redirect('transactions:category_list')
    
    if category.user != request.user:
        messages.error(request, '권한이 없습니다.')
        return redirect('transactions:category_list')
    
    # 사용 중인지 체크
    transaction_count = category.transactions.filter(is_active=True).count()
    if transaction_count > 0:
        messages.error(request, f'사용 중인 카테고리는 삭제할 수 없습니다. (거래 {transaction_count}건)')
        return redirect('transactions:category_list')
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f"'{category_name}' 카테고리가 삭제되었습니다.")
        return redirect('transactions:category_list')
    
    return render(request, 'transactions/category_confirm_delete.html', {
        'category': category
    })


# ============================================================
# Merchant CRUD
# ============================================================

# @login_required
# def merchant_list(request):
#     merchants = Merchant.active.filter(user=request.user)
#     return render(request, 'transactions/merchant_list.html', {'merchants': merchants})

@login_required
def merchant_list(request):
    view_type = request.GET.get('view', 'all')  # all 또는 frequent
    
    base_qs = Merchant.active.filter(user=request.user).annotate(
        transaction_count=Count('transactions', filter=Q(transactions__is_active=True))
    )
    
    if view_type == 'frequent':
        merchants = base_qs.filter(transaction_count__gt=0).order_by('-transaction_count')[:10]
    else:
        merchants = base_qs.order_by('-created_at')
    
    return render(request, 'transactions/merchant_list.html', {
        'merchants': merchants,
        'view_type': view_type,
    })


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


# @login_required
# def merchant_detail(request, pk):
#     merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)
#     return render(request, 'transactions/merchant_detail.html', {'merchant': merchant})

@login_required
def merchant_detail(request, pk):
    merchant = get_object_or_404(Merchant, pk=pk, user=request.user, is_active=True)
    
    # 해당 거래처의 최근 거래 내역
    recent_transactions = Transaction.active.filter(
        merchant=merchant,
        user=request.user
    ).order_by('-occurred_at')[:20]
    
    # 통계
    from django.db.models import Sum, Count
    stats = Transaction.active.filter(merchant=merchant, user=request.user).aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        total_vat=Sum('vat_amount')
    )
    
    return render(request, 'transactions/merchant_detail.html', {
        'merchant': merchant,
        'recent_transactions': recent_transactions,
        'stats': stats,
    })


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

@login_required
def merchant_frequently_used(request):
    """자주 쓰는 거래처 (거래 횟수 기준)"""
    from django.db.models import Count
    
    merchants = Merchant.active.filter(user=request.user).annotate(
        transaction_count=Count('transactions', filter=Q(transactions__is_active=True))
    ).filter(
        transaction_count__gt=0
    ).order_by('-transaction_count')[:10]
    
    return render(request, 'transactions/merchant_frequently_used.html', {
        'merchants': merchants
    })


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
        base_qs = Transaction.active.with_relations().filter(
            user=user, 
            is_business=True,
            occurred_at__year=year,
            occurred_at__month__in=range(start_month, end_month + 1),
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
            # next()의 기본값인 0이 반환되더라도, item['vat_sum'] 자체가 None일 수 있으므로 마지막에 'or 0' 추가
            m_sales = next((item['vat_sum'] for item in monthly_data if item['m'] == m and item['tx_type'] == 'IN'), 0) or 0
            m_purchase = next((item['vat_sum'] for item in monthly_data if item['m'] == m and item['tx_type'] == 'OUT'), 0) or 0
            
            monthly_stats.append({
                'month': m,
                'sales_vat': m_sales,
                'purchase_vat': m_purchase,
                'net_vat': m_sales - m_purchase  # 이제 0 - 0 = 0 으로 정상 계산됩니다.
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
def download_transactions(request):
    # 다운로드할 데이터 필터링
    queryset = Transaction.active.filter(user=request.user).order_by('-occurred_at')
    
    # utils.py의 함수 호출
    excel_file = process_transaction_excel(queryset)
    
    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="transactions.xlsx"'
    return response

@login_required
def download_excel_template(request):
    """
    엑셀 업로드 양식을 다운로드하는 뷰
    """
    excel_file = generate_transaction_template()
    
    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # 파일명 설정
    response['Content-Disposition'] = 'attachment; filename="transaction_template.xlsx"'
    
    return response

@login_required
def upload_transactions_excel(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                count = process_transaction_excel(request.FILES['excel_file'], request.user)
                return redirect('transactions:transaction_list')
            except Exception as e:
                # 여기에 print를 넣으면 터미널 로그(ROLLBACK 근처)에 에러 내용이 찍힙니다.
                print("\n" + "!"*30)
                print(f"실제 에러 내용: {e}")
                print("!"*30 + "\n")
                messages.error(request, f"저장 실패: {e}")
        else:
            print(f"폼 에러: {form.errors}")
    else:
        form = ExcelUploadForm()
    
    return render(request, 'transactions/excel_upload.html', {'form': form})

@login_required
def transaction_export_view(request):
    # 현재 로그인한 사용자의 활성 거래 내역만 가져옴
    # (원한다면 여기서 날짜 필터링 등을 추가할 수 있습니다)
    queryset = Transaction.active.filter(user=request.user).select_related('business', 'account', 'category')
    
    # 엑셀 파일 생성
    excel_file = export_transactions_to_excel(queryset)
    now = timezone.localtime(timezone.now())
    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')    

    # HTTP 응답 설정
    filename = f"transaction_{request.user.username}_{timestamp}.xlsx"
    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@login_required
def attachment_upload(request, transaction_id):
    """영수증 첨부파일 업로드"""
    transaction_obj = get_object_or_404(Transaction, pk=transaction_id, user=request.user)
    
    # 이미 첨부파일이 있으면 수정
    try:
        attachment = transaction_obj.attachment
        is_update = True
    except Attachment.DoesNotExist:
        attachment = None
        is_update = False
    
    if request.method == 'POST':
        form = AttachmentForm(request.POST, request.FILES, instance=attachment)
        
        if form.is_valid():
            try:
                attachment = form.save(commit=False)
                attachment.user = request.user
                attachment.transaction = transaction_obj
                
                # 파일 정보 저장
                uploaded_file = request.FILES['file']
                attachment.original_name = uploaded_file.name
                attachment.size = uploaded_file.size
                attachment.content_type = uploaded_file.content_type
                
                attachment.save()
                
                messages.success(request, '영수증이 업로드되었습니다.')
                return redirect('transactions:transaction_detail', pk=transaction_id)
                
            except Exception as e:
                logger.error(f"파일 업로드 실패: {e}")
                messages.error(request, '파일 업로드 중 오류가 발생했습니다.')
        else:
            messages.error(request, '파일 업로드에 실패했습니다. 입력 내용을 확인해주세요.')
    else:
        form = AttachmentForm(instance=attachment)
    
    context = {
        'form': form,
        'transaction': transaction_obj,
        'is_update': is_update,
    }
    
    return render(request, 'transactions/attachment_form.html', context)


@login_required
def attachment_download(request, pk):
    """첨부파일 다운로드"""
    attachment = get_object_or_404(
        Attachment, 
        pk=pk, 
        user=request.user
    )
    
    try:
        # 파일 응답
        response = FileResponse(attachment.file.open('rb'))
        
        # Content-Type 설정
        content_type = attachment.content_type or mimetypes.guess_type(attachment.original_name)[0] or 'application/octet-stream'
        response['Content-Type'] = content_type
        
        # 파일명 설정 (한글 지원)
        from django.utils.encoding import escape_uri_path
        encoded_filename = escape_uri_path(attachment.original_name)
        response['Content-Disposition'] = f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        
        return response
        
    except Exception as e:
        logger.error(f"파일 다운로드 실패: {e}")
        raise Http404("파일을 찾을 수 없습니다.")


@login_required
def attachment_delete(request, pk):
    """첨부파일 삭제"""
    attachment = get_object_or_404(
        Attachment, 
        pk=pk, 
        user=request.user
    )
    
    transaction_id = attachment.transaction.pk
    
    if request.method == 'POST':
        attachment_name = attachment.original_name
        attachment.delete()  # Signal이 물리 파일도 자동 삭제
        
        logger.info(f"첨부파일 삭제: {attachment_name} (ID: {pk})")
        messages.success(request, f'첨부파일 "{attachment_name}"이 삭제되었습니다.')
        
        return redirect('transactions:transaction_detail', pk=transaction_id)
    
    context = {
        'attachment': attachment,
    }
    
    return render(request, 'transactions/attachment_confirm_delete.html', context)

# @login_required
# def transaction_list(request):
#     """거래 목록 (개선 버전)"""
#     user = request.user
    
#     # 1. 기본 쿼리셋 (사용자별, 활성화된 거래만)
#     transactions = Transaction.active.filter(user=user).with_relations()
    
#     # 2. 연도/월 필터 (예외처리 추가)
#     year = request.GET.get('year')
#     month = request.GET.get('month')
    
#     if year:
#         try:
#             year_int = int(year)
#             if 2000 <= year_int <= 2100:
#                 transactions = transactions.filter(occurred_at__year=year_int)
#                 year = year_int  # 정상적인 값으로 변환
#         except (ValueError, TypeError):
#             year = None
    
#     if month:
#         try:
#             month_int = int(month)
#             if 1 <= month_int <= 12:
#                 transactions = transactions.filter(occurred_at__month=month_int)
#                 month = month_int  # 정상적인 값으로 변환
#         except (ValueError, TypeError):
#             month = None
    
#     # 3. 정렬
#     transactions = transactions.order_by('-occurred_at')
    
#     # 4. 페이지네이션 (20개씩)
#     paginator = Paginator(transactions, 20)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
    
#     # 5. 연도 선택지 (DB에서 실제 존재하는 연도만)
#     year_list = Transaction.active.filter(user=user).dates('occurred_at', 'year', order='DESC')
#     year_list = [d.year for d in year_list]
    

#     # 6. 통계 (선택적)
#     from django.db.models import Sum, Count

#     stats = transactions.aggregate(
#     total_count=Count('id'),
#     total_income=Sum('amount', filter=Q(tx_type='IN')),
#     total_expense=Sum('amount', filter=Q(tx_type='OUT'))
# )

#     # None 값 처리 (데이터가 없을 경우 0으로 변환)
#     stats['total_income'] = stats['total_income'] or 0
#     stats['total_expense'] = stats['total_expense'] or 0
#     stats['net_profit'] = stats['total_income'] - stats['total_expense']
        
#     context = {
#         'page_obj': page_obj,
#         'year_list': year_list,
#         'selected_year': year,
#         'selected_month': month,
#         'stats': stats,
#     }
    
#     return render(request, 'transactions/list.html', context)