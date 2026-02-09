from django.contrib import admin
from django.utils.html import format_html
from .models import Business, Account

# 1. 공통 믹스인: 삭제된 데이터(Soft Delete)도 관리자에서 볼 수 있게 함
class SoftDeleteAdminMixin:
    def get_queryset(self, request):
        # 기본 매니저 대신 objects(전체 매니저)를 사용하여 삭제된 것도 가져옴
        return self.model.objects.all()

# 2. 인라인 설정: 사업장 상세 페이지 하단에 '연결된 계좌 목록'을 바로 보여줌
class AccountInline(admin.TabularInline):
    model = Account
    extra = 0  # 빈 줄 추가 안 함
    fields = ['name', 'bank_name', 'account_number', 'balance', 'is_active']
    readonly_fields = ['balance'] # 잔액은 여기서 함부로 수정 못하게 막음
    can_delete = False # 여기서 바로 삭제하지 않도록 (안전장치)
    show_change_link = True # 클릭해서 상세 수정 페이지로 이동 가능

@admin.register(Business)
class BusinessAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    """
    사업장 관리 (Business)
    """
    # 리스트 컬럼
    list_display = [
        'name', 
        'user', 
        'registration_number', 
        'branch_type', 
        'get_account_count', # 연결된 계좌 수 (커스텀 메서드)
        'is_active', 
        'created_at'
    ]
    
    # 링크 연결
    list_display_links = ['name', 'registration_number']
    
    # 필터
    list_filter = ['is_active', 'branch_type', 'business_type']
    
    # 검색 (사업장명, 사업자번호, 소유자 아이디/이름)
    search_fields = ['name', 'registration_number', 'user__username', 'user__first_name']
    
    # 상세 페이지 구조
    fieldsets = [
        ('기본 정보', {
            'fields': ('user', 'name', 'is_active')
        }),
        ('사업자 상세', {
            'fields': ('registration_number', 'business_type', 'branch_type', 'location')
        }),
    ]
    
    # 계좌 인라인 추가
    inlines = [AccountInline]

    # --- 커스텀 메서드 ---
    @admin.display(description='연결 계좌 수')
    def get_account_count(self, obj):
        # 활성 계좌 수만 카운트
        count = obj.accounts.filter(is_active=True).count()
        return f"{count}개"

@admin.register(Account)
class AccountAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    """
    계좌 관리 (Account)
    """
    list_display = [
        'name', 
        'bank_name', 
        'account_number', 
        'business', 
        'get_balance_display', # 천 단위 콤마 적용된 잔액
        'is_active'
    ]
    
    list_filter = ['is_active', 'bank_name']
    
    # 검색 (계좌명, 계좌번호, 연결된 사업장 이름)
    search_fields = ['name', 'account_number', 'business__name']
    
    # 읽기 전용 필드 (잔액은 거래내역에 의해 변하므로 관리자가 임의 수정 주의)
    # readonly_fields = ['balance'] 

    # --- 커스텀 메서드 ---
    @admin.display(description='잔액', ordering='balance')
    def get_balance_display(self, obj):
        # 1000 -> 1,000원 형식으로 변환 & 금액에 따라 색상 표시
        formatted = f"{int(obj.balance):,}원"
        if obj.balance < 0:
            return format_html('<span style="color:red; font-weight:bold;">{}</span>', formatted)
        return formatted