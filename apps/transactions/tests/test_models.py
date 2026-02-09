from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.models import Category, Transaction


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
class TestTransactionModel:
    def test_vat_auto_calculated_on_save(self, test_user, business, account, income_category):
        tx = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('11000.00'),
            vat_amount=None,
            occurred_at=timezone.now(),
            merchant_name='고객',
        )

        tx.refresh_from_db()

        assert tx.vat_amount == Decimal('1100.00')
        assert tx.supply_value == Decimal('9900.00')
        assert tx.total_amount == Decimal('11000.00')

        account.refresh_from_db()
        assert account.balance == Decimal('11000.00')

    def test_tax_free_rejects_vat_amount(self, test_user, business, account, income_category):
        tx = Transaction(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='tax_free',
            is_business=True,
            amount=Decimal('10000.00'),
            vat_amount=Decimal('1000.00'),
            occurred_at=timezone.now(),
            merchant_name='고객',
        )

        with pytest.raises(ValidationError):
            tx.full_clean()
