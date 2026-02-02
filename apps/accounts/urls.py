from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("1/", views.home_view, name="home_view"),
	path("signup/", views.signup, name="signup"),
	path("login/", views.LoginView.as_view(), name="login"),
	path("logout/", views.LogoutView.as_view(), name="logout"),
	path("home/", views.home, name="home"),
    
	# 비밀번호 변경 페이지
    path('password_change/', views.PasswordChangeView.as_view(
        template_name='accounts/password_change.html'
    ), name='password_change'),
    
    # 비밀번호 변경 완료 페이지
    path('password_change/done/', views.PasswordChangeDoneView.as_view(
        template_name='accounts/password_change_done.html'
    ), name='password_change_done'),
]
