"""
Accounts Admin & Models 커버리지 완성 테스트 (Pytest)

3순위: admin.py 누락 라인 커버 (8줄)
- get_masked_brn() 마스킹 엣지 케이스 (50, 54-60 라인)

4순위: models.py 누락 라인 커버 (1줄)
- get_masked_business_number() 비정상 길이 (56 라인)
"""
import pytest
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite

from apps.accounts.models import Profile
from apps.accounts.admin import ProfileAdmin


@pytest.mark.django_db
class TestProfileAdminMasking:
    """admin.py get_masked_brn() 엣지 케이스 (50, 54-60 라인)"""
    
    @pytest.fixture
    def admin_site(self):
        return AdminSite()
    
    @pytest.fixture
    def profile_admin(self, admin_site):
        return ProfileAdmin(Profile, admin_site)
    
    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
    
    def test_masked_brn_none(self, profile_admin, user):
        """사업자번호 None인 경우 (50 라인)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = None
        profile.save()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == "-"
    
    def test_masked_brn_empty_string(self, profile_admin, user):
        """사업자번호 빈 문자열인 경우 (50 라인)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = ''
        profile.save()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == "-"
    
    def test_masked_brn_normal_10_digits(self, profile_admin, user):
        """정상 10자리 사업자번호 (54-60 라인)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '1234567890'
        profile.save()
        
        result = profile_admin.get_masked_brn(profile)
        
        # 123-45-***** 형태
        assert result == '12345*****'
        assert result.endswith('*****')
        assert len(result) == 10
    
    def test_masked_brn_short_number(self, profile_admin, user):
        """10자리 미만 사업자번호 (54-60 라인)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '12345'  # 5자리
        profile.save()
        
        result = profile_admin.get_masked_brn(profile)
        
        # 10자리 미만이면 전체 마스킹
        assert result == "*****"
    
    def test_masked_brn_9_digits(self, profile_admin, user):
        """9자리 사업자번호 (경계값)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '123456789'
        profile.save()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == "*****"
    
    def test_masked_brn_exactly_10_digits(self, profile_admin, user):
        """정확히 10자리 (경계값)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '0123456789'
        profile.save()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == '01234*****'
    
    def test_masked_brn_more_than_10_digits(self, profile_admin, user):
        """10자리 초과 (비정상이지만 처리)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '12345678901'  # 11자리
        profile.save()
        
        result = profile_admin.get_masked_brn(profile)
        
        # 10자리 이상이면 뒤 5자리 마스킹
        assert result.endswith('*****')
        assert len(result) == 11


@pytest.mark.django_db
class TestProfileModelMasking:
    """models.py get_masked_business_number() 비정상 길이 (56 라인)"""
    
    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
    
    def test_masked_business_number_empty(self, user):
        """사업자번호 비어있음"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = ''
        profile.save()
        
        result = profile.get_masked_business_number()
        
        assert result == ''
    
    def test_masked_business_number_none(self, user):
        """사업자번호 None"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = None
        profile.save()
        
        result = profile.get_masked_business_number()
        
        assert result == ''
    
    def test_masked_business_number_normal_10_digits(self, user):
        """정상 10자리"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '1234567890'
        profile.save()
        
        result = profile.get_masked_business_number()
        
        # 123-45-***** 형태
        assert result == '123-45-*****'
    
    def test_masked_business_number_short(self, user):
        """10자리 미만 (56 라인 - 이 부분이 누락됨!)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '12345'  # 5자리
        profile.save()
        
        result = profile.get_masked_business_number()
        
        # 10자리가 아니면 원본 그대로 반환
        assert result == '12345'
    
    def test_masked_business_number_9_digits(self, user):
        """9자리 (경계값)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '123456789'
        profile.save()
        
        result = profile.get_masked_business_number()
        
        # 10자리가 아니므로 원본 반환
        assert result == '123456789'
    
    def test_masked_business_number_exactly_10_digits(self, user):
        """정확히 10자리 (경계값)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '0000000000'
        profile.save()
        
        result = profile.get_masked_business_number()
        
        assert result == '000-00-*****'
    
    def test_masked_business_number_with_hyphens(self, user):
        """하이픈 포함된 번호"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '123-45-67890'  # 하이픈 포함 12자
        profile.save()
        
        result = profile.get_masked_business_number()
        
        # 하이픈 제거 후 10자리이므로 마스킹
        assert result == '123-45-*****'
    
    def test_masked_business_number_more_than_10_digits(self, user):
        """10자리 초과 (비정상)"""
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '12345678901'  # 11자리
        profile.save()
        
        result = profile.get_masked_business_number()
        
        # 하이픈 제거 후 10자리가 아니므로 원본 반환
        assert result == '12345678901'


@pytest.mark.django_db
class TestAdminIntegration:
    """Admin 통합 테스트"""
    
    @pytest.fixture
    def admin_site(self):
        return AdminSite()
    
    @pytest.fixture
    def profile_admin(self, admin_site):
        return ProfileAdmin(Profile, admin_site)
    
    def test_get_email_display(self, profile_admin):
        """이메일 표시 메서드"""
        user = User.objects.create_user(
            username='testuser',
            email='display@test.com',
            password='testpass123'
        )
        profile = Profile.objects.get(user=user)
        
        result = profile_admin.get_email(profile)
        
        assert result == 'display@test.com'
    
    def test_admin_list_display_fields(self, profile_admin):
        """list_display 필드 확인"""
        expected_fields = [
            'user',
            'get_email',
            'phone',
            'business_type',
            'get_masked_brn',
            'created_at'
        ]
        
        for field in expected_fields:
            assert field in profile_admin.list_display


@pytest.mark.django_db
class TestModelEdgeCases:
    """모델 엣지 케이스"""
    
    def test_profile_str_representation(self):
        """프로필 문자열 표현"""
        user = User.objects.create_user(
            username='strtest',
            password='test123'
        )
        profile = Profile.objects.get(user=user)
        
        str_repr = str(profile)
        
        assert 'strtest' in str_repr
        assert '프로필' in str_repr
    
    def test_profile_business_type_choices(self):
        """사업자 유형 선택지"""
        user = User.objects.create_user(username='test', password='test')
        profile = Profile.objects.get(user=user)
        
        # individual 설정
        profile.business_type = 'individual'
        profile.save()
        assert profile.business_type == 'individual'
        
        # corporate 설정
        profile.business_type = 'corporate'
        profile.save()
        assert profile.business_type == 'corporate'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])