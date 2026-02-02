from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import ProfileForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .models import Profile

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
    else:
        context = {}
    
    # 하나의 템플릿으로 통일!
    return render(request, "accounts/home.html", context)
    

class MyPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:home')  # 홈으로 바로 이동
    success_message = "비밀번호가 성공적으로 변경되었습니다." # 👈 Mixin 덕분에 한 줄로 해결!
    

@login_required
def profile_edit(request):
    # 1. 안전하게 프로필을 가져옵니다. (없으면 여기서 생성됨)
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        # 2. instance=profile을 사용하여 데이터를 덮어씁니다.
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            # 3. 성공 메시지 추가
            messages.success(request, "프로필이 성공적으로 저장되었습니다.")
            return redirect('accounts:home')
    else:
        # 4. 기존 데이터를 폼에 채워서 보여주기
        form = ProfileForm(instance=profile)
        
    return render(request, "accounts/profile_edit.html", {"form": form})

def profile_detail(request):
    # 로그인한 사용자의 프로필 정보를 가져옵니다.
    profile = get_object_or_404(Profile, user=request.user)
    
    # 'profile'이라는 이름으로 HTML에 데이터를 보냅니다.
    return render(request, 'accounts/profile_detail.html', {'profile': profile})

