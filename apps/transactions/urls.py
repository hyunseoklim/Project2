from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # 최재용 코드작업
    path('vat-report/', views.VATReportView.as_view(), name='vat_report_default'),
    # path('search', views.transaction_list, name='transaction_list'),
    # Category
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/update/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # 카테고리별 집계
    path('categories/statistics/', views.category_statistics, name='category_statistics'),

    # 월별 요약
    path('summary/monthly/', views.monthly_summary, name='monthly_summary'),

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

    # excel
    path('download-template/', views.download_excel_template, name='download_template'),
    path('upload-excel/', views.upload_transactions_excel, name='upload_excel'),
    path('export/', views.transaction_export_view, name='transaction_export'),

    # 첨부파일
    path('<int:transaction_id>/attachment/upload/', views.attachment_upload, name='attachment_upload'),
    path('attachment/<int:pk>/download/', views.attachment_download, name='attachment_download'),
    path('attachment/<int:pk>/delete/', views.attachment_delete, name='attachment_delete'),
    path('attachments/', views.attachment_list_view, name='attachment_list'),

]   