from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # 거래 목록
    path('', views.transaction_list, name='list'),
    
    # 거래 생성
    path('create/', views.transaction_create, name='create'),
    
    # 거래 상세
    path('<int:pk>/', views.transaction_detail, name='detail'),
    
    # 거래 수정
    path('<int:pk>/edit/', views.transaction_edit, name='edit'),
    
    # 거래 삭제
    path('<int:pk>/delete/', views.transaction_delete, name='delete'),
]
