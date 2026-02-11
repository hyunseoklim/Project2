from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_email', 'phone', 'business_type', 'get_main_business_number', 'created_at']  # 수정!
    list_filter = ['business_type', 'created_at']
    search_fields = ['user__username', 'user__email', 'full_name', 'phone']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = '이메일'
    
    def get_main_business_number(self, obj):
        """대표 사업장의 사업자번호"""
        from apps.businesses.models import Business  # import 추가!
        
        main_business = Business.objects.filter(
            user=obj.user,
            is_active=True,
            branch_type='main'
        ).first()
        
        if main_business and main_business.registration_number:
            return main_business.get_full_registration_number()
        return "-"
    get_main_business_number.short_description = '사업자번호'