from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "accounts"

urlpatterns = [
    # root(/) 혹은 accounts/home/ 경로를 views.home에 연결
    path("", views.home, name="home"), 
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),


    # 비밀번호 변경 페이지
    # 우리가 직접 만든 클래스 뷰를 연결
    path('password_change/', views.MyPasswordChangeView.as_view(), name='password_change'),
    
    # 완료 페이지는 간단하므로 장고 기본 뷰를 그대로 써도 무방합니다.
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='accounts/password_change_done.html'), name='password_change_done'),
]