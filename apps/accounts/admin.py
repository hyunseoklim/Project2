from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # 리스트에 보여줄 컬럼
    list_display = ['user', 'phone', 'business_type', 'created_at']
    
    # 클릭해서 수정할 수 있는 링크 걸 컬럼
    list_display_links = ['user']
    
    # 검색창 (유저 아이디, 이메일, 전화번호로 검색 가능)
    search_fields = ['user__username', 'user__email', 'phone']
    
    # 우측 필터 (사업자 유형별 보기)
    list_filter = ['business_type', 'created_at']