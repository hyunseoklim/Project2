from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
import logging
from .models import Account, Business
from .forms import AccountForm, AccountSearchForm, BusinessForm, BusinessSearchForm
from apps.transactions.models import Transaction

logger = logging.getLogger(__name__)


# =============================================================================
# Helper 함수
# =============================================================================

def _get_optimized_page(queryset, page_number, per_page=20):
    """
    최적화된 페이지네이션 헬퍼 함수
    
    Args:
        queryset: 페이지네이션할 QuerySet
        page_number: 페이지 번호
        per_page: 페이지당 항목 수 (기본 20)
    
    Returns:
        Page 객체
    """
    paginator = Paginator(queryset, per_page)
    
    # 페이지 번호 검증
    try:
        page_num = int(page_number) if page_number else 1
        if page_num < 1:
            page_num = 1
        elif page_num > paginator.num_pages and paginator.num_pages > 0:
            page_num = paginator.num_pages
    except (ValueError, TypeError):
        page_num = 1
    
    return paginator.get_page(page_num)


# =============================================================================
# Account 뷰
# =============================================================================

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
    
    # 페이지네이션 (헬퍼 함수 사용)
    page_obj = _get_optimized_page(accounts, request.GET.get('page'))
    


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
def account_deleted_list(request):
    """삭제된 계좌 목록"""
    user = request.user
    deleted_accounts = Account.objects.filter(
        user=user, 
        is_active=False
    ).select_related('business').order_by('-updated_at')
    
    # 페이지네이션 (헬퍼 함수 사용)
    page_obj = _get_optimized_page(deleted_accounts, request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'deleted_count': deleted_accounts.count(),
    }
    return render(request, 'businesses/account_deleted_list.html', context)


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

        # 통계 계산
    stats = account.transactions.filter(is_active=True).aggregate(
        total_count=Count('id'),
        income_count=Count('id', filter=Q(tx_type='IN')),
        expense_count=Count('id', filter=Q(tx_type='OUT')),
        total_income=Sum('amount', filter=Q(tx_type='IN')),
        total_expense=Sum('amount', filter=Q(tx_type='OUT'))
    )

    # None 값 처리
    stats['total_count'] = stats['total_count'] or 0
    stats['income_count'] = stats['income_count'] or 0
    stats['expense_count'] = stats['expense_count'] or 0
    stats['total_income'] = stats['total_income'] or 0
    stats['total_expense'] = stats['total_expense'] or 0
    stats['net_amount'] = stats['total_income'] - stats['total_expense']
    
    context = {
        'account': account,
        'recent_transactions': recent_transactions,
        'stats': stats,
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
            try:
                account = form.save(commit=False)
                account.user = request.user
                account.save()
                
                logger.info(
                    f"계좌 생성: {account.name} ({account.bank_name}) "
                    f"- 사용자: {request.user.username}"
                )
                
                messages.success(request, f'계좌 "{account.name}"가 생성되었습니다.')
                return redirect('businesses:account_detail', pk=account.pk)
                
            except IntegrityError as e:
                logger.error(f"계좌 생성 실패 (무결성 제약): user_id={request.user.id}, error={e}")
                messages.error(request, '이미 등록된 계좌입니다.')
                
            except ValidationError as e:
                logger.warning(f"계좌 검증 실패: user_id={request.user.id}, error={e}")
                messages.error(request, '입력 형식이 올바르지 않습니다.')
                
            except Exception as e:
                logger.error(f"계좌 생성 중 예상치 못한 오류: user_id={request.user.id}, error={e}", exc_info=True)
                messages.error(request, '계좌 생성 중 오류가 발생했습니다. 관리자에게 문의해주세요.')
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
            try:
                form.save()
                
                logger.info(f"계좌 수정: {account.name} (ID: {account.pk})")
                
                messages.success(request, f'계좌 "{account.name}"가 수정되었습니다.')
                return redirect('businesses:account_detail', pk=account.pk)
                
            except IntegrityError as e:
                logger.error(f"계좌 수정 실패 (무결성 제약): account_id={account.pk}, error={e}")
                messages.error(request, '이미 등록된 계좌입니다.')
                
            except ValidationError as e:
                logger.warning(f"계좌 검증 실패: account_id={account.pk}, error={e}")
                messages.error(request, '입력 형식이 올바르지 않습니다.')
                
            except Exception as e:
                logger.error(f"계좌 수정 중 예상치 못한 오류: account_id={account.pk}, error={e}", exc_info=True)
                messages.error(request, '계좌 수정 중 오류가 발생했습니다. 관리자에게 문의해주세요.')
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
def account_hard_delete(request, pk):
    # 계좌 영구삭제 모드
    # 소프트 삭제된 데이터도 가져오기 위해 .objects 사용
    account = get_object_or_404(Account.objects, pk=pk, user=request.user)
    
    if request.method == 'POST':
        account.hard_delete() # 모델의 메서드 호출
        messages.success(request, "계좌가 영구 삭제되었습니다.")
        return redirect('businesses:account_list')
    
    return render(request, 'businesses/account_confirm_hard_delete.html', {'account': account})


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


# =============================================================================
# Business 뷰
# =============================================================================

@login_required
def business_list(request):
    """
    사업장 목록 조회
    
    기능:
    - 본인 사업장만 조회
    - 구분(본점/지점), 업종, 검색어로 필터링
    - 페이지네이션 (페이지당 20개)
    """
    user = request.user
    
    # 기본 쿼리셋: 본인의 활성 사업장만
    businesses = Business.active.filter(user=user)
    
    # 검색 폼
    search_form = BusinessSearchForm(request.GET)
    
    if search_form.is_valid():
        # 구분 필터 (본점/지점)
        branch_type = search_form.cleaned_data.get('branch_type')
        if branch_type:
            businesses = businesses.filter(branch_type=branch_type)
        
        # 업종 필터
        business_type = search_form.cleaned_data.get('business_type')
        if business_type:
            businesses = businesses.filter(business_type__icontains=business_type)
        
        # 검색어 필터 (사업장명 또는 위치)
        search = search_form.cleaned_data.get('search')
        if search:
            businesses = businesses.filter(
                Q(name__icontains=search) | Q(location__icontains=search)
            )
    
    # 정렬: 이름순
    businesses = businesses.order_by('name')
    
    # 페이지네이션 (헬퍼 함수 사용)
    page_obj = _get_optimized_page(businesses, request.GET.get('page'))
    
    # 통계 계산 최적화 (1번 쿼리)
    stats = Business.active.filter(user=user).aggregate(
        total_count=Count('id'),
        main_count=Count('id', filter=Q(branch_type='main')),
        branch_count=Count('id', filter=Q(branch_type='branch'))
    )
    
    total_count = stats['total_count']
    main_count = stats['main_count']
    branch_count = stats['branch_count']
    
    context = {
        'businesses': businesses,
        'page_obj': page_obj,
        'businesses': businesses,
        'search_form': search_form,
        'total_count': total_count,
        'main_count': main_count,
        'branch_count': branch_count,
    }
    
    return render(request, 'businesses/business_list.html', context)


@login_required
def business_deleted_list(request):
    """삭제된 사업장 목록"""
    user = request.user
    deleted_businesses = Business.objects.filter(
        user=user,
        is_active=False
    ).order_by('-updated_at')
    
    # 페이지네이션 (헬퍼 함수 사용)
    page_obj = _get_optimized_page(deleted_businesses, request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'deleted_count': deleted_businesses.count(),
    }
    return render(request, 'businesses/business_deleted_list.html', context)


@login_required
def business_create(request):
    """
    사업장 생성
    
    - 폼 검증
    - 사용자 자동 설정
    - 성공 메시지 표시
    """
    if request.method == 'POST':
        form = BusinessForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                business = form.save(commit=False)
                business.user = request.user
                business.save()
                
                logger.info(
                    f"사업장 생성: {business.name} ({business.get_branch_type_display()}) "
                    f"- 사용자: {request.user.username}"
                )
                
                messages.success(request, f'사업장 "{business.name}"가 생성되었습니다.')
                return redirect('businesses:business_detail', pk=business.pk)
                
            except IntegrityError as e:
                logger.error(f"사업장 생성 실패 (무결성 제약): user_id={request.user.id}, error={e}")
                messages.error(request, '이미 등록된 사업장명입니다.')
                
            except ValidationError as e:
                logger.warning(f"사업장 검증 실패: user_id={request.user.id}, error={e}")
                messages.error(request, '입력 형식이 올바르지 않습니다.')
                
            except Exception as e:
                logger.error(f"사업장 생성 중 예상치 못한 오류: user_id={request.user.id}, error={e}", exc_info=True)
                messages.error(request, '사업장 생성 중 오류가 발생했습니다. 관리자에게 문의해주세요.')
        else:
            messages.error(request, '사업장 생성에 실패했습니다. 입력 내용을 확인해주세요.')
    else:
        form = BusinessForm(user=request.user)
    
    context = {
        'form': form,
        'title': '사업장 생성',
        'submit_text': '생성',
    }
    
    return render(request, 'businesses/business_form.html', context)


@login_required
def business_detail(request, pk):
    """
    사업장 상세 조회
    
    - 본인 사업장만 조회 가능
    - 연결된 계좌 목록
    - 기본 통계 표시
    """
    business = get_object_or_404(
        Business.active,
        pk=pk,
        user=request.user
    )
    
    # 연결된 계좌 목록 (select_related 최적화)
    accounts = business.accounts.filter(
        is_active=True
    ).select_related('business').order_by('-created_at')
    
    # 통계
    account_count = accounts.count()
    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    context = {
        'business': business,
        'accounts': accounts,
        'account_count': account_count,
        'total_balance': total_balance,
    }
    
    return render(request, 'businesses/business_detail.html', context)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from apps.businesses.models import Business
from apps.transactions.models import Transaction

@login_required
def business_statistics(request, pk):
    """
    사업장 통계 요약 조회 (유형/연도/월 필터링 포함)
    """
    business = get_object_or_404(Business, pk=pk, user=request.user, is_active=True)
    
    # 1. 파라미터 가져오기
    tx_type = request.GET.get('tx_type', 'OUT')
    year = request.GET.get('year', str(timezone.now().year))
    month = request.GET.get('month', 'all')
    period = request.GET.get('period', '')  # 'all_time' 체크용
    
    # 해당 사업장의 활성 거래 기본 쿼리셋
    transactions = Transaction.objects.filter(
        business=business,
        is_active=True
    )

    # 2. 필터 적용 로직
    period_label = "전체 기간"
    
    # 거래 유형 필터 (IN/OUT)
    if tx_type in ['IN', 'OUT']:
        transactions = transactions.filter(tx_type=tx_type)

    # 날짜 필터 (전체 기간 모드가 아닐 때만 적용)
    if period != 'all_time':
        if year != 'all' and year.isdigit():
            if month == 'all':
                transactions = transactions.filter(occurred_at__year=year)
                period_label = f"{year}년 전체"
            elif month.isdigit():
                transactions = transactions.filter(occurred_at__year=year, occurred_at__month=month)
                period_label = f"{year}년 {month}월"
    else:
        # 전체 기간일 때는 연도/월 선택값을 무시
        year = 'all'
        month = 'all'

    # 3. 데이터 집계 (카테고리별)
    stats = transactions.values('category__name').annotate(
        total_amount=Sum('amount'),
        count=Count('id')
    ).order_by('-total_amount')

    # 총액 계산
    total_sum = transactions.aggregate(Sum('amount'))['amount__sum'] or 0

    # 비중(%) 계산
    for s in stats:
        if total_sum > 0:
            s['percentage'] = round((s['total_amount'] / total_sum) * 100, 1)
        else:
            s['percentage'] = 0

    # 4. 연도 목록 (최근 5년)
    current_year = timezone.now().year
    available_years = [str(y) for y in range(current_year, current_year - 5, -1)]

    context = {
        'business': business,
        'stats': stats,
        'total_sum': total_sum,
        'category_count': stats.count(),
        'available_years': available_years,
        'selected_year': year,
        'selected_month': month,
        'selected_type': tx_type,
        'period_label': period_label,
        'is_all_time': period == 'all_time',
    }
    
    return render(request, 'businesses/business_statistics.html', context)

@login_required
def business_update(request, pk):
    """
    사업장 수정
    
    - 본인 사업장만 수정 가능
    - 폼 검증
    """
    business = get_object_or_404(Business.active, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = BusinessForm(request.POST, instance=business, user=request.user)
        
        if form.is_valid():
            try:
                form.save()
                
                logger.info(f"사업장 수정: {business.name} (ID: {business.pk})")
                
                messages.success(request, f'사업장 "{business.name}"가 수정되었습니다.')
                return redirect('businesses:business_detail', pk=business.pk)
                
            except IntegrityError as e:
                logger.error(f"사업장 수정 실패 (무결성 제약): business_id={business.pk}, error={e}")
                messages.error(request, '이미 등록된 사업장명입니다.')
                
            except ValidationError as e:
                logger.warning(f"사업장 검증 실패: business_id={business.pk}, error={e}")
                messages.error(request, '입력 형식이 올바르지 않습니다.')
                
            except Exception as e:
                logger.error(f"사업장 수정 중 예상치 못한 오류: business_id={business.pk}, error={e}", exc_info=True)
                messages.error(request, '사업장 수정 중 오류가 발생했습니다. 관리자에게 문의해주세요.')
        else:
            messages.error(request, '사업장 수정에 실패했습니다. 입력 내용을 확인해주세요.')
    else:
        form = BusinessForm(instance=business, user=request.user)
    
    context = {
        'form': form,
        'business': business,
        'title': '사업장 수정',
        'submit_text': '수정',
    }
    
    return render(request, 'businesses/business_form.html', context)


@login_required
def business_delete(request, pk):
    """
    사업장 삭제 (소프트 삭제)
    
    - 본인 사업장만 삭제 가능
    - 확인 페이지 표시
    """
    business = get_object_or_404(Business.active, pk=pk, user=request.user)
    
    if request.method == 'POST':
        business_name = business.name
        business.soft_delete()
        
        logger.info(f"사업장 삭제: {business_name} (ID: {pk})")
        
        messages.success(request, f'사업장 "{business_name}"가 삭제되었습니다.')
        return redirect('businesses:business_list')
    
    # 연결된 계좌 수 확인
    account_count = business.accounts.filter(is_active=True).count()
    
    context = {
        'business': business,
        'account_count': account_count,
    }
    
    return render(request, 'businesses/business_confirm_delete.html', context)


@login_required
def business_restore(request, pk):
    """
    삭제된 사업장 복구
    
    - 삭제된 사업장만 복구 가능
    - POST 요청만 허용
    """
    # 삭제된 사업장 조회 (objects 사용)
    business = get_object_or_404(Business.objects, pk=pk, user=request.user)
    
    if business.is_active:
        messages.warning(request, '이미 활성 상태인 사업장입니다.')
        return redirect('businesses:business_detail', pk=pk)
    
    if request.method == 'POST':
        business.restore()
        
        logger.info(f"사업장 복구: {business.name} (ID: {pk})")
        
        messages.success(request, f'사업장 "{business.name}"가 복구되었습니다.')
        return redirect('businesses:business_detail', pk=pk)
    
    # GET 요청 시 확인 페이지
    context = {
        'business': business,
    }
    
    return render(request, 'businesses/business_confirm_restore.html', context)