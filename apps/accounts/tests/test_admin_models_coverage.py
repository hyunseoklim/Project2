"""
Accounts Admin & Models 커버리지 완성 테스트 (Pytest) - PostgreSQL 호환

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


@pytest.mark.django_db(transaction=True)  # ⭐ transaction=True 추가
class TestProfileAdminMasking:
    """admin.py get_masked_brn() 엣지 케이스 (50, 54-60 라인)"""
    
    @pytest.fixture
    def admin_site(self):
        return AdminSite()
    
    @pytest.fixture
    def profile_admin(self, admin_site):
        return ProfileAdmin(Profile, admin_site)
    
    @pytest.fixture
    def user_with_profile(self, db):
        """User와 Profile을 명시적으로 생성"""
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        # ⭐ Profile이 자동 생성되지 않는 경우를 대비해 get_or_create 사용
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        return user, profile
    
    def test_masked_brn_none(self, profile_admin, user_with_profile):
        """사업자번호 None인 경우 (50 라인)"""
        user, profile = user_with_profile
        profile.business_registration_number = None
        profile.save()
        
        # ⭐ DB에서 다시 가져오기 (PostgreSQL에서 중요)
        profile.refresh_from_db()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == "-"
    
    def test_masked_brn_empty_string(self, profile_admin, user_with_profile):
        """사업자번호 빈 문자열인 경우 (50 라인)"""
        user, profile = user_with_profile
        profile.business_registration_number = ''
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == "-"
    
    def test_masked_brn_normal_10_digits(self, profile_admin, user_with_profile):
        """정상 10자리 사업자번호 (54-60 라인)"""
        user, profile = user_with_profile
        profile.business_registration_number = '1234567890'
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile_admin.get_masked_brn(profile)
        
        # 12345***** 형태
        assert result == '12345*****'
        assert result.endswith('*****')
        assert len(result) == 10
    
    def test_masked_brn_short_number(self, profile_admin, user_with_profile):
        """10자리 미만 사업자번호 (54-60 라인)"""
        user, profile = user_with_profile
        profile.business_registration_number = '12345'  # 5자리
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile_admin.get_masked_brn(profile)
        
        # 10자리 미만이면 전체 마스킹
        assert result == "*****"
    
    def test_masked_brn_9_digits(self, profile_admin, user_with_profile):
        """9자리 사업자번호 (경계값)"""
        user, profile = user_with_profile
        profile.business_registration_number = '123456789'
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == "*****"
    
    def test_masked_brn_exactly_10_digits(self, profile_admin, user_with_profile):
        """정확히 10자리 (경계값)"""
        user, profile = user_with_profile
        profile.business_registration_number = '0123456789'
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile_admin.get_masked_brn(profile)
        
        assert result == '01234*****'


@pytest.mark.django_db(transaction=True)  # ⭐ transaction=True 추가
class TestProfileModelMasking:
    """models.py get_masked_business_number() 비정상 길이 (56 라인)"""
    
    @pytest.fixture
    def user_with_profile(self, db):
        """User와 Profile을 명시적으로 생성"""
        user = User.objects.create_user(
            username='modeltest',
            email='model@test.com',
            password='testpass123'
        )
        
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                'business_type': 'individual',
                'phone': '010-9999-8888'
            }
        )
        
        return user, profile
    
    def test_masked_business_number_empty(self, user_with_profile):
        """사업자번호 비어있음"""
        user, profile = user_with_profile
        profile.business_registration_number = ''
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile.get_masked_business_number()
        
        assert result == ''
    
    def test_masked_business_number_none(self, user_with_profile):
        """사업자번호 None"""
        user, profile = user_with_profile
        profile.business_registration_number = None
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile.get_masked_business_number()
        
        assert result == ''
    
    def test_masked_business_number_normal_10_digits(self, user_with_profile):
        """정상 10자리"""
        user, profile = user_with_profile
        profile.business_registration_number = '1234567890'
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile.get_masked_business_number()
        
        # 123-45-***** 형태
        assert result == '123-45-*****'
    
    def test_masked_business_number_short(self, user_with_profile):
        """10자리 미만 (56 라인 - 이 부분이 누락됨!)"""
        user, profile = user_with_profile
        profile.business_registration_number = '12345'  # 5자리
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile.get_masked_business_number()
        
        # 10자리가 아니면 원본 그대로 반환
        assert result == '12345'
    
    def test_masked_business_number_9_digits(self, user_with_profile):
        """9자리 (경계값)"""
        user, profile = user_with_profile
        profile.business_registration_number = '123456789'
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile.get_masked_business_number()
        
        # 10자리가 아니므로 원본 반환
        assert result == '123456789'
    
    def test_masked_business_number_exactly_10_digits(self, user_with_profile):
        """정확히 10자리 (경계값)"""
        user, profile = user_with_profile
        profile.business_registration_number = '0000000000'
        profile.save()
        
        profile.refresh_from_db()
        
        result = profile.get_masked_business_number()
        
        assert result == '000-00-*****'


@pytest.mark.django_db(transaction=True)
class TestAdminIntegration:
    """Admin 통합 테스트"""
    
    @pytest.fixture
    def admin_site(self):
        return AdminSite()
    
    @pytest.fixture
    def profile_admin(self, admin_site):
        return ProfileAdmin(Profile, admin_site)
    
    @pytest.fixture
    def user_with_profile(self, db):
        """고유한 username을 사용하여 충돌 방지"""
        import uuid
        username = f'displaytest_{uuid.uuid4().hex[:8]}'
        
        user = User.objects.create_user(
            username=username,
            email='display@test.com',
            password='testpass123'
        )
        
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={'business_type': 'individual'}
        )
        
        return user, profile
    
    def test_get_email_display(self, profile_admin, user_with_profile):
        """이메일 표시 메서드"""
        user, profile = user_with_profile
        
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


@pytest.mark.django_db(transaction=True)
class TestModelEdgeCases:
    """모델 엣지 케이스"""
    
    def test_profile_str_representation(self, db):
        """프로필 문자열 표현"""
        import uuid
        username = f'strtest_{uuid.uuid4().hex[:8]}'
        
        user = User.objects.create_user(
            username=username,
            password='test123'
        )
        
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={'business_type': 'individual'}
        )
        
        str_repr = str(profile)
        
        assert username in str_repr
        assert '프로필' in str_repr
    
    def test_profile_business_type_choices(self, db):
        """사업자 유형 선택지"""
        import uuid
        username = f'typetest_{uuid.uuid4().hex[:8]}'
        
        user = User.objects.create_user(username=username, password='test')
        
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={'business_type': 'individual'}
        )
        
        # individual 설정
        profile.business_type = 'individual'
        profile.save()
        profile.refresh_from_db()
        assert profile.business_type == 'individual'
        
        # corporate 설정
        profile.business_type = 'corporate'
        profile.save()
        profile.refresh_from_db()
        assert profile.business_type == 'corporate'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])