from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, update_session_auth_hash
from django.db import IntegrityError, transaction
from django.db.models import Sum, Q, DecimalField, Value, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging
from .forms import ProfileForm, CustomUserCreationForm
from .models import Profile
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.views import PasswordChangeView
from apps.transactions.models import Transaction
from apps.businesses.models import Business

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
    홈 페이지
    - 로그인 상태에 따라 동적 렌더링
    - 단일 템플릿 사용 (home.html)
    """
    context = {}
    if request.user.is_authenticated:
        # 로그인 시 → 빠른 메뉴만 있는 홈
        uncategorized_count = Transaction.active.filter(
            user=request.user,
            category__isnull=True
        ).count()
        
        context = {
            'uncategorized_count': uncategorized_count,
        }
        return render(request, "accounts/home_loggedin.html", context)
    else:
        # 로그아웃 시 → 랜딩 페이지
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
        occurred_at__month=month
    )

    # 3. 합계 계산 (대소문자 이슈 방지를 위해 __iexact 사용)
    # DB의 tx_type이 'income', 'INCOME' 무엇이든 상관없이 가져옵니다.
    total_income = monthly_qs.filter(tx_type__iexact='IN').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = monthly_qs.filter(tx_type__iexact='OUT').aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = total_income - total_expense

    # 4. 최근 거래 (상위 5개)
    # 수정, timezone.now를 통해 미래내용 없앰.
    recent_transactions = Transaction.objects.filter(
        user=request.user,
        occurred_at__lte=timezone.now() # 현재 시간보다 작거나 같은(과거~현재) 거래만
    ).order_by('-occurred_at', '-id')[:5]
    # 5. 사업장별 집계
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

    # 6. Context 한 번만!
    context = {
        'user': request.user,
        'profile': profile,
        'masked_biz_num': profile.get_masked_business_number() if profile else "미등록",
        
        'year': year,
        'month': month,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
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