import pytest
from apps.accounts.forms import ProfileForm, CustomUserCreationForm
from apps.accounts.models import Profile
from django.contrib.auth.models import User



@pytest.fixture
def test_user(db):
    """테스트용 유저와 프로필을 확실하게 생성하는 픽스처"""
    user = User.objects.create_user(username='testuser', password='password123')
    # get_or_create를 사용하여 시그널 유무와 상관없이 프로필을 확보합니다.
    Profile.objects.get_or_create(user=user)
    return user

@pytest.mark.django_db
class TestProfileForm:
    def test_profile_form_clean_brn_success(self, test_user):
        """하이픈이나 공백이 있어도 숫자로만 잘 정제되는지 테스트"""
        data = {
            'business_registration_number': '123-45-67890 ', # 하이픈과 공백 섞임
            'business_type': 'individual',
            'phone': '010-1234-5678'
        }
        form = ProfileForm(data=data, instance=test_user.profile)
        
        assert form.is_valid()
        # 정제된 데이터가 clean 메서드를 통해 하이픈이 제거되었는지 확인
        assert form.cleaned_data['business_registration_number'] == '1234567890'

    def test_profile_form_duplicate_brn(self, test_user, django_user_model):
        """이미 다른 사람이 사용 중인 사업자 번호일 때 에러 발생 테스트"""
        
        # 1. 다른 유저 생성
        other_user = django_user_model.objects.create_user(username='other', password='pass')
        
        # [수정 포인트] filter(...).update() 대신 확실하게 생성/수정
        Profile.objects.update_or_create(
            user=other_user, 
            defaults={'business_registration_number': '1112223333'}
        )
        
        # 2. 내 프로필 수정 폼에 동일 번호 입력
        data = {
            'business_registration_number': '1112223333', # 중복 발생 유도
            'business_type': 'individual',
            'phone': '010-0000-0000'
        }
        
        # test_user의 프로필 인스턴스를 넘김
        form = ProfileForm(data=data, instance=test_user.profile)
        
        # 3. 검증
        is_valid = form.is_valid()
        
        # 만약 여기서 실패한다면 어떤 에러가 있는지 출력해보기 (디버깅용)
        if is_valid:
            print(f"폼 에러: {form.errors}")
            
        assert not is_valid
        assert '이미 등록된 사업자 등록번호입니다.' in form.errors['business_registration_number']

@pytest.mark.django_db
class TestCustomUserCreationForm:
    def test_user_creation_form_password_mismatch(self):
        """비밀번호 불일치 시 에러 처리 테스트"""
        data = {
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'secure_pass123',
            'password2': 'different_pass', # 서로 다름
        }
        form = CustomUserCreationForm(data=data)
        
        assert not form.is_valid()
        # password2의 clean 메서드에서 걸러짐
        assert '두 비밀번호가 일치하지 않습니다.' in form.errors['password2']

    def test_user_creation_form_too_short_username(self):
        """아이디가 너무 짧을 때 에러 처리 테스트"""
        data = {
            'username': 'abc', # 4자 미만
            'email': 'new@test.com',
            'password1': 'secure_pass123',
            'password2': 'secure_pass123',
        }
        form = CustomUserCreationForm(data=data)
        
        assert not form.is_valid()
        assert '아이디는 최소 4자 이상이어야 합니다.' in form.errors['username']