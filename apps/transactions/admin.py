from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Transaction, Merchant, Category, Attachment

# 1. 공통 믹스인
class SoftDeleteAdminMixin:
    def get_queryset(self, request):
        return self.model.objects.all()

# 2. 인라인
class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ['original_name', 'get_size_display', 'uploaded_at']
    readonly_fields = ['original_name', 'get_size_display', 'uploaded_at']
    can_delete = True
    show_change_link = True

    @admin.display(description='파일 크기')
    def get_size_display(self, obj):
        # [수정] size가 None이거나 0인 경우 처리
        if obj.size is None:
            return "0 B"
            
        if obj.size < 1024:
            return f"{obj.size} B"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.1f} KB"
        else:
            return f"{obj.size / (1024 * 1024):.1f} MB"

@admin.register(Transaction)
class TransactionAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    """
    거래 내역 관리
    """
    list_display = [
        'occurred_at', 
        'get_tx_type_display_colored', 
        'get_amount_display', 
        'merchant', 
        'business', 
        'category', 
        'is_active'
    ]
    
    date_hierarchy = 'occurred_at'
    
    list_filter = [
        'is_active', 
        'tx_type', 
        'tax_type', 
        'is_business', 
        'business__name'
    ]
    
    search_fields = ['memo', 'merchant__name', 'business__name']
    
    inlines = [AttachmentInline]

    @admin.display(description='구분', ordering='tx_type')
    def get_tx_type_display_colored(self, obj):
        # format_html 인자 추가 수정 반영됨
        if obj.tx_type == 'IN':
            return format_html('<span style="color:blue; font-weight:bold;">{}</span>', '수입')
        return format_html('<span style="color:red; font-weight:bold;">{}</span>', '지출')

    @admin.display(description='금액', ordering='amount')
    def get_amount_display(self, obj):
        formatted = f"{int(obj.amount):,}원"
        if obj.tx_type == 'IN':
            return format_html('<span style="color:blue;">{}</span>', formatted)
        return format_html('<span style="color:red;">{}</span>', formatted)

@admin.register(Merchant)
class MerchantAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = [
        'name', 
        'business_number', 
        'category', 
        'get_transaction_count', 
        'is_active'
    ]
    
    search_fields = ['name', 'business_number']
    list_filter = ['is_active', 'category']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # [수정 완료] transaction -> transactions ('s' 붙임)
        # 에러 메시지 "Choices are: ... transactions ..." 참고함
        return qs.annotate(tx_count=Count('transactions'))

    @admin.display(description='거래 횟수', ordering='tx_count')
    def get_transaction_count(self, obj):
        return f"{obj.tx_count}건"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'user', 'order']
    list_filter = ['type']
    ordering = ['type', 'order']
    search_fields = ['name']

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_name', 'get_size_display', 'transaction', 'uploaded_at']
    list_filter = ['uploaded_at', 'content_type']
    search_fields = ['original_name', 'transaction__memo']

    @admin.display(description='크기', ordering='size')
    def get_size_display(self, obj):
        # [수정] 위와 동일하게 None 처리 추가
        if obj.size is None:
            return "0 B"
            
        if obj.size < 1024:
            return f"{obj.size} B"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.1f} KB"
        else:
            return f"{obj.size / (1024 * 1024):.1f} MB"