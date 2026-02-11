import pytest
from django.contrib.auth.models import User
from apps.accounts.models import Profile
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.apps import AppConfig


@pytest.fixture
def test_user(db):
    user = User.objects.create_user(username='testuser', password='password123')
    # 시그널이 안 돌 수도 있으니 여기서도 안전하게 생성 확인
    Profile.objects.get_or_create(user=user)
    return user


@pytest.mark.django_db
class TestProfileModel:
    def test_profile_str_method(self, test_user):
        """프로필의 __str__ 메서드가 유저네임을 잘 반환하는지 테스트"""
        profile = test_user.profile
        # 모델에 정의한 __str__ 형식이 f"{self.user.username}의 프로필" 이라면:
        assert str(profile) == f"{test_user.username} 프로필"

    def test_business_registration_number_unique_constraint(self, test_user, django_user_model):
        """DB 레벨에서 사업자 번호 중복을 실제로 막는지 테스트"""
        # 1. 첫 번째 유저에게 번호 부여
        test_user.profile.business_registration_number = "1112223333"
        test_user.profile.save()
        
        # 2. 두 번째 유저 생성 및 동일 번호 시도
        other_user = django_user_model.objects.create_user(username='other', password='pass')
        # 시그널로 프로필이 생성되었다고 가정하고 업데이트
        other_profile = other_user.profile
        other_profile.business_registration_number = "1112223333"
        
        # 3. DB 저장 시 IntegrityError가 발생하는지 확인 (unique=True 검증)
        with pytest.raises(IntegrityError):
            other_profile.save()

    def test_profile_auto_creation_on_user_save(self, django_user_model):
        """유저 생성 시 프로필이 자동 생성되는지 (시그널) 검증"""
        new_user = django_user_model.objects.create_user(username='new_guy', password='password')
        
        # hasattr를 통해 profile 연결이 존재하는지 확인
        assert hasattr(new_user, 'profile')
        assert isinstance(new_user.profile, Profile)