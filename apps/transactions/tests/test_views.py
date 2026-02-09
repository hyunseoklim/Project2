from decimal import Decimal
from datetime import datetime

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.models import Category, Transaction


@pytest.fixture
def test_user(db):
    return User.objects.create_user(username='tester', password='pass')


@pytest.fixture
def auth_client(client, test_user):
    client.login(username='tester', password='pass')
    return client


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


@pytest.fixture
def expense_category():
    return Category.objects.create(name='경비', type='expense', is_system=True)


@pytest.mark.django_db
class TestTransactionViews:
    def test_monthly_summary_view_renders(self, auth_client, test_user, business, account, income_category, expense_category):
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('11000.00'),
            vat_amount=None,
            occurred_at=timezone.now().replace(month=1),
            merchant_name='고객',
        )
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('5500.00'),
            vat_amount=None,
            occurred_at=timezone.now().replace(month=2),
            merchant_name='업체',
        )

        response = auth_client.get(reverse('transactions:monthly_summary'))

        assert response.status_code == 200
        assert 'rows' in response.context
        assert len(response.context['rows']) == 12

    def test_transaction_list_filters_and_pagination(self, auth_client, test_user, business, account, income_category, expense_category):
        base_time = timezone.now().replace(month=1)

        for idx in range(25):
            Transaction.objects.create(
                user=test_user,
                business=business,
                account=account,
                category=income_category,
                tx_type='IN',
                tax_type='taxable',
                is_business=True,
                amount=Decimal('10000.00') + idx,
                vat_amount=None,
                occurred_at=base_time,
                merchant_name='고객',
            )
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('5000.00'),
            vat_amount=None,
            occurred_at=base_time,
            merchant_name='업체',
        )

        response = auth_client.get(reverse('transactions:transaction_list'), {'tx_type': 'IN'})

        assert response.status_code == 200
        assert response.context['querystring'] == 'tx_type=IN'
        assert response.context['page_obj'].paginator.num_pages >= 2
        assert b'?page=2&tx_type=IN' in response.content
        assert all(tx.tx_type == 'IN' for tx in response.context['page_obj'])

    def test_transaction_create_and_update(self, auth_client, test_user, business, account, expense_category):
        create_url = reverse('transactions:transaction_create')
        occurred_at = timezone.now().strftime('%Y-%m-%dT%H:%M')

        response = auth_client.post(create_url, {
            'business': business.id,
            'account': account.id,
            'merchant': '',
            'merchant_name': '테스트 거래처',
            'category': expense_category.id,
            'tx_type': 'OUT',
            'tax_type': 'taxable',
            'is_business': True,
            'amount': '11000.00',
            'vat_amount': '',
            'occurred_at': occurred_at,
            'memo': '메모',
        })

        assert response.status_code == 302
        tx = Transaction.objects.get(user=test_user, merchant_name='테스트 거래처')

        update_url = reverse('transactions:transaction_update', kwargs={'pk': tx.pk})
        response = auth_client.post(update_url, {
            'business': business.id,
            'account': account.id,
            'merchant': '',
            'merchant_name': '수정 거래처',
            'category': expense_category.id,
            'tx_type': 'OUT',
            'tax_type': 'taxable',
            'is_business': True,
            'amount': '22000.00',
            'vat_amount': '',
            'occurred_at': occurred_at,
            'memo': '메모 수정',
        })

        assert response.status_code == 302
        tx.refresh_from_db()
        assert tx.amount == Decimal('22000.00')
        assert tx.merchant_name == '수정 거래처'

    def test_vat_report_year_dropdown(self, auth_client, test_user, business, account, income_category):
        now = timezone.now()
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('11000.00'),
            vat_amount=None,
            occurred_at=now,
            merchant_name='고객',
        )

        response = auth_client.get(reverse('transactions:vat_report_default'))

        assert response.status_code == 200
        assert 'year_options' in response.context
        assert len(response.context['year_options']) == 5
        assert 'monthly_stats' in response.context
        assert len(response.context['monthly_stats']) == 3

    def test_monthly_summary_filters_year_and_month(self, auth_client, test_user, business, account, income_category, expense_category):
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('12000.00'),
            vat_amount=None,
            occurred_at=timezone.make_aware(datetime(2025, 3, 1, 9, 0, 0)),
            merchant_name='고객',
        )
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('3000.00'),
            vat_amount=None,
            occurred_at=timezone.make_aware(datetime(2025, 3, 15, 9, 0, 0)),
            merchant_name='업체',
        )
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('500.00'),
            vat_amount=None,
            occurred_at=timezone.make_aware(datetime(2024, 2, 1, 9, 0, 0)),
            merchant_name='과거',
        )

        response = auth_client.get(reverse('transactions:monthly_summary'), {'year': 2025, 'month': 3})

        assert response.status_code == 200
        assert response.context['year'] == 2025
        assert response.context['month'] == 3
        assert len(response.context['rows']) == 1
        assert response.context['rows'][0]['month'] == 3
        assert response.context['totals']['income'] == Decimal('12000.00')
        assert response.context['totals']['expense'] == Decimal('3000.00')

    def test_monthly_summary_renders_charts(self, auth_client, test_user, business, account, income_category):
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('8000.00'),
            vat_amount=None,
            occurred_at=timezone.now(),
            merchant_name='고객',
        )

        response = auth_client.get(reverse('transactions:monthly_summary'))

        assert response.status_code == 200
        assert b'id="monthlyLineChart"' in response.content
        assert b'id="monthlyNetChart"' in response.content

    def test_monthly_summary_includes_year_list(self, auth_client, test_user, business, account, income_category):
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('5000.00'),
            vat_amount=None,
            occurred_at=timezone.make_aware(datetime(2023, 5, 1, 9, 0, 0)),
            merchant_name='고객',
        )

        response = auth_client.get(reverse('transactions:monthly_summary'))

        assert response.status_code == 200
        assert response.context['year_list']
        assert 2023 in response.context['year_list']
