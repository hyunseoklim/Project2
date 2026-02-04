from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # 최재용 코드작업
    path('vat-report/', views.VATReportView.as_view(), name='vat_report_default'),
    path('search', views.transaction_list, name='transaction_list'),
    # Category
    path('categories/', views.category_list, name='category_list'),

    # Merchant
    path('merchants/', views.merchant_list, name='merchant_list'),
    path('merchants/create/', views.merchant_create, name='merchant_create'),
    path('merchants/<int:pk>/', views.merchant_detail, name='merchant_detail'),
    path('merchants/<int:pk>/update/', views.merchant_update, name='merchant_update'),
    path('merchants/<int:pk>/delete/', views.merchant_delete, name='merchant_delete'),

    # Transaction
    path('', views.transaction_list, name='transaction_list'),
    path('create/', views.transaction_create, name='transaction_create'),
    path('<int:pk>/', views.transaction_detail, name='transaction_detail'),
    path('<int:pk>/update/', views.transaction_update, name='transaction_update'),
    path('<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),
]