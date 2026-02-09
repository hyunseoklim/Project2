from django.urls import path
from . import views

app_name = 'businesses'

urlpatterns = [
    # 계좌 목록 및 요약
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/deleted/', views.account_deleted_list, name='account_deleted_list'),
    path('accounts/summary/', views.account_summary, name='account_summary'),   
    # 계좌 생성
    path('accounts/create/', views.account_create, name='account_create'),   
    # 계좌 상세/수정/삭제
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    path('accounts/<int:pk>/update/', views.account_update, name='account_update'),
    path('accounts/<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('accounts/<int:pk>/restore/', views.account_restore, name='account_restore'),
    path('account/<int:pk>/hard-delete/', views.account_hard_delete, name='account_hard_delete'),

# 1. 특수 목적의 주소 (글자로 된 것들)를 먼저 배치
    path('', views.business_list, name='business_list'),
    path('deleted/', views.business_deleted_list, name='business_deleted_list'),
    path('create/', views.business_create, name='business_create'),

    # 2. 통계 페이지 (통계도 ID가 필요하므로 상세 페이지 바로 근처에)
    path('<int:pk>/statistics/', views.business_statistics, name='business_statistics'),

    # 3. 변수(ID)가 들어가는 상세 페이지를 아래쪽에 배치
    path('<int:pk>/', views.business_detail, name='business_detail'),
    path('<int:pk>/update/', views.business_update, name='business_update'),
    path('<int:pk>/delete/', views.business_delete, name='business_delete'),
    path('<int:pk>/restore/', views.business_restore, name='business_restore'),
]


