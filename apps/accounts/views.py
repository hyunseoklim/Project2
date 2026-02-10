# Django 기본
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import login as auth_login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.utils import timezone

# Django 인증 관련
from django.contrib.auth.views import (
    LoginView as DjangoLoginView,
    LogoutView as DjangoLogoutView,
    PasswordChangeView
)
from django.contrib.messages.views import SuccessMessageMixin

# 데이터베이스
from django.db import IntegrityError, transaction
from django.db.models import Sum, Count, Q, DecimalField, Value, F
from django.db.models.functions import Coalesce

# 기타
import logging
from datetime import timedelta

# 앱 내부
from .forms import ProfileForm, CustomUserCreationForm
from .models import Profile
from apps.transactions.models import Transaction
from apps.businesses.models import Business, Account
from django.db.models.functions import ExtractMonth
from datetime import timedelta

logger = logging.getLogger(__name__)

class UserLoginView(DjangoLoginView):
    """사용자 로그인"""
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("accounts:home")


class UserLogoutView(DjangoLogoutView):
    """사용자 로그아웃"""
    next_page = reverse_lazy("accounts:home")


def signup(request):
    """
    회원가입
    - 이메일 포함 커스텀 폼 사용
    - 가입 즉시 로그인 처리
    - Profile 자동 생성 (signals.py에서 처리)
    """
    
    if request.user.is_authenticated:
        return redirect('accounts:home')

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)  # 커스텀 폼으로 변경
        if form.is_valid():
            try:
                user = form.save()
                auth_login(request, user)
                logger.info(f"신규 회원가입: {user.username} (ID: {user.id}, Email: {user.email})")
                messages.success(request, f"{user.username}님, 환영합니다! 가입이 완료되었습니다.")
                return redirect("accounts:home")
            except IntegrityError as e:
                logger.error(f"회원가입 실패 (중복 데이터): {e}")
                messages.error(request, "이미 사용 중인 정보입니다.")
            except Exception as e:
                logger.error(f"회원가입 중 예상치 못한 오류: {e}", exc_info=True)
                messages.error(request, "회원가입 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        else:
            # 폼 검증 실패 시 구체적인 에러 메시지는 템플릿에서 표시
            messages.error(request, "입력 정보를 확인해주세요.")
    else:
        form = CustomUserCreationForm()  # 커스텀 폼으로 변경
    
    return render(request, "accounts/signup.html", {"form": form})


def home(request):
    """
    배포용 정식 홈: 전월 대비 지출 분석 및 성장형 대시보드 요약
    """
    if request.user.is_authenticated:
        # 1. 시간 설정 (이번 달 vs 저번 달)
        today = timezone.now()
        this_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # 다음 달 1일 00:00 (이번 달의 끝)
        next_month = (this_month_start + timedelta(days=32)).replace(day=1)

        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 2. 데이터 집계
        # 이번 달 지출
        monthly_expense = Transaction.active.filter(
            user=request.user,
            tx_type='OUT',
            occurred_at__gte=this_month_start,
            occurred_at__lt=next_month  # 다음 달 전까지!
        ).aggregate(total=Sum('amount'))['total'] or 0

        # 저번 달 지출
        last_month_expense = Transaction.active.filter(
            user=request.user,
            tx_type='OUT',
            occurred_at__gte=last_month_start,  # 수정
            occurred_at__lt=this_month_start    # 수정
        ).aggregate(total=Sum('amount'))['total'] or 0

        # 3. 데이터 가공 (증감액 및 그래프 퍼센트)
        expense_diff = monthly_expense - last_month_expense
        expense_diff_abs = abs(expense_diff)

        # 전월 대비 퍼센트 계산 (그래프용)
        if last_month_expense > 0:
            # 100%가 넘더라도 그래프가 깨지지 않게 계산하되, UI에서 100% 이상임을 표시
            expense_percent = int((monthly_expense / last_month_expense) * 100)
        else:
            # 저번 달 기록이 없으면 이번 달 지출이 있는 경우 100%, 없으면 0%
            expense_percent = 100 if monthly_expense > 0 else 0

        context = {
            'monthly_expense': monthly_expense,
            'last_month_expense': last_month_expense,
            'expense_diff': expense_diff,
            'expense_diff_abs': expense_diff_abs,
            'expense_percent': expense_percent,
            'business_count': Business.objects.filter(user=request.user, is_active=True).count(),
            'account_count': Account.objects.filter(business__user=request.user, is_active=True).count(),
        }
        return render(request, "accounts/home_loggedin.html", context)
    
    else:
        return render(request, "accounts/home.html")


@login_required
def dashboard(request):
    """대시보드 (통계 + 빠른 메뉴 + 사업장별 집계)"""
    profile = getattr(request.user, 'profile', None)

    # 1. 날짜 설정
    now = timezone.now()
    year = now.year
    month = now.month

    # 2. 이번 달 거래 필터링
    monthly_qs = Transaction.objects.filter(
        user=request.user,
        occurred_at__year=year,
        occurred_at__month=month,
        is_active=True
    )

    # 3. 합계 계산
    total_income = monthly_qs.filter(tx_type__iexact='IN').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = monthly_qs.filter(tx_type__iexact='OUT').aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = total_income - total_expense
    transaction_count = monthly_qs.count()

    # 4. 전월 데이터 (전월 대비 비교용)
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    
    prev_monthly_qs = Transaction.objects.filter(
        user=request.user,
        occurred_at__year=prev_year,
        occurred_at__month=prev_month,
        is_active=True
    )
    
    prev_income = prev_monthly_qs.filter(tx_type__iexact='IN').aggregate(Sum('amount'))['amount__sum'] or 0
    prev_expense = prev_monthly_qs.filter(tx_type__iexact='OUT').aggregate(Sum('amount'))['amount__sum'] or 0
    prev_profit = prev_income - prev_expense
    
    # 전월 대비 증감 계산
    profit_diff = net_profit - prev_profit
    profit_diff_percent = round((profit_diff / prev_profit * 100), 1) if prev_profit != 0 else 0

    # ========================================
    # 5. 카테고리별 지출 분석 (전월 대비 포함)
    # ========================================

    # 1. 이번 달 카테고리별 집계
    category_stats = monthly_qs.filter(tx_type='OUT').values('category__name').annotate(
        total=Sum('amount'),
        count=Count('id'),
    ).order_by('-total')

    # 2. 전월 카테고리별 집계 (비교용)
    prev_category_stats = prev_monthly_qs.filter(tx_type='OUT').values('category__name').annotate(
        total=Sum('amount')
    )

    # 3. 전월 데이터를 딕셔너리로 변환 (빠른 조회를 위해)
    #    예: {'식비': 500000, '교통비': 100000, ...}
    prev_category_dict = {item['category__name']: item['total'] for item in prev_category_stats}

    # 4. 이번 달 데이터에 분석 정보 추가
    for stat in category_stats:
        # 4-1. 전체 지출 대비 비율 계산
        #      예: 식비 50만원 ÷ 총 지출 200만원 = 25%
        if total_expense > 0:
            stat['percentage'] = round((stat['total'] / total_expense) * 100, 1)
        else:
            stat['percentage'] = 0
        
        # 4-2. 거래 건당 평균 금액
        #      예: 식비 총 50만원 ÷ 10건 = 건당 5만원
        stat['avg_per_transaction'] = stat['total'] / stat['count'] if stat['count'] > 0 else 0
        
        # 4-3. 전월 대비 증감 분석
        category_name = stat['category__name']
        prev_total = prev_category_dict.get(category_name, 0)  # 전월 금액 조회
        
        if prev_total > 0:
            # 전월 데이터가 있는 경우
            stat['prev_total'] = prev_total  # 전월 금액
            stat['diff'] = stat['total'] - prev_total  # 증감액 (이번달 - 전월)
            stat['diff_percent'] = round((stat['diff'] / prev_total * 100), 1)  # 증감률
            # 예: 이번달 60만원, 전월 50만원 → +10만원, +20%
        else:
            # 전월 데이터가 없는 경우 (새로운 카테고리)
            stat['prev_total'] = 0
            stat['diff'] = stat['total']  # 전액이 증가
            stat['diff_percent'] = 0  # 비교 불가

    # 7. 최근 거래 (상위 5개)
    recent_transactions = Transaction.objects.filter(
        user=request.user,
        occurred_at__lte=timezone.now(),
        is_active=True
    ).order_by('-occurred_at', '-id')[:5]

    # 7. 사업장별 집계
    businesses = Business.objects.filter(
        user=request.user,
        is_active=True
    ).annotate(
        revenue=Coalesce(
            Sum('transactions__amount', filter=Q(
                transactions__tx_type='IN',
                transactions__is_active=True
            )),
            Value(0),
            output_field=DecimalField()
        ),
        expense=Coalesce(
            Sum('transactions__amount', filter=Q(
                transactions__tx_type='OUT',
                transactions__is_active=True
            )),
            Value(0),
            output_field=DecimalField()
        ),
        profit=F('revenue') - F('expense')
    ).order_by('branch_type', 'name')

    # 8. Context
    context = {
        'user': request.user,
        'profile': profile,
        'masked_biz_num': profile.get_masked_business_number() if profile else "미등록",
        
        'year': year,
        'month': month,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'transaction_count': transaction_count,
        
        # 전월 대비
        'prev_year': prev_year,
        'prev_month': prev_month,
        'prev_income': prev_income,
        'prev_expense': prev_expense,
        'prev_profit': prev_profit,
        'profit_diff': profit_diff,
        'profit_diff_percent': profit_diff_percent,
        
        # 카테고리별
        'category_stats': category_stats,
        
        'recent_transactions': recent_transactions,
        'businesses': businesses,
    }
    return render(request, "accounts/home2.html", context)

class MyPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    """
    비밀번호 변경
    - 변경 후 세션 유지 (자동 로그아웃 방지)
    """
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:home')
    success_message = "비밀번호가 성공적으로 변경되었습니다."
    
    def form_valid(self, form):
        """비밀번호 변경 후 세션 유지"""
        response = super().form_valid(form)
        # 세션 해시 업데이트 (자동 로그아웃 방지)
        update_session_auth_hash(self.request, form.user)
        logger.info(f"비밀번호 변경: {self.request.user.username} (ID: {self.request.user.id})")
        return response


@login_required
def profile_edit(request):
    """
    프로필 수정
    - 트랜잭션 처리로 데이터 안정성 확보
    - 구체적인 예외 처리
    """
    # get_or_create로 프로필 없으면 생성
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if created:
        logger.info(f"프로필 자동 생성: user_id={request.user.id}")
    
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                logger.info(f"프로필 수정: user_id={request.user.id}")
                messages.success(request, "프로필이 저장되었습니다.")
                return redirect('accounts:home')
                
            except IntegrityError as e:
                logger.error(f"프로필 저장 실패 (무결성 제약): user_id={request.user.id}, error={e}")
                messages.error(request, "이미 등록된 정보입니다. 입력값을 확인해주세요.")
                
            except ValidationError as e:
                logger.warning(f"프로필 검증 실패: user_id={request.user.id}, error={e}")
                messages.error(request, "입력 형식이 올바르지 않습니다.")
                
            except Exception as e:
                logger.error(f"프로필 저장 중 예상치 못한 오류: user_id={request.user.id}, error={e}", exc_info=True)
                messages.error(request, "저장 중 오류가 발생했습니다. 관리자에게 문의해주세요.")
        else:
            messages.error(request, "입력 정보를 확인해주세요.")
    else:
        form = ProfileForm(instance=profile)
    
    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
def profile_detail(request):
    """
    프로필 상세 조회
    - 프로필 없으면 자동 생성
    """
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if created:
        logger.info(f"프로필 자동 생성: user_id={request.user.id}")
    
    return render(request, 'accounts/profile_detail.html', {'profile': profile})