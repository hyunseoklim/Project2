from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.contrib import messages

def home_view(request):
    """
    프로젝트 루트(/) 접속 시 보여줄 화면
    """
    # 1. 템플릿에 전달할 데이터(Context) 준비
    context = {
        'project_name': '스마트 사업자 가계부',
        'status': '운영 중'
    }
    
    # 2. 로그인 여부에 따라 다른 템플릿 렌더링 가능
    if request.user.is_authenticated:
        # 로그인 사용자는 대시보드 느낌의 홈으로
        return render(request, 'base.html', context)
    else:
        # 비로그인 사용자는 서비스 소개나 로그인 유도 화면으로
        return render(request, 'base.html', context)

class LoginView(DjangoLoginView):
	template_name = "accounts/login.html"
	redirect_authenticated_user = True

	def get_success_url(self):
		return reverse_lazy("accounts:home")


class LogoutView(DjangoLogoutView):
	next_page = reverse_lazy("accounts:login")


@login_required
def home(request):
	return render(request, "accounts/home.html")


def signup(request):
	if request.method == "POST":
		form = UserCreationForm(request.POST)
		if form.is_valid():
			form.save()
			return redirect("accounts:login")
	else:
		form = UserCreationForm()

	return render(request, "accounts/signup.html", {"form": form})

class CustomPasswordChangeView(PasswordChangeView):
    """
    비밀번호 변경 뷰
    - 성공 시 세션을 업데이트하여 로그아웃되지 않도록 처리
    """
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')

    def form_valid(self, form):
        response = super().form_valid(form)
        # 비밀번호 변경 후 세션 정보가 바뀌어 자동 로그아웃되는 것을 방지
        update_session_auth_hash(self.request, self.request.user)
        messages.success(self.request, '비밀번호가 성공적으로 변경되었습니다.')
        return response

class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    """비밀번호 변경 완료 뷰"""
    template_name = 'accounts/password_change_done.html'