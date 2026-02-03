from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # 기본 페이지 (접속 시 현재 날짜 기준 분기 데이터 노출)
    path('vat-report/', views.VATReportView.as_view(), name='vat_report_default'),
    path('search', views.transaction_list, name='transaction_list'),
]