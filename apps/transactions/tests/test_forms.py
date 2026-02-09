from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.forms import TransactionForm
from apps.transactions.models import Category


@pytest.fixture
def test_user(db):
    return User.objects.create_user(username='tester', password='pass')


@pytest.fixture
def business(test_user):
    return Business.objects.create(user=test_user, name='Test Biz')


@pytest.fixture
def account(test_user, business):
    return Account.objects.create(
        user=test_user,
        business=business,
        name='Main Account',
        bank_name='Test Bank',
        account_number='123-456',
    )


@pytest.fixture
def income_category():
    return Category.objects.create(name='매출', type='income', is_system=True)


@pytest.mark.django_db
class TestTransactionForm:
    def test_requires_merchant_or_name(self, test_user, business, account, income_category):
        data = {
            'business': business.id,
            'account': account.id,
            'merchant': '',
            'merchant_name': '',
            'category': income_category.id,
            'tx_type': 'IN',
            'tax_type': 'taxable',
            'is_business': True,
            'amount': '11000.00',
            'vat_amount': '',
            'occurred_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'memo': '',
        }

        form = TransactionForm(data=data, user=test_user)

        assert not form.is_valid()
        assert '거래처를 선택하거나 직접 입력하세요.' in form.non_field_errors()

    def test_vat_auto_calculation(self, test_user, business, account, income_category):
        data = {
            'business': business.id,
            'account': account.id,
            'merchant': '',
            'merchant_name': '테스트 거래처',
            'category': income_category.id,
            'tx_type': 'IN',
            'tax_type': 'taxable',
            'is_business': True,
            'amount': '11000.00',
            'vat_amount': '',
            'occurred_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'memo': '',
        }

        form = TransactionForm(data=data, user=test_user)

        assert form.is_valid()
        assert form.cleaned_data['vat_amount'] == Decimal('1100.00')
