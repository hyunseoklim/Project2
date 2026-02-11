# =============================================================================
# businesses/tests/test_views.py - pytest Views 테스트 (Part 1: Account Views)
# =============================================================================

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import Client
from django.contrib.messages import get_messages
from unittest.mock import patch, MagicMock

from apps.businesses.models import Business, Account


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """테스트 클라이언트"""
    return Client()


@pytest.fixture
def user(db):
    """테스트용 사용자 (이미 있으면 get)"""
    user, _ = User.objects.get_or_create(
        username='tester',
        defaults={
            'email': 'tester@example.com',
            'password': 'testpass123'
        }
    )
    if not user.check_password('testpass123'):
        user.set_password('testpass123')
        user.save()
    return user


@pytest.fixture
def other_user(db):
    """다른 사용자"""
    return User.objects.create_user(
        username='otheruser',
        email='other@example.com',
        password='testpass123'
    )


@pytest.fixture
def authenticated_client(client, user):
    """로그인된 클라이언트"""
    client.login(username='tester', password='testpass123')
    return client


@pytest.fixture
def business(db, user):
    """테스트용 사업장"""
    return Business.objects.create(
        user=user,
        name='강남점',
        location='서울시 강남구',
        business_type='소매업'
    )


@pytest.fixture
def account(db, user, business):
    """테스트용 계좌"""
    return Account.objects.create(
        user=user,
        business=business,
        name='국민은행 주거래',
        bank_name='국민은행',
        account_number='1234-5678-9012-3456',
        account_type='business',
        balance=Decimal('1000000.00')
    )


@pytest.fixture
def multiple_accounts(db, user, business):
    """여러 개의 계좌 생성"""
    accounts = []
    for i in range(25):  # 페이지네이션 테스트용
        account = Account.objects.create(
            user=user,
            business=business if i % 2 == 0 else None,
            name=f'계좌{i}',
            bank_name='은행',
            account_number=f'{i:04d}-5678-9012',
            account_type='business' if i % 2 == 0 else 'personal',
            balance=Decimal('100000.00') * (i + 1)
        )
        accounts.append(account)
    return accounts


