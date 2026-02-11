from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # business_registration_number -> get_masked_brn 교체
    list_display = [
        'user',              
        'get_email',         
        'phone',             
        'business_type',     
        'get_masked_brn', # 마스킹된 컬럼
        'created_at',        
    ]

    list_display_links = ['user', 'get_email']

    list_filter = [
        'business_type',     
        'created_at',        
    ]

    search_fields = [
        'user__username',    
        'user__email',       
        'user__first_name',  
        'phone',             
        'business_registration_number', 
    ]

    fieldsets = [
        ('기본 정보', {
            'fields': ('user', 'phone')
        }),
        ('사업자 정보', {
            'fields': ('business_type', 'business_registration_number'),
            'classes': ('wide',),  
        }),
        ('타임스탬프', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),  
        }),
    ]

    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    @admin.display(description='이메일')
    def get_email(self, obj):
        return obj.user.email

    @admin.display(description='사업자 번호')
    def get_masked_brn(self, obj):
        if not obj.business_registration_number:
            return "-"
        val = str(obj.business_registration_number)
        # 예: 123-45-67890 -> 123-45-*****
        if len(val) >= 10:
            return val[:-5] + "*****"
        return "*****"