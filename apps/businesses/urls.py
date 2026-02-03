from django.urls import path
from . import views

app_name = 'businesses'

urlpatterns = [
    # 계좌 목록 및 요약
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/deleted/', views.account_deleted_list, name='account_deleted_list'),# 삭제된 계좌 목록
    path('accounts/summary/', views.account_summary, name='account_summary'),   
    # 계좌 생성
    path('accounts/create/', views.account_create, name='account_create'),   
    # 계좌 상세/수정/삭제
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    path('accounts/<int:pk>/update/', views.account_update, name='account_update'),
    path('accounts/<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('accounts/<int:pk>/restore/', views.account_restore, name='account_restore'),

    ## 🎯 주요 URL 패턴

# | URL | 설명 | 메서드 |
# |-----|------|--------|
# | `/businesses/accounts/` | 계좌 목록 | GET |
# | `/businesses/accounts/summary/` | 대시보드 | GET |
# | `/businesses/accounts/create/` | 계좌 생성 | GET, POST |
# | `/businesses/accounts/<id>/` | 계좌 상세 | GET |
# | `/businesses/accounts/<id>/update/` | 계좌 수정 | GET, POST |
# | `/businesses/accounts/<id>/delete/` | 계좌 삭제 | GET, POST |
# | `/businesses/accounts/<id>/restore/` | 계좌 복구 | GET, POST |

    path('', views.business_list, name='business_list'),
    path('create/', views.business_create, name='business_create'),
    path('<int:pk>/', views.business_detail, name='business_detail'),
    path('<int:pk>/update/', views.business_update, name='business_update'),
    path('<int:pk>/delete/', views.business_delete, name='business_delete'),


]





