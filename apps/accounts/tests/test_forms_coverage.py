"""
Accounts Forms 커버리지 완성 테스트 (Pytest)

2순위: forms.py 누락 라인 커버 (10줄)
- ProfileForm ValidationError (63, 70, 73 라인)
- CustomUserCreationForm ValidationError (147, 151, 155, 165, 169, 183, 188 라인)
"""
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.accounts.forms import ProfileForm, CustomUserCreationForm
from apps.accounts.models import Profile


@pytest.mark.django_db
class TestProfileFormValidation:
    """ProfileForm ValidationError 케이스"""
    
    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
    
    @pytest.fixture
    def profile(self, user):
        return Profile.objects.get(user=user)
    
    def test_business_number_empty_allowed(self, user, profile):
        """사업자번호 비어있음 허용 (63 라인)"""
        form = ProfileForm(
            instance=profile,
            data={
                'full_name': '홍길동',
                'business_registration_number': '',  # 빈 값
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        # 빈 값은 허용 (blank=True)
        assert form.is_valid()
        cleaned_brn = form.clean_business_registration_number()
        assert cleaned_brn == ''
    
    def test_business_number_non_digit(self, user, profile):
        """사업자번호 숫자 아닌 문자 포함 (70 라인)"""
        form = ProfileForm(
            instance=profile,
            data={
                'full_name': '홍길동',
                'business_registration_number': '123abc7890',  # 문자 포함
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        assert not form.is_valid()
        assert 'business_registration_number' in form.errors
        assert '숫자만 입력 가능' in str(form.errors['business_registration_number'])
    
    def test_business_number_wrong_length(self, user, profile):
        """사업자번호 10자리 아님 (73 라인)"""
        # 9자리
        form_short = ProfileForm(
            instance=profile,
            data={
                'full_name': '홍길동',
                'business_registration_number': '123456789',  # 9자리
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        assert not form_short.is_valid()
        assert '10자리' in str(form_short.errors['business_registration_number'])
        
        # 11자리
        form_long = ProfileForm(
            instance=profile,
            data={
                'full_name': '홍길동',
                'business_registration_number': '12345678901',  # 11자리
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        assert not form_long.is_valid()
        assert '10자리' in str(form_long.errors['business_registration_number'])
    
    def test_business_number_with_hyphens_cleaned(self, user, profile):
        """사업자번호 하이픈 포함 시 자동 제거"""
        form = ProfileForm(
            instance=profile,
            data={
                'full_name': '홍길동',
                'business_registration_number': '123-45-67890',  # 하이픈 포함
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        assert form.is_valid()
        # 하이픈이 제거되어야 함
        assert form.cleaned_data['business_registration_number'] == '1234567890'


@pytest.mark.django_db
class TestCustomUserCreationFormValidation:
    """CustomUserCreationForm ValidationError 케이스"""
    
    def test_username_too_short(self):
        """아이디 4자 미만 (147 라인)"""
        form = CustomUserCreationForm(data={
            'username': 'abc',  # 3자리
            'email': 'test@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert not form.is_valid()
        assert 'username' in form.errors
        assert '최소 4자' in str(form.errors['username'])
    
    def test_username_too_long(self):
        """아이디 20자 초과 (151 라인)"""
        form = CustomUserCreationForm(data={
            'username': 'a' * 21,  # 21자리
            'email': 'test@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert not form.is_valid()
        assert 'username' in form.errors
        assert '최대 20자' in str(form.errors['username'])
    
    def test_username_invalid_characters(self):
        """아이디 영문/숫자 외 문자 (155 라인)"""
        invalid_usernames = [
            'user@name',  # 특수문자
            'user-name',  # 하이픈
            'user_name',  # 언더스코어
            '사용자이름',  # 한글
        ]
        
        for username in invalid_usernames:
            form = CustomUserCreationForm(data={
                'username': username,
                'email': 'test@test.com',
                'password1': 'testpass123',
                'password2': 'testpass123'
            })
            
            assert not form.is_valid()
            assert 'username' in form.errors
            assert '영문과 숫자만' in str(form.errors['username'])
    
    def test_username_duplicate(self):
        """아이디 중복"""
        # 기존 사용자 생성
        User.objects.create_user(
            username='existinguser',
            email='existing@test.com',
            password='testpass123'
        )
        
        # 같은 아이디로 가입 시도
        form = CustomUserCreationForm(data={
            'username': 'existinguser',
            'email': 'new@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert not form.is_valid()
        assert 'username' in form.errors
        assert '이미 사용 중' in str(form.errors['username'])
    
    def test_email_duplicate(self):
        """이메일 중복"""
        # 기존 사용자 생성
        User.objects.create_user(
            username='user1',
            email='duplicate@test.com',
            password='testpass123'
        )
        
        # 같은 이메일로 가입 시도
        form = CustomUserCreationForm(data={
            'username': 'user2',
            'email': 'duplicate@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert not form.is_valid()
        assert 'email' in form.errors
        assert '이미 가입된' in str(form.errors['email'])
    
    def test_email_no_at_symbol(self):
        """이메일 @ 없음 (165 라인)"""
        form = CustomUserCreationForm(data={
            'username': 'testuser',
            'email': 'invalidemail.com',  # @ 없음
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert not form.is_valid()
        assert 'email' in form.errors
        assert '올바른 이메일' in str(form.errors['email'])
    
    def test_password_too_short(self):
        """비밀번호 8자 미만 (169 라인)"""
        form = CustomUserCreationForm(data={
            'username': 'testuser',
            'email': 'test@test.com',
            'password1': 'short1',  # 6자리
            'password2': 'short1'
        })
        
        assert not form.is_valid()
        assert 'password1' in form.errors
        assert '최소 8자' in str(form.errors['password1'])
    
    def test_password_only_digits(self):
        """비밀번호 숫자만"""
        form = CustomUserCreationForm(data={
            'username': 'testuser',
            'email': 'test@test.com',
            'password1': '12345678',  # 숫자만
            'password2': '12345678'
        })
        
        assert not form.is_valid()
        assert 'password1' in form.errors
        assert '숫자만으로 구성할 수 없습니다' in str(form.errors['password1'])
    
    def test_password_too_common(self):
        """비밀번호 너무 흔함"""
        common_passwords = ['password', '12345678', 'qwerty123', 'abc12345']
        
        for pwd in common_passwords:
            form = CustomUserCreationForm(data={
                'username': 'testuser',
                'email': 'test@test.com',
                'password1': pwd,
                'password2': pwd
            })
            
            assert not form.is_valid()
            assert 'password1' in form.errors
            # 특정 문구 대신 에러가 존재함을 확인하거나, 여러 가능성을 열어둠
            error_msg = str(form.errors['password1'])
            assert any(term in error_msg for term in ['흔한', '숫자만', '일상적인'])
        
    def test_password_mismatch(self):
        """비밀번호 불일치 (183 라인)"""
        form = CustomUserCreationForm(data={
            'username': 'testuser',
            'email': 'test@test.com',
            'password1': 'testpass123',
            'password2': 'testpass456'  # 다름
        })
        
        assert not form.is_valid()
        assert 'password2' in form.errors
        assert '일치하지 않습니다' in str(form.errors['password2'])
    
    def test_email_saved_on_user(self):
        """이메일 User 모델에 저장 (188 라인)"""
        form = CustomUserCreationForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert form.is_valid()
        user = form.save()
        
        # 이메일이 User 모델에 저장되어야 함
        assert user.email == 'new@test.com'


@pytest.mark.django_db
class TestFormsBoundaryValues:
    """경계값 테스트"""
    
    def test_username_exactly_4_chars(self):
        """아이디 정확히 4자 (통과)"""
        form = CustomUserCreationForm(data={
            'username': 'test',  # 4자
            'email': 'test@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert form.is_valid()
    
    def test_username_exactly_20_chars(self):
        """아이디 정확히 20자 (통과)"""
        form = CustomUserCreationForm(data={
            'username': 'a' * 20,  # 20자
            'email': 'test@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert form.is_valid()
    
    def test_password_exactly_8_chars(self):
        """비밀번호 정확히 8자 (통과)"""
        form = CustomUserCreationForm(data={
            'username': 'testuser',
            'email': 'test@test.com',
            'password1': 'testpas1',  # 8자
            'password2': 'testpas1'
        })
        
        assert form.is_valid()
    
    def test_business_number_exactly_10_digits(self):
        """사업자번호 정확히 10자리 (통과)"""
        user = User.objects.create_user(username='test', password='test')
        profile = Profile.objects.get(user=user)
        
        form = ProfileForm(
            instance=profile,
            data={
                'full_name': '홍길동',
                'business_registration_number': '1234567890',  # 10자리
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        assert form.is_valid()


@pytest.mark.django_db
class TestFormsEdgeCases:
    """엣지 케이스"""
    
    def test_business_number_with_spaces(self):
        """사업자번호 공백 포함 (자동 제거)"""
        user = User.objects.create_user(username='test', password='test')
        profile = Profile.objects.get(user=user)
        
        form = ProfileForm(
            instance=profile,
            data={
                'full_name': '홍길동',
                'business_registration_number': '123 456 7890',  # 공백 포함
                'business_type': 'individual',
                'phone': '010-1234-5678'
            }
        )
        
        assert form.is_valid()
        assert form.cleaned_data['business_registration_number'] == '1234567890'
    
    def test_username_alphanumeric_mix(self):
        """아이디 영문+숫자 조합 (통과)"""
        form = CustomUserCreationForm(data={
            'username': 'user123',
            'email': 'test@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        assert form.is_valid()
    
    def test_password_alphanumeric_special(self):
        """비밀번호 영문+숫자+특수문자 (통과)"""
        form = CustomUserCreationForm(data={
            'username': 'testuser',
            'email': 'test@test.com',
            'password1': 'Test@123!',
            'password2': 'Test@123!'
        })
        
        assert form.is_valid()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])