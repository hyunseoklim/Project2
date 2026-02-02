from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import ProfileForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Profile

from django.contrib.auth.views import PasswordChangeView

class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("accounts:home")

class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy("accounts:login")

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accounts:login")
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})

# 이 함수를 추가합니다! (@login_required는 제거)
def home(request):
    """
    로그인 여부에 따라 다른 화면 렌더링
    """
    if request.user.is_authenticated:
        # 로그인 상태: 프로필 정보를 가져와서 home.html 렌더링
        profile = getattr(request.user, 'profile', None)
        context = {
            'user': request.user,
            'profile': profile,
            'masked_biz_num': profile.get_masked_business_number() if profile else "미등록"
        }
        return render(request, "accounts/home2.html", context)
    else:
        # 비로그인 상태: 서비스 소개 화면 home2.html 렌더링
        return render(request, "accounts/home.html")
    

class MyPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change.html'
    # 기존코드
    # success_url = reverse_lazy('password_change_done') # 변경 성공 시 이동할 URL 이름 
    success_url = reverse_lazy('accounts:password_change_done') # 변경 성공 시 이동할 URL 이름

    # 성공했을 때 사용자에게 알림(메시지)을 띄우고 싶다면 추가
    def form_valid(self, form):
        messages.success(self.request, "비밀번호가 성공적으로 변경되었습니다.")
        return super().form_valid(form)
    

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

