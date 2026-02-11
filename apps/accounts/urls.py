from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "accounts"

urlpatterns = [
    # root(/) 혹은 accounts/home/ 경로를 views.home에 연결
    path("", views.home, name="home"), 
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # 비밀번호 변경 페이지 
    path('password_change/', views.MyPasswordChangeView.as_view(), name='password_change'),

    # 비밀번호 변경 완료 페이지 
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='accounts/password_change_done.html'), name='password_change_done'),
    
    # 프로필 수정 및 확인 페이지
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/detail/', views.profile_detail, name='profile_detail'),
]