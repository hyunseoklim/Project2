import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from apps.businesses.models import Business

@pytest.mark.django_db
class TestSecurity:
    
    # --- 1. 인증 테스트 (Authentication) ---
    
    def test_unauthenticated_user_redirected_from_dashboard(self, client):
        """로그인 안 한 사용자가 대시보드 접근 시 로그인 페이지로 튕기는지"""
        url = reverse('accounts:dashboard')
        response = client.get(url)
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_unauthenticated_user_cannot_edit_profile(self, client):
        """로그인 안 한 사용자가 프로필 수정 페이지 접근 불가한지"""
        url = reverse('accounts:profile_edit')
        response = client.get(url)
        assert response.status_code == 302

    # --- 2. 인가/권한 테스트 (Authorization) ---

    def test_user_cannot_access_others_business_statistics(self, client):
        """A 사용자가 B 사용자의 사업장 통계 페이지를 볼 수 없는지 (보안 핵심)"""
        # 유저 A와 B 생성
        user_a = User.objects.create_user(username='user_a', password='pass123')
        user_b = User.objects.create_user(username='user_b', password='pass123')
        
        # 유저 B의 사업장 생성
        business_b = Business.objects.create(user=user_b, name="B의 가게", is_active=True)
        
        # 유저 A로 로그인
        client.login(username='user_a', password='pass123')
        
        # 유저 B의 사업장 통계 URL 접근
        url = reverse('businesses:business_statistics', kwargs={'pk': business_b.pk})
        response = client.get(url)
        
        # 실패(404 or 403)해야 성공! 만약 200이 뜨면 보안 구멍입니다.
        assert response.status_code in [403, 404]

    # --- 3. 회원가입/로그인 보안 ---

    def test_authenticated_user_cannot_signup_again(self, client):
        """이미 로그인한 사용자가 회원가입 페이지로 가려고 하면 홈으로 튕기는지"""
        user = User.objects.create_user(username='tester', password='pass123')
        client.login(username='tester', password='pass123')
        
        url = reverse('accounts:signup')
        response = client.get(url)
        
        # 사장님 view 로직에 redirect('accounts:home')이 있으므로 302 확인
        assert response.status_code == 302
        assert response.url == reverse('accounts:home')

    # --- 4. 비밀번호 보안 ---

    def test_password_change_requires_login(self, client):
        """로그인 없이 비밀번호 변경 주소로 접근 시 차단되는지"""
        url = reverse('accounts:password_change') # 사장님 urls.py 네임 확인 필요
        response = client.get(url)
        assert response.status_code == 302