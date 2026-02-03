from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from decimal import Decimal
import logging

from .models import Account, Business
from .forms import AccountForm, AccountSearchForm

logger = logging.getLogger(__name__)


@login_required
def account_list(request):
    """
    계좌 목록 조회
    
    기능:
    - 본인 계좌만 조회
    - 계좌 타입, 사업장, 검색어로 필터링
    - 페이지네이션 (페이지당 20개)
    """
    user = request.user
    
    # 기본 쿼리셋: 본인의 활성 계좌만
    accounts = Account.active.filter(user=user).select_related('business')
    
    # 검색 폼
    search_form = AccountSearchForm(request.GET, user=user)
    
    if search_form.is_valid():
        # 계좌 타입 필터
        account_type = search_form.cleaned_data.get('account_type')
        if account_type:
            accounts = accounts.filter(account_type=account_type)
        
        # 사업장 필터
        business = search_form.cleaned_data.get('business')
        if business:
            accounts = accounts.filter(business=business)
        
        # 검색어 필터 (계좌명 또는 은행명)
        search = search_form.cleaned_data.get('search')
        if search:
            accounts = accounts.filter(
                Q(name__icontains=search) | Q(bank_name__icontains=search)
            )
    
    # 정렬: 최신순
    accounts = accounts.order_by('-created_at')
    
    # 페이지네이션
    paginator = Paginator(accounts, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # 요약 정보
    total_count = Account.active.filter(user=user).count()
    business_count = Account.active.filter(user=user, account_type='business').count()
    personal_count = Account.active.filter(user=user, account_type='personal').count()
    total_balance = Account.active.filter(user=user).aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'total_count': total_count,
        'business_count': business_count,
        'personal_count': personal_count,
        'total_balance': total_balance,
    }
    
    return render(request, 'businesses/account_list.html', context)


@login_required
def account_detail(request, pk):
    """
    계좌 상세 조회
    
    - 본인 계좌만 조회 가능
    - 마스킹된 계좌번호 표시
    - 최근 거래 내역 5건
    """
    account = get_object_or_404(
        Account.active.select_related('business'),
        pk=pk,
        user=request.user
    )
    
    # 최근 거래 내역 5건
    recent_transactions = account.transactions.filter(
        is_active=True
    ).select_related('category', 'merchant').order_by('-occurred_at')[:5]
    
    context = {
        'account': account,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'businesses/account_detail.html', context)


@login_required
def account_create(request):
    """
    계좌 생성
    
    - 폼 검증
    - 사용자 자동 설정
    - 성공 메시지 표시
    """
    if request.method == 'POST':
        form = AccountForm(request.POST, user=request.user)
        
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            
            logger.info(
                f"계좌 생성: {account.name} ({account.bank_name}) "
                f"- 사용자: {request.user.username}"
            )
            
            messages.success(request, f'계좌 "{account.name}"가 생성되었습니다.')
            return redirect('businesses:account_detail', pk=account.pk)
        else:
            messages.error(request, '계좌 생성에 실패했습니다. 입력 내용을 확인해주세요.')
    else:
        form = AccountForm(user=request.user)
    
    context = {
        'form': form,
        'title': '계좌 생성',
        'submit_text': '생성',
    }
    
    return render(request, 'businesses/account_form.html', context)


@login_required
def account_update(request, pk):
    """
    계좌 수정
    
    - 본인 계좌만 수정 가능
    - 잔액은 수정 불가 (거래를 통해서만 변경)
    """
    account = get_object_or_404(Account.active, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account, user=request.user)
        
        if form.is_valid():
            form.save()
            
            logger.info(f"계좌 수정: {account.name} (ID: {account.pk})")
            
            messages.success(request, f'계좌 "{account.name}"가 수정되었습니다.')
            return redirect('businesses:account_detail', pk=account.pk)
        else:
            messages.error(request, '계좌 수정에 실패했습니다. 입력 내용을 확인해주세요.')
    else:
        form = AccountForm(instance=account, user=request.user)
    
    context = {
        'form': form,
        'account': account,
        'title': '계좌 수정',
        'submit_text': '수정',
    }
    
    return render(request, 'businesses/account_form.html', context)


@login_required
def account_delete(request, pk):
    """
    계좌 삭제 (소프트 삭제)
    
    - 본인 계좌만 삭제 가능
    - 확인 페이지 표시
    - 실제로는 is_active=False로 설정
    """
    account = get_object_or_404(Account.active, pk=pk, user=request.user)
    
    if request.method == 'POST':
        account_name = account.name
        account.soft_delete()
        
        logger.info(f"계좌 삭제: {account_name} (ID: {pk})")
        
        messages.success(request, f'계좌 "{account_name}"가 삭제되었습니다.')
        return redirect('businesses:account_list')
    
    # 연결된 거래 수 확인
    transaction_count = account.transactions.filter(is_active=True).count()
    
    context = {
        'account': account,
        'transaction_count': transaction_count,
    }
    
    return render(request, 'businesses/account_confirm_delete.html', context)


@login_required
def account_restore(request, pk):
    """
    삭제된 계좌 복구
    
    - 삭제된 계좌만 복구 가능
    - POST 요청만 허용
    """
    # 삭제된 계좌 조회 (objects 사용)
    account = get_object_or_404(Account.objects, pk=pk, user=request.user)
    
    if account.is_active:
        messages.warning(request, '이미 활성 상태인 계좌입니다.')
        return redirect('businesses:account_detail', pk=pk)
    
    if request.method == 'POST':
        account.restore()
        
        logger.info(f"계좌 복구: {account.name} (ID: {pk})")
        
        messages.success(request, f'계좌 "{account.name}"가 복구되었습니다.')
        return redirect('businesses:account_detail', pk=pk)
    
    # GET 요청 시 확인 페이지
    context = {
        'account': account,
    }
    
    return render(request, 'businesses/account_confirm_restore.html', context)


@login_required
def account_summary(request):
    """
    계좌 요약 대시보드
    
    표시 정보:
    - 총 계좌 수
    - 계좌 타입별 개수
    - 총 잔액
    - 사업장별 계좌 현황
    - 잔액 부족 계좌 (10만원 미만)
    """
    user = request.user
    
    # 기본 통계
    accounts = Account.active.filter(user=user)
    total_count = accounts.count()
    business_count = accounts.filter(account_type='business').count()
    personal_count = accounts.filter(account_type='personal').count()
    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    # 사업장별 계좌 현황
    business_accounts = accounts.filter(business__isnull=False).values(
        'business__id', 'business__name'
    ).annotate(
        count=Count('id'),
        total_balance=Sum('balance')
    ).order_by('-total_balance')
    
    # 잔액 부족 계좌 (10만원 미만)
    threshold = Decimal('100000')
    low_balance_accounts = accounts.filter(balance__lt=threshold).order_by('balance')[:5]
    
    # 은행별 계좌 현황
    bank_accounts = accounts.values('bank_name').annotate(
        count=Count('id'),
        total_balance=Sum('balance')
    ).order_by('-count')[:5]
    
    context = {
        'total_count': total_count,
        'business_count': business_count,
        'personal_count': personal_count,
        'total_balance': total_balance,
        'business_accounts': business_accounts,
        'low_balance_accounts': low_balance_accounts,
        'low_balance_threshold': threshold,
        'bank_accounts': bank_accounts,
    }
    
    return render(request, 'businesses/account_summary.html', context)