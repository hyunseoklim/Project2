# =============================================================================
# conftest.py - pytest 공통 설정 및 Fixtures
# =============================================================================

import pytest
from django.conf import settings
from django.test import Client
from django.contrib.auth.models import User
from decimal import Decimal

from apps.businesses.models import Business, Account


# =============================================================================
# pytest-django 설정
# =============================================================================

@pytest.fixture(scope='session')
def django_db_setup():
    """데이터베이스 설정"""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': True,
    }


# =============================================================================
# 공통 Fixtures
# =============================================================================

@pytest.fixture
def client():
    """테스트 클라이언트"""
    return Client()


@pytest.fixture
def user(db):
    """기본 테스트 사용자"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123',
        first_name='테스트',
        last_name='사용자'
    )


@pytest.fixture
def other_user(db):
    """다른 테스트 사용자"""
    return User.objects.create_user(
        username='otheruser',
        email='other@example.com',
        password='testpass123'
    )


@pytest.fixture
def superuser(db):
    """관리자 사용자"""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def authenticated_client(client, user):
    """로그인된 클라이언트"""
    client.login(username='testuser', password='testpass123')
    client.user = user  # 편의를 위해 user 속성 추가
    return client


@pytest.fixture
def admin_client(client, superuser):
    """관리자로 로그인된 클라이언트"""
    client.login(username='admin', password='adminpass123')
    client.user = superuser
    return client


# =============================================================================
# Business Fixtures
# =============================================================================

@pytest.fixture
def business(db, user):
    """기본 테스트 사업장 (본점)"""
    return Business.objects.create(
        user=user,
        name='강남점',
        location='서울시 강남구 테헤란로 123',
        business_type='소매업',
        branch_type='main',
        registration_number='123-45-67890'
    )


@pytest.fixture
def branch_business(db, user):
    """지점 사업장"""
    return Business.objects.create(
        user=user,
        name='강남점 지점1',
        location='서울시 강남구 역삼동 456',
        business_type='소매업',
        branch_type='branch'
    )


@pytest.fixture
def deleted_business(db, user):
    """삭제된 사업장"""
    business = Business.objects.create(
        user=user,
        name='삭제된사업장'
    )
    business.soft_delete()
    return business


@pytest.fixture
def multiple_businesses(db, user):
    """여러 사업장 (페이지네이션 테스트용)"""
    businesses = []
    for i in range(30):
        business = Business.objects.create(
            user=user,
            name=f'사업장{i:02d}',
            location=f'위치{i}',
            business_type='소매업' if i % 2 == 0 else '제조업',
            branch_type='main' if i % 3 == 0 else 'branch'
        )
        businesses.append(business)
    return businesses


# =============================================================================
# Account Fixtures
# =============================================================================

@pytest.fixture
def account(db, user, business):
    """기본 테스트 계좌 (사업용)"""
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
def personal_account(db, user):
    """개인용 계좌"""
    return Account.objects.create(
        user=user,
        business=None,
        name='신한은행 개인통장',
        bank_name='신한은행',
        account_number='9876-5432-1098-7654',
        account_type='personal',
        balance=Decimal('500000.00')
    )


@pytest.fixture
def deleted_account(db, user, business):
    """삭제된 계좌"""
    account = Account.objects.create(
        user=user,
        business=business,
        name='삭제된계좌',
        bank_name='은행',
        account_number='0000-0000-0000'
    )
    account.soft_delete()
    return account


@pytest.fixture
def low_balance_account(db, user):
    """잔액 부족 계좌 (10만원 미만)"""
    return Account.objects.create(
        user=user,
        name='잔액부족계좌',
        bank_name='은행',
        account_number='1111-1111-1111',
        balance=Decimal('50000.00')
    )


@pytest.fixture
def multiple_accounts(db, user, business):
    """여러 계좌 (페이지네이션 및 필터링 테스트용)"""
    accounts = []
    
    for i in range(30):
        account = Account.objects.create(
            user=user,
            business=business if i % 2 == 0 else None,
            name=f'계좌{i:02d}',
            bank_name='국민은행' if i % 3 == 0 else '신한은행',
            account_number=f'{i:04d}-5678-9012-3456',
            account_type='business' if i % 2 == 0 else 'personal',
            balance=Decimal('100000.00') * (i + 1)
        )
        accounts.append(account)
    
    return accounts


# =============================================================================
# 데이터 조합 Fixtures
# =============================================================================

@pytest.fixture
def complete_business_setup(db, user):
    """완전한 사업장 + 계좌 설정"""
    # 본점
    main_business = Business.objects.create(
        user=user,
        name='본점',
        branch_type='main',
        business_type='소매업'
    )
    
    # 지점
    branch = Business.objects.create(
        user=user,
        name='지점1',
        branch_type='branch',
        business_type='소매업'
    )
    
    # 본점 계좌들
    main_account1 = Account.objects.create(
        user=user,
        business=main_business,
        name='본점 주거래',
        bank_name='국민은행',
        account_number='1111-1111-1111',
        account_type='business',
        balance=Decimal('5000000')
    )
    
    main_account2 = Account.objects.create(
        user=user,
        business=main_business,
        name='본점 세금계좌',
        bank_name='신한은행',
        account_number='2222-2222-2222',
        account_type='business',
        balance=Decimal('2000000')
    )
    
    # 지점 계좌
    branch_account = Account.objects.create(
        user=user,
        business=branch,
        name='지점1 운영',
        bank_name='우리은행',
        account_number='3333-3333-3333',
        account_type='business',
        balance=Decimal('1000000')
    )
    
    # 개인 계좌
    personal = Account.objects.create(
        user=user,
        business=None,
        name='개인통장',
        bank_name='하나은행',
        account_number='4444-4444-4444',
        account_type='personal',
        balance=Decimal('3000000')
    )
    
    return {
        'main_business': main_business,
        'branch': branch,
        'main_account1': main_account1,
        'main_account2': main_account2,
        'branch_account': branch_account,
        'personal': personal
    }


# =============================================================================
# 테스트 유틸리티 Fixtures
# =============================================================================

@pytest.fixture
def assert_message_contains():
    """메시지 검증 헬퍼"""
    def _assert(response, text):
        from django.contrib.messages import get_messages
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        assert any(text in msg for msg in messages), \
            f"Expected message containing '{text}', got: {messages}"
    return _assert


@pytest.fixture
def create_test_user(db):
    """테스트 사용자 생성 팩토리"""
    def _create(username='testuser', **kwargs):
        defaults = {
            'email': f'{username}@example.com',
            'password': 'testpass123'
        }
        defaults.update(kwargs)
        return User.objects.create_user(username=username, **defaults)
    return _create


@pytest.fixture
def create_test_business(db):
    """테스트 사업장 생성 팩토리"""
    def _create(user, name='테스트사업장', **kwargs):
        defaults = {
            'branch_type': 'main',
            'business_type': '소매업'
        }
        defaults.update(kwargs)
        return Business.objects.create(user=user, name=name, **defaults)
    return _create


@pytest.fixture
def create_test_account(db):
    """테스트 계좌 생성 팩토리"""
    def _create(user, name='테스트계좌', **kwargs):
        defaults = {
            'bank_name': '테스트은행',
            'account_number': '1234-5678-9012',
            'account_type': 'business',
            'balance': Decimal('100000')
        }
        defaults.update(kwargs)
        return Account.objects.create(user=user, name=name, **defaults)
    return _create


# =============================================================================
# pytest 마커 정의
# =============================================================================

def pytest_configure(config):
    """pytest 설정"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


# =============================================================================
# 자동 사용 Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """모든 테스트에 DB 접근 허용"""
    pass


@pytest.fixture(autouse=True)
def reset_sequences(db):
    """각 테스트 후 시퀀스 리셋 (PK 초기화)"""
    pass