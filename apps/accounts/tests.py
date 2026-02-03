# uv run python manage.py test apps.accounts.tests
from django.test import TestCase
from django.contrib.auth.models import User
from .forms import ProfileForm
from .models import Profile
from django.urls import reverse

# views.py profile 테스트코드
class ProfileViewTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="password123")
        self.user2 = User.objects.create_user(username="user2", password="password123")
        # user1은 이미 사업자 번호를 가지고 있음
        Profile.objects.create(user=self.user1, business_registration_number="1234567890")
        # user2는 빈 프로필
        self.profile2, _ = Profile.objects.get_or_create(user=self.user2)

    def test_profile_edit_get_login_required(self):
        """로그인하지 않은 사용자가 수정을 시도하면 리다이렉트되는가?"""
        response = self.client.get(reverse('accounts:profile_edit'))
        self.assertNotEqual(response.status_code, 200)
        self.assertIn('/login/', response.url)

    def test_profile_edit_post_success(self):
        """정상 저장 테스트: 왜 200이 나오는지 원인을 파악합니다."""
        self.client.login(username="user2", password="password123")
        
        # 실제 ProfileForm의 필드명과 일치해야 합니다.
        data = {
            'business_registration_number': '9876543210',
            'business_type': 'individual',
            'phone': '01012345678'
        }
        
        response = self.client.post(reverse('accounts:profile_edit'), data)
        self.assertRedirects(response, reverse('accounts:home'))

    def test_profile_edit_integrity_error_message(self):
        """중복 체크 테스트: 폼 에러가 발생하는지 확인합니다."""
        self.client.login(username="user2", password="password123")
        
        response = self.client.post(reverse('accounts:profile_edit'), {
            'business_registration_number': '1234567890', # user1과 중복
            'business_type': 'corporate',
            'phone': '01011112222'
        })
        
        # 폼이 에러를 잡으면 200 상태코드가 유지됩니다.
        self.assertEqual(response.status_code, 200)
        
        form = response.context['form']
        # 에러 메시지 검사
        self.assertTrue(form.errors)

# forms.py 테스트 코드
class ProfileFormTest(TestCase):
    def setUp(self):
        # 1. 테스트 유저 생성
        self.user1 = User.objects.create_user(username="user1", password="password")
        self.user2 = User.objects.create_user(username="user2", password="password")
        
        # 2. user1용 프로필 생성 (중복 테스트 대상)
        Profile.objects.create(user=self.user1, business_registration_number="1234567890")
        
        # 3. user2용 프로필 생성 (수정 테스트 대상) - 이 부분이 빠져있었습니다!
        self.profile2 = Profile.objects.create(user=self.user2)

    def test_valid_brn(self):
        # self.user2.profile 대신 미리 만들어둔 self.profile2를 사용하면 안전합니다.
        form = ProfileForm(data={'business_registration_number': '9876543210'}, instance=self.profile2)
        self.assertTrue(form.is_valid())

    def test_valid_brn(self):
        """정상적인 번호 입력 시 통과해야 함"""
        form = ProfileForm(data={'business_registration_number': '9876543210'}, instance=self.user2.profile)
        self.assertTrue(form.is_valid())

    def test_brn_cleaning(self):
        """하이픈이나 공백이 있어도 정제되어 통과해야 함"""
        form = ProfileForm(data={'business_registration_number': '987-65-43210 '}, instance=self.user2.profile)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['business_registration_number'], '9876543210')

    def test_invalid_length(self):
        """10자리가 아니면 에러가 발생해야 함"""
        form = ProfileForm(data={'business_registration_number': '123'}, instance=self.user2.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('business_registration_number', form.errors)

    def test_duplicate_brn(self):
        """이미 존재하는 번호 입력 시 에러가 발생해야 함 (중복 체크)"""
        form = ProfileForm(data={'business_registration_number': '1234567890'}, instance=self.user2.profile)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['business_registration_number'], ["이미 등록된 사업자 등록번호입니다."])