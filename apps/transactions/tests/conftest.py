"""
transactions 앱 테스트용 공통 fixture
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.models import Category, Merchant, MerchantCategory


@pytest.fixture
def test_user(db):
    """테스트용 사용자"""
    return User.objects.create_user(username='tester', password='pass')


@pytest.fixture
def other_user(db):
    """다른 사용자 (권한 테스트용)"""
    return User.objects.create_user(username='other', password='pass')


@pytest.fixture
def business(test_user):
    """테스트용 사업장"""
    return Business.objects.create(user=test_user, name='Test Biz')


@pytest.fixture
def account(test_user, business):
    """테스트용 계좌"""
    return Account.objects.create(
        user=test_user,
        business=business,
        name='Main Account',
        bank_name='Test Bank',
        account_number='123-456',
        balance=Decimal('0.00'),
    )


@pytest.fixture
def income_category():
    """수입 카테고리 (시스템)"""
    return Category.objects.create(name='매출', type='income', is_system=True)


@pytest.fixture
def expense_category():
    """지출 카테고리 (시스템)"""
    return Category.objects.create(name='경비', type='expense', is_system=True)


@pytest.fixture
def merchant_category():
    """거래처 카테고리 (공용)"""
    return MerchantCategory.objects.create(name='도매처', user=None)


@pytest.fixture
def merchant(test_user):
    """테스트용 거래처"""
    return Merchant.objects.create(
        user=test_user,
        name='테스트 거래처',
        business_number='123-45-67890'
    )


@pytest.fixture
def auth_client(client, test_user):
    """로그인된 클라이언트"""
    client.login(username='tester', password='pass')
    return client