# =============================================================================
# account_list 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountListView:
    """계좌 목록 뷰 테스트"""
    
    def test_account_list_requires_login(self, client):
        """로그인 필요 테스트"""
        url = reverse('businesses:account_list')
        response = client.get(url)
        
        assert response.status_code == 302  # 리다이렉트
        assert '/login/' in response.url
    
    def test_account_list_success(self, authenticated_client, account):
        """계좌 목록 조회 성공"""
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'page_obj' in response.context
        assert 'search_form' in response.context
        assert account in response.context['page_obj']
    
    def test_account_list_only_shows_own_accounts(self, authenticated_client, account, other_user):
        """본인 계좌만 표시"""
        # 다른 사용자의 계좌
        other_account = Account.objects.create(
            user=other_user,
            name='남의 계좌',
            bank_name='은행',
            account_number='9999-9999-9999'
        )
        
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url)
        
        accounts = list(response.context['page_obj'])
        assert account in accounts
        assert other_account not in accounts
    
    def test_account_list_filter_by_account_type(self, authenticated_client, user, business):
        """계좌 타입으로 필터링"""
        # 사업용 계좌
        business_account = Account.objects.create(
            user=user, business=business, name='사업용',
            bank_name='은행', account_number='1111',
            account_type='business'
        )
        # 개인용 계좌
        personal_account = Account.objects.create(
            user=user, name='개인용',
            bank_name='은행', account_number='2222',
            account_type='personal'
        )
        
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url, {'account_type': 'business'})
        
        accounts = list(response.context['page_obj'])
        assert business_account in accounts
        assert personal_account not in accounts
    
    def test_account_list_filter_by_business(self, authenticated_client, user):
        """사업장으로 필터링"""
        business1 = Business.objects.create(user=user, name='사업장1')
        business2 = Business.objects.create(user=user, name='사업장2')
        
        account1 = Account.objects.create(
            user=user, business=business1, name='계좌1',
            bank_name='은행', account_number='1111'
        )
        account2 = Account.objects.create(
            user=user, business=business2, name='계좌2',
            bank_name='은행', account_number='2222'
        )
        
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url, {'business': business1.pk})
        
        accounts = list(response.context['page_obj'])
        assert account1 in accounts
        assert account2 not in accounts
    
    def test_account_list_search_by_name(self, authenticated_client, user):
        """계좌명으로 검색"""
        account1 = Account.objects.create(
            user=user, name='국민은행 주거래',
            bank_name='국민은행', account_number='1111'
        )
        account2 = Account.objects.create(
            user=user, name='신한은행 적금',
            bank_name='신한은행', account_number='2222'
        )
        
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url, {'search': '국민은행'})
        
        accounts = list(response.context['page_obj'])
        assert account1 in accounts
        assert account2 not in accounts
    
    def test_account_list_search_by_bank_name(self, authenticated_client, user):
        """은행명으로 검색"""
        account1 = Account.objects.create(
            user=user, name='주거래',
            bank_name='국민은행', account_number='1111'
        )
        account2 = Account.objects.create(
            user=user, name='적금',
            bank_name='신한은행', account_number='2222'
        )
        
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url, {'search': '신한'})
        
        accounts = list(response.context['page_obj'])
        assert account2 in accounts
        assert account1 not in accounts
    
    def test_account_list_pagination(self, authenticated_client, multiple_accounts):
        """페이지네이션 테스트 (페이지당 20개)"""
        url = reverse('businesses:account_list')
        
        # 1페이지
        response = authenticated_client.get(url)
        assert len(response.context['page_obj']) == 20
        
        # 2페이지
        response = authenticated_client.get(url, {'page': 2})
        assert len(response.context['page_obj']) == 5  # 총 25개 중 나머지 5개
    
    def test_account_list_summary_statistics(self, authenticated_client, user):
        """요약 통계 확인"""
        Account.objects.create(
            user=user, name='계좌1', bank_name='은행',
            account_number='1111', account_type='business',
            balance=Decimal('500000')
        )
        Account.objects.create(
            user=user, name='계좌2', bank_name='은행',
            account_number='2222', account_type='personal',
            balance=Decimal('300000')
        )
        
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url)
        
        assert response.context['total_count'] == 2
        assert response.context['business_count'] == 1
        assert response.context['personal_count'] == 1
        assert response.context['total_balance'] == Decimal('800000')
    
    def test_account_list_template_used(self, authenticated_client, account):
        """올바른 템플릿 사용 확인"""
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url)
        
        assert 'businesses/account_list.html' in [t.name for t in response.templates]


