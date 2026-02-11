from django.urls import path
from . import views

app_name = 'tax'

urlpatterns = [
    # 종합소득세 계산
    path('income-tax/', views.income_tax_report, name='income_tax_report'),
]