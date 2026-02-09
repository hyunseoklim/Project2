from django.contrib import admin
from django.utils.html import format_html
from .models import Business, Account

# 1. 공통 믹스인
class SoftDeleteAdminMixin:
    def get_queryset(self, request):
        return self.model.objects.all()

# 2. 계좌 인라인 (사업장 상세 페이지 하단)
class AccountInline(admin.TabularInline):
    model = Account
    extra = 0
    # account_number 대신 마스킹된 메서드 사용
    fields = ['name', 'bank_name', 'get_masked_account_number', 'balance', 'is_active']
    readonly_fields = ['get_masked_account_number', 'balance']
    can_delete = False
    show_change_link = True

    @admin.display(description='계좌번호')
    def get_masked_account_number(self, obj):
        if not obj.account_number:
            return "-"
        val = str(obj.account_number)
        # 6자리보다 짧으면 전체 마스킹, 길면 앞3/뒤3만 노출
        if len(val) > 6:
            return f"{val[:3]}****{val[-3:]}"
        return "****"

@admin.register(Business)
class BusinessAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    # registration_number -> get_masked_registration_number 교체
    list_display = [
        'name', 
        'user', 
        'get_masked_registration_number', 
        'branch_type', 
        'get_account_count', 
        'is_active', 
        'created_at'
    ]
    
    list_display_links = ['name'] # 링크는 이름에만 검
    list_filter = ['is_active', 'branch_type', 'business_type']
    
    # 검색은 실제 번호로도 가능해야 관리자가 편함 (보여주는 것만 마스킹)
    search_fields = ['name', 'registration_number', 'user__username', 'user__first_name']
    
    fieldsets = [
        ('기본 정보', {
            'fields': ('user', 'name', 'is_active')
        }),
        ('사업자 상세', {
            'fields': ('registration_number', 'business_type', 'branch_type', 'location')
        }),
    ]
    
    inlines = [AccountInline]

    @admin.display(description='사업자 번호')
    def get_masked_registration_number(self, obj):
        if not obj.registration_number:
            return "-"
        val = str(obj.registration_number)
        # 예: 123-45-67890 -> 123-45-*****
        if len(val) >= 10:
            return val[:-5] + "*****"
        return "*****"

    @admin.display(description='연결 계좌 수')
    def get_account_count(self, obj):
        count = obj.accounts.filter(is_active=True).count()
        return f"{count}개"

@admin.register(Account)
class AccountAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    # account_number -> get_masked_account_number 교체
    list_display = [
        'name', 
        'bank_name', 
        'get_masked_account_number', 
        'business', 
        'get_balance_display', 
        'is_active'
    ]
    
    list_filter = ['is_active', 'bank_name']
    search_fields = ['name', 'account_number', 'business__name']
    
    @admin.display(description='계좌번호')
    def get_masked_account_number(self, obj):
        if not obj.account_number:
            return "-"
        val = str(obj.account_number)
        if len(val) > 6:
            return f"{val[:3]}****{val[-3:]}"
        return "****"

    @admin.display(description='잔액', ordering='balance')
    def get_balance_display(self, obj):
        formatted = f"{int(obj.balance):,}원"
        if obj.balance < 0:
            return format_html('<span style="color:red; font-weight:bold;">{}</span>', formatted)
        return formatted