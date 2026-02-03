from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # 기본 페이지 (접속 시 현재 날짜 기준 분기 데이터 노출)
    path('vat-report/', views.VATReportView.as_view(), name='vat_report_default'),

    path('', views.transaction_list, name='transaction_list'),
    
#     # 특정 연도/분기 지정 페이지 (예: /vat-report/2024/1/)
#     path('vat-report/<int:year>/<int:quarter>/', views.VATReportView.as_view(), name='vat_report_detail'),
    
#     # 세금계산서 목록만 따로 보기 (부가 기능)
#     path('vat-report/tax-invoices/', views.TaxInvoiceListView.as_view(), name='tax_invoice_list'),
]