# =============================================================================
# account_detail 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountDetailView:
    """계좌 상세 뷰 테스트"""
    
    def test_account_detail_requires_login(self, client, account):
        """로그인 필요"""
        url = reverse('businesses:account_detail', kwargs={'pk': account.pk})
        response = client.get(url)
        
        assert response.status_code == 302
        assert '/login/' in response.url
    
    def test_account_detail_success(self, authenticated_client, account):
        """계좌 상세 조회 성공"""
        url = reverse('businesses:account_detail', kwargs={'pk': account.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.context['account'] == account
    
    def test_account_detail_other_user_account_404(self, authenticated_client, other_user):
        """다른 사용자의 계좌 조회 시 404"""
        other_account = Account.objects.create(
            user=other_user,
            name='남의 계좌',
            bank_name='은행',
            account_number='9999'
        )
        
        url = reverse('businesses:account_detail', kwargs={'pk': other_account.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 404
    
    def test_account_detail_shows_statistics(self, authenticated_client, account):
        """통계 정보 표시"""
        url = reverse('businesses:account_detail', kwargs={'pk': account.pk})
        response = authenticated_client.get(url)
        
        stats = response.context['stats']
        assert 'total_count' in stats
        assert 'income_count' in stats
        assert 'expense_count' in stats
        assert 'total_income' in stats
        assert 'total_expense' in stats
        assert 'net_amount' in stats
    
    def test_account_detail_recent_transactions(self, authenticated_client, account):
        """최근 거래 내역 표시"""
        url = reverse('businesses:account_detail', kwargs={'pk': account.pk})
        response = authenticated_client.get(url)
        
        assert 'recent_transactions' in response.context


# =============================================================================
# account_create 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountCreateView:
    """계좌 생성 뷰 테스트"""
    
    def test_account_create_get_requires_login(self, client):
        """로그인 필요 (GET)"""
        url = reverse('businesses:account_create')
        response = client.get(url)
        
        assert response.status_code == 302
    
    def test_account_create_get_success(self, authenticated_client):
        """계좌 생성 폼 표시"""
        url = reverse('businesses:account_create')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'form' in response.context
    
    def test_account_create_post_success(self, authenticated_client, business):
        """계좌 생성 성공"""
        url = reverse('businesses:account_create')
        data = {
            'name': '새 계좌',
            'bank_name': '국민은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'business',
            'business': business.pk,
        }
        
        response = authenticated_client.post(url, data)
        
        # 리다이렉트 확인
        assert response.status_code == 302
        
        # 계좌 생성 확인
        assert Account.objects.filter(name='새 계좌').exists()
        
        # 성공 메시지 확인
        messages = list(get_messages(response.wsgi_request))
        assert any('생성되었습니다' in str(m) for m in messages)
    
    def test_account_create_post_invalid_data(self, authenticated_client):
        """유효하지 않은 데이터로 생성 시도"""
        url = reverse('businesses:account_create')
        data = {
            'name': '',  # 빈 값
            'bank_name': '은행',
            'account_number': '123',  # 너무 짧음
        }
        
        response = authenticated_client.post(url, data)
        
        # 폼 에러로 같은 페이지 표시
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['form'].errors
    
    def test_account_create_sets_user_automatically(self, authenticated_client, user):
        """계좌 생성 시 사용자 자동 설정"""
        url = reverse('businesses:account_create')
        data = {
            'name': '새 계좌',
            'bank_name': '은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'personal',
        }
        
        authenticated_client.post(url, data)
        
        account = Account.objects.get(name='새 계좌')
        assert account.user == user
    
    def test_account_create_duplicate_account_number(self, authenticated_client, account):
        """중복 계좌번호 생성 시도"""
        url = reverse('businesses:account_create')
        data = {
            'name': '새 계좌',
            'bank_name': '은행',
            'account_number': account.account_number,  # 중복
            'account_type': 'personal',
        }
        
        response = authenticated_client.post(url, data)
        
        # 에러 메시지 확인
        messages = list(get_messages(response.wsgi_request))
        assert any('이미 등록된' in str(m) or '실패' in str(m) for m in messages)


# =============================================================================
# account_update 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountUpdateView:
    """계좌 수정 뷰 테스트"""
    
    def test_account_update_get_success(self, authenticated_client, account):
        """계좌 수정 폼 표시"""
        url = reverse('businesses:account_update', kwargs={'pk': account.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['account'] == account
    
    def test_account_update_post_success(self, authenticated_client, account):
        """계좌 수정 성공"""
        url = reverse('businesses:account_update', kwargs={'pk': account.pk})
        data = {
            'name': '수정된 계좌명',
            'bank_name': account.bank_name,
            'account_number': account.account_number,
            'account_type': account.account_type,
        }
        
        response = authenticated_client.post(url, data)
        
        assert response.status_code == 302
        
        account.refresh_from_db()
        assert account.name == '수정된 계좌명'
        
        messages = list(get_messages(response.wsgi_request))
        assert any('수정되었습니다' in str(m) for m in messages)
    
    def test_account_update_other_user_account_404(self, authenticated_client, other_user):
        """다른 사용자의 계좌 수정 시도"""
        other_account = Account.objects.create(
            user=other_user,
            name='남의 계좌',
            bank_name='은행',
            account_number='9999'
        )
        
        url = reverse('businesses:account_update', kwargs={'pk': other_account.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 404


# =============================================================================
# account_delete 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountDeleteView:
    """계좌 삭제 뷰 테스트"""
    
    def test_account_delete_get_confirmation_page(self, authenticated_client, account):
        """삭제 확인 페이지 표시"""
        url = reverse('businesses:account_delete', kwargs={'pk': account.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.context['account'] == account
        assert 'transaction_count' in response.context
    
    def test_account_delete_post_success(self, authenticated_client, account):
        """계좌 소프트 삭제 성공"""
        url = reverse('businesses:account_delete', kwargs={'pk': account.pk})
        response = authenticated_client.post(url)
        
        assert response.status_code == 302
        
        account.refresh_from_db()
        assert account.is_active is False
        
        messages = list(get_messages(response.wsgi_request))
        assert any('삭제되었습니다' in str(m) for m in messages)
    
    def test_account_delete_other_user_account_404(self, authenticated_client, other_user):
        """다른 사용자의 계좌 삭제 시도"""
        other_account = Account.objects.create(
            user=other_user,
            name='남의 계좌',
            bank_name='은행',
            account_number='9999'
        )
        
        url = reverse('businesses:account_delete', kwargs={'pk': other_account.pk})
        response = authenticated_client.post(url)
        
        assert response.status_code == 404


# =============================================================================
# account_restore 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountRestoreView:
    """계좌 복구 뷰 테스트"""
    
    def test_account_restore_get_confirmation_page(self, authenticated_client, account):
        """복구 확인 페이지"""
        account.soft_delete()
        
        url = reverse('businesses:account_restore', kwargs={'pk': account.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.context['account'] == account
    
    def test_account_restore_post_success(self, authenticated_client, account):
        """계좌 복구 성공"""
        # 삭제
        account.soft_delete()
        account.refresh_from_db()
        assert account.is_active is False
        
        # 복구
        url = reverse('businesses:account_restore', kwargs={'pk': account.pk})
        response = authenticated_client.post(url)
        
        # 검증
        assert response.status_code == 302
        account.refresh_from_db()
        assert account.is_active is True 
    
    def test_account_restore_already_active_warning(self, authenticated_client, account):
        """이미 활성 상태인 계좌 복구 시도"""
        url = reverse('businesses:account_restore', kwargs={'pk': account.pk})
        response = authenticated_client.post(url)
        
        messages = list(get_messages(response.wsgi_request))
        assert any('이미 활성' in str(m) for m in messages)


# =============================================================================
# account_summary 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountSummaryView:
    """계좌 요약 대시보드 뷰 테스트"""
    
    def test_account_summary_requires_login(self, client):
        """로그인 필요"""
        url = reverse('businesses:account_summary')
        response = client.get(url)
        
        assert response.status_code == 302
    
    def test_account_summary_success(self, authenticated_client, user):
        """요약 대시보드 표시"""
        # 테스트 데이터 생성
        business = Business.objects.create(user=user, name='사업장')
        Account.objects.create(
            user=user, business=business, name='계좌1',
            bank_name='은행', account_number='1111',
            account_type='business', balance=Decimal('500000')
        )
        Account.objects.create(
            user=user, name='계좌2',
            bank_name='은행', account_number='2222',
            account_type='personal', balance=Decimal('300000')
        )
        
        url = reverse('businesses:account_summary')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.context['total_count'] == 2
        assert response.context['business_count'] == 1
        assert response.context['personal_count'] == 1
        assert response.context['total_balance'] == Decimal('800000')
    
    def test_account_summary_low_balance_accounts(self, authenticated_client, user):
        """잔액 부족 계좌 표시"""
        # 잔액 10만원 미만 계좌
        Account.objects.create(
            user=user, name='부족계좌',
            bank_name='은행', account_number='1111',
            balance=Decimal('50000')
        )
        
        url = reverse('businesses:account_summary')
        response = authenticated_client.get(url)
        
        low_balance_accounts = response.context['low_balance_accounts']
        assert len(low_balance_accounts) == 1
        assert low_balance_accounts[0].balance < Decimal('100000')