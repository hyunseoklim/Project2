from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import ProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .models import Profile
from django.db import IntegrityError,transaction

from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.views import PasswordChangeView

# 1. 클래스명을 조금 더 명확하게 변경
class UserLoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    # 메서드 대신 변수로 간단하게 지정 가능
    next_page = reverse_lazy("accounts:home") 

class UserLogoutView(DjangoLogoutView):
    # 템플릿 없이 처리하거나 POST 요청으로 로그아웃을 처리하는 것이 정석입니다.
    next_page = reverse_lazy("accounts:home")

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save() # 저장된 유저 객체를 변수에 담음
            auth_login(request, user) # 가입 즉시 로그인 처리
            messages.success(request, f"{user.username}님, 환영합니다! 가입이 완료되었습니다.")
            return redirect("accounts:home")
        else:
            # 유효성 검사 실패 시 에러 메시지 추가 (선택 사항)
            messages.error(request, "가입 정보를 확인해주세요.")
    else:
        form = UserCreationForm()
    
    return render(request, "accounts/signup.html", {"form": form})


def home(request):
     """로그인 여부에 따라 다른 화면 렌더링"""
     if request.user.is_authenticated:
         profile = getattr(request.user, 'profile', None)
         context = {
             'user': request.user,
             'profile': profile,
             'masked_biz_num': profile.get_masked_business_number() if profile else "미등록"
         }
         return render(request, "accounts/home2.html", context)
     else:
         context = {}
         return render(request, "accounts/home.html", context)
    

class MyPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:home')  # 홈으로 바로 이동
    success_message = "비밀번호가 성공적으로 변경되었습니다." # Mixin 사용으로 이득
    

@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        # 추후 프로필에 파일 업로드 예상.
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            try:
                # 데이터 저장 시 안전하게 트랜잭션 사용 가능
                with transaction.atomic():
                    form.save()
                messages.success(request, "프로필이 저장되었습니다.")
                return redirect('accounts:home')
            except IntegrityError:
                # DB 제약 조건 위반 (중복 데이터 등) 시 처리
                messages.error(request, "이미 등록된 정보이거나 데이터 충돌이 발생했습니다. 입력값을 다시 확인해주세요.")
            except Exception as e:
                # 예상치 못한 DB 에러 등 처리
                messages.error(request, f"저장 중 오류가 발생했습니다: {e}")
    else:
        form = ProfileForm(instance=profile)
        
    return render(request, "accounts/profile_edit.html", {"form": form})

@login_required  # 로그인을 안 한 사용자는 로그인 페이지로 보냅니다.
def profile_detail(request):
    # 없으면 빈 프로필이라도 가져옴
    # signals.py가 있지만, 만약을 대비한 안전장치입니다.
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    return render(request, 'accounts/profile_detail.html', {'profile': profile})
