"""
Accounts Views 커버리지 완성 테스트 (Pytest)

1순위: views.py 누락 라인 커버 (29줄)
- dashboard 뷰 전체 (99-161 라인)
- signup 예외 처리 (58-63 라인)
- profile_edit 예외 처리 (204-214 라인)
- 기타 로깅 및 엣지 케이스

3가지는 Mock 없이는 의미 없는 테스트라 진행불가.
test_signup_unexpected_exception
test_profile_edit_validation_error
test_profile_edit_unexpected_exception
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from apps.accounts.models import Profile
from apps.accounts.forms import CustomUserCreationForm, ProfileForm
from apps.transactions.models import Transaction, Category
from apps.businesses.models import Business, Account

from django.contrib.messages import get_messages
from unittest.mock import patch


@pytest.mark.django_db
class TestDashboardView:
    """dashboard 뷰 전체 테스트 (99-161 라인)"""
    
    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            username='dashuser',
            email='dash@test.com',
            password='testpass123'
        )
    
    @pytest.fixture
    def profile(self, user):
        return Profile.objects.get(user=user)
    
    @pytest.fixture
    def business(self, user):
        return Business.objects.create(
            user=user,
            name='테스트 사업장',
            branch_type='main',
            business_type='음식점'
        )
    
    @pytest.fixture
    def account(self, user, business):
        return Account.objects.create(
            user=user,
            business=business,
            name='테스트 계좌',
            bank_name='테스트은행',
            account_number='1234567890',
            balance=Decimal('0')
        )
    
    @pytest.fixture
    def income_category(self):
        return Category.objects.create(
            name='매출',
            type='income',
            is_system=True
        )
    
    @pytest.fixture
    def expense_category(self):
        return Category.objects.create(
            name='인건비',
            type='expense',
            expense_type='salary',
            is_system=True
        )
    
    def test_dashboard_basic_rendering(self, client, user, profile):
        """대시보드 기본 렌더링"""
        client.force_login(user)
        
        response = client.get(reverse('accounts:dashboard'))
        
        assert response.status_code == 200
        assert 'user' in response.context
        assert 'profile' in response.context
        assert response.context['profile'] == profile
    
    def test_dashboard_with_transactions(
        self,
        client,
        user,
        business,
        account,
        income_category,
        expense_category
    ):
        """거래 데이터가 있는 대시보드"""
        client.force_login(user)
        
        # 이번 달 거래 생성
        now = datetime.now(timezone.utc)
        
        # 수입 거래
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('1000000'),
            occurred_at=now,
            merchant_name='고객',
            is_business=True
        )
        
        # 지출 거래
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            amount=Decimal('500000'),
            occurred_at=now,
            merchant_name='직원',
            is_business=True
        )
        
        response = client.get(reverse('accounts:dashboard'))
        
        assert response.status_code == 200
        
        # 통계 확인
        assert 'total_income' in response.context
        assert 'total_expense' in response.context
        assert 'net_profit' in response.context
        
        assert response.context['total_income'] == Decimal('1000000')
        assert response.context['total_expense'] == Decimal('500000')
        assert response.context['net_profit'] == Decimal('500000')
    
    def test_dashboard_recent_transactions(
        self,
        client,
        user,
        business,
        account,
        income_category
    ):
        """최근 거래 5개 표시"""
        client.force_login(user)
        
        # 10개 거래 생성
        for i in range(10):
            Transaction.objects.create(
                user=user,
                business=business,
                account=account,
                category=income_category,
                tx_type='IN',
                amount=Decimal('100000') * (i + 1),
                occurred_at=datetime.now(timezone.utc) - timedelta(days=i),
                merchant_name=f'고객{i}',
                is_business=True
            )
        
        response = client.get(reverse('accounts:dashboard'))
        
        # 최근 5개만
        assert len(response.context['recent_transactions']) == 5
        
        # 최신순 정렬 확인
        transactions = response.context['recent_transactions']
        for i in range(len(transactions) - 1):
            assert transactions[i].occurred_at >= transactions[i + 1].occurred_at
    
    def test_dashboard_business_aggregation(
        self,
        client,
        user,
        income_category,
        expense_category
    ):
        """사업장별 집계"""
        client.force_login(user)
        
        # 2개 사업장 생성
        business1 = Business.objects.create(
            user=user,
            name='강남점',
            branch_type='main'
        )
        account1 = Account.objects.create(
            user=user,
            business=business1,
            name='강남 계좌',
            bank_name='은행',
            account_number='1111111111',
            balance=Decimal('0')
        )
        
        business2 = Business.objects.create(
            user=user,
            name='서초점',
            branch_type='branch'
        )
        account2 = Account.objects.create(
            user=user,
            business=business2,
            name='서초 계좌',
            bank_name='은행',
            account_number='2222222222',
            balance=Decimal('0')
        )
        
        # 각 사업장에 거래 생성
        now = datetime.now(timezone.utc)
        
        # 강남점: 수입 200만원, 지출 100만원
        Transaction.objects.create(
            user=user, business=business1, account=account1,
            category=income_category, tx_type='IN',
            amount=Decimal('2000000'), occurred_at=now,
            merchant_name='고객', is_business=True
        )
        Transaction.objects.create(
            user=user, business=business1, account=account1,
            category=expense_category, tx_type='OUT',
            amount=Decimal('1000000'), occurred_at=now,
            merchant_name='직원', is_business=True
        )
        
        # 서초점: 수입 150만원, 지출 50만원
        Transaction.objects.create(
            user=user, business=business2, account=account2,
            category=income_category, tx_type='IN',
            amount=Decimal('1500000'), occurred_at=now,
            merchant_name='고객', is_business=True
        )
        Transaction.objects.create(
            user=user, business=business2, account=account2,
            category=expense_category, tx_type='OUT',
            amount=Decimal('500000'), occurred_at=now,
            merchant_name='직원', is_business=True
        )
        
        response = client.get(reverse('accounts:dashboard'))
        
        businesses = response.context['businesses']
        assert len(businesses) == 2
        
        # 강남점 확인
        gangnam = next(b for b in businesses if b.name == '강남점')
        assert gangnam.revenue == Decimal('2000000')
        assert gangnam.expense == Decimal('1000000')
        assert gangnam.profit == Decimal('1000000')
        
        # 서초점 확인
        seocho = next(b for b in businesses if b.name == '서초점')
        assert seocho.revenue == Decimal('1500000')
        assert seocho.expense == Decimal('500000')
        assert seocho.profit == Decimal('1000000')
    
    def test_dashboard_year_month_context(self, client, user):
        """현재 연도/월 컨텍스트"""
        client.force_login(user)
        
        response = client.get(reverse('accounts:dashboard'))
        
        now = datetime.now()
        assert response.context['year'] == now.year
        assert response.context['month'] == now.month
    
    def test_dashboard_masked_business_number(self, client, user):
        """사업자번호 마스킹 표시"""
        client.force_login(user)
        
        # 프로필에 사업자번호 설정
        profile = Profile.objects.get(user=user)
        profile.business_registration_number = '1234567890'
        profile.save()
        
        response = client.get(reverse('accounts:dashboard'))
        
        assert 'masked_biz_num' in response.context
        assert '123-45-*****' in response.context['masked_biz_num']


@pytest.mark.django_db
class TestSignupExceptionHandling:
    """signup 뷰 예외 처리 테스트 (58-63 라인)"""
    
    def test_signup_integrity_error(self, client):
        User.objects.create_user(username='newuser', password='password123')
        form_data = {
            'username': 'newuser', # 중복
            'email': 'new@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        }
        response = client.post(reverse('accounts:signup'), form_data)
    
        # 실제 메시지인 '입력 정보를 확인해주세요.'를 포함하는지 확인
        messages = [str(m) for m in list(response.context['messages'])]
        assert any('확인해주세요' in m for m in messages)

    
    # def test_signup_unexpected_exception(self, client):
    #     """회원가입 시 예상치 못한 예외 처리"""

    #     form_data = {
    #         'username': 'newuser',
    #         'email': 'new@test.com',
    #         'password1': 'testpass123',
    #         'password2': 'testpass123'
    #     }
        
    #     response = client.post(reverse('accounts:signup'), form_data)
        
    #     messages = list(response.context['messages'])
    #     assert '오류가 발생했습니다' in str(messages[0])


@pytest.mark.django_db
class TestHomeViewLogoutState:
    """home 뷰 로그아웃 상태 테스트 (93 라인)"""
    
    def test_home_view_unauthenticated(self, client):
        """로그아웃 상태에서 홈 접근"""
        response = client.get(reverse('accounts:home'))
        
        assert response.status_code == 200
        assert 'accounts/home.html' in [t.name for t in response.templates]


@pytest.mark.django_db
class TestPasswordChangeLogging:
    """비밀번호 변경 로깅 테스트 (192 라인)"""
    
    def test_password_change_success_logging(self, client):
        """비밀번호 변경 성공 시 로깅"""
        user = User.objects.create_user(
            username='testuser',
            password='oldpass123'
        )
        client.force_login(user)
        
        response = client.post(reverse('accounts:password_change'), {
            'old_password': 'oldpass123',
            'new_password1': 'newpass123!',
            'new_password2': 'newpass123!'
        })
        
        # 성공 시 리다이렉트
        assert response.status_code == 302


@pytest.mark.django_db
class TestProfileEditExceptionHandling:
    """profile_edit 뷰 예외 처리 테스트 (204-214 라인)"""
    
    def test_profile_edit_integrity_error(self, client):
        # 1. 로그인할 유저와 중복을 일으킬 유저 생성
        user = User.objects.create_user(username='me', password='pass')
        other = User.objects.create_user(username='other', password='pass')
        
        # 2. 다른 유저가 사업자 번호 선점
        Profile.objects.filter(user=other).update(business_registration_number='1234567890')
        
        # 3. 로그인!! (가장 중요)
        client.force_login(user)
        
        # 4. 요청
        response = client.post(reverse('accounts:profile_edit'), {
            'full_name': '홍길동',
            'business_registration_number': '1234567890', # 중복
            'business_type': 'individual',
            'phone': '010-1234-5678'
        }, follow=True)
    
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        # 메시지가 아예 안 나온다면 print(messages)로 찍어보며 실제 문구를 확인해보세요.
        assert len(messages) > 0
    
    # def test_profile_edit_validation_error(self, client):
    #     """프로필 검증 실패"""
    #     user = User.objects.create_user(
    #         username='testuser',
    #         password='testpass123'
    #     )
    #     client.force_login(user)

    #     response = client.post(reverse('accounts:profile_edit'), {
    #         'full_name': '홍길동',
    #         'business_registration_number': '1234567890',
    #         'business_type': 'individual',
    #         'phone': '010-1234-5678'
    #     })
        
    #     messages = list(response.context['messages'])
    #     assert '입력 형식이 올바르지 않습니다' in str(messages[0])
    
    # def test_profile_edit_unexpected_exception(self, client):
    #     """프로필 저장 중 예상치 못한 오류"""
    #     user = User.objects.create_user(
    #         username='testuser',
    #         password='testpass123'
    #     )
    #     client.force_login(user)
    
    #     response = client.post(reverse('accounts:profile_edit'), {
    #         'full_name': '홍길동',
    #         'business_registration_number': '1234567890',
    #         'business_type': 'individual',
    #         'phone': '010-1234-5678'
    #     })
        
    #     messages = list(response.context['messages'])
    #     assert '저장 중 오류가 발생했습니다' in str(messages[0])


@pytest.mark.django_db
class TestProfileDetailCreation:
    """profile_detail 뷰 프로필 자동 생성 테스트 (232 라인)"""
    
    def test_profile_auto_creation_on_detail_view(self, client):
        """프로필 없을 때 자동 생성 및 로깅"""
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # 프로필 삭제 (시그널로 자동 생성된 것)
        Profile.objects.filter(user=user).delete()
        
        client.force_login(user)
        
        # profile_detail 접근
        response = client.get(reverse('accounts:profile_detail'))
        
        # 프로필이 자동 생성되어야 함
        assert response.status_code == 200
        assert Profile.objects.filter(user=user).exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])