from django.contrib import admin
from .models import Transaction, Merchant, Category, Attachment

@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'business_number', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'business_number')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'expense_type', 'user')
    list_filter = ('type',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # 관리자 목록 화면에서 보여줄 컬럼들
    list_display = ('occurred_at', 'user', 'tx_type', 'amount', 'vat_amount', 'tax_type', 'is_business')
    
    # 우측 필터 바 설정 (매우 유용합니다!)
    list_filter = ('tx_type', 'tax_type', 'is_business', 'occurred_at')
    
    # 검색 기능
    search_fields = ('merchant_name', 'memo')
    
    # 날짜 계층 구조 (상단에 연/월 선택 바 생성)
    date_hierarchy = 'occurred_at'

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'attachment_type', 'original_name', 'uploaded_at')