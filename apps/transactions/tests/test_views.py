from decimal import Decimal
from datetime import datetime

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.models import Category, Transaction, Merchant, MerchantCategory


# Fixtures
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
        balance=Decimal('1000000.00'),  # ✅ 충분한 잔액 설정
        is_active=True
    )


@pytest.fixture
def income_category():
    return Category.objects.create(name='매출', type='income', is_system=True)


@pytest.fixture
def expense_category():
    return Category.objects.create(name='경비', type='expense', is_system=True)


@pytest.fixture
def merchant(test_user):
    return Merchant.objects.create(user=test_user, name='테스트 거래처')


# Transaction views tests
@pytest.mark.django_db
class TestTransactionViews:
    def test_transaction_list_requires_login(self, client):
        """거래 목록은 로그인 필요"""
        response = client.get(reverse('transactions:transaction_list'))
        assert response.status_code == 302  # 로그인 페이지로 리다이렉트

    def test_transaction_list_renders(self, auth_client, test_user, business, account, income_category):
        """거래 목록 페이지 렌더링"""
        Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=income_category, tx_type='IN', amount=Decimal('10000'),
            occurred_at=timezone.now(), merchant_name='고객'
        )

        response = auth_client.get(reverse('transactions:transaction_list'))
        
        assert response.status_code == 200
        assert 'page_obj' in response.context

    def test_transaction_list_filters_and_pagination(self, auth_client, test_user, business, account, income_category, expense_category):
        """거래 목록 필터링 및 페이지네이션"""
        base_time = timezone.now().replace(month=1)

        # 수입 거래 25건
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
        
        # 지출 거래 1건
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

        # 수입 필터링
        response = auth_client.get(reverse('transactions:transaction_list'), {'tx_type': 'IN'})

        assert response.status_code == 200
        assert response.context['querystring'] == 'tx_type=IN'
        assert response.context['page_obj'].paginator.num_pages >= 2
        assert b'?page=2&tx_type=IN' in response.content
        assert all(tx.tx_type == 'IN' for tx in response.context['page_obj'])

    def test_transaction_create_and_update(self, auth_client, test_user, business, account, expense_category):
        """거래 생성 및 수정"""
        create_url = reverse('transactions:transaction_create')
        occurred_at = timezone.now().strftime('%Y-%m-%dT%H:%M')
        

        # 생성
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

        # 수정
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

    def test_transaction_delete(self, auth_client, test_user, business, account, income_category):
        """거래 삭제"""
        tx = Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=income_category, tx_type='IN', amount=Decimal('10000'),
            occurred_at=timezone.now(), merchant_name='고객'
        )

        delete_url = reverse('transactions:transaction_delete', kwargs={'pk': tx.pk})
        response = auth_client.post(delete_url)

        assert response.status_code == 302
        assert not Transaction.active.filter(pk=tx.pk).exists()

    def test_transaction_detail(self, auth_client, test_user, business, account, income_category):
        """거래 상세 페이지"""
        tx = Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=income_category, tx_type='IN', amount=Decimal('10000'),
            occurred_at=timezone.now(), merchant_name='고객'
        )

        response = auth_client.get(reverse('transactions:transaction_detail', kwargs={'pk': tx.pk}))
        
        assert response.status_code == 200
        assert response.context['transaction'].id == tx.id


# Monthly summary view tests
@pytest.mark.django_db
class TestMonthlyViews:
    def test_monthly_summary_view_renders(self, auth_client, test_user, business, account, income_category, expense_category):
        """월별 요약 페이지 렌더링"""
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

    def test_monthly_summary_filters_year_and_month(self, auth_client, test_user, business, account, income_category, expense_category):
        """월별 요약 년/월 필터링"""
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
        """월별 요약 차트 렌더링"""
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
        """월별 요약에 연도 목록 포함"""
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


@pytest.mark.django_db
class TestVATReportView:
    def test_vat_report_year_dropdown(self, auth_client, test_user, business, account, income_category):
        """부가세 신고 페이지 연도 드롭다운"""
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


@pytest.mark.django_db
class TestCategoryViews:
    def test_category_list(self, auth_client, test_user, income_category):
        """카테고리 목록"""
        # 사용자 카테고리 생성
        Category.objects.create(user=test_user, name='내카테고리', type='income')

        response = auth_client.get(reverse('transactions:category_list'))

        assert response.status_code == 200
        assert 'categories' in response.context

    def test_category_create(self, auth_client, test_user):
        """카테고리 생성"""
        response = auth_client.post(reverse('transactions:category_create'), {
            'name': '새카테고리',
            'type': 'income',
            'expense_type': '',
        })

        assert response.status_code == 302
        assert Category.objects.filter(user=test_user, name='새카테고리').exists()

    def test_category_update(self, auth_client, test_user):
        """카테고리 수정"""
        category = Category.objects.create(user=test_user, name='수정전', type='income')

        response = auth_client.post(
            reverse('transactions:category_update', kwargs={'pk': category.pk}),
            {
                'name': '수정후',
                'type': 'income',
                'expense_type': '',
            }
        )

        assert response.status_code == 302
        category.refresh_from_db()
        assert category.name == '수정후'

    def test_category_delete_with_transactions(self, auth_client, test_user, business, account):
        """거래가 있는 카테고리 삭제 불가"""
        category = Category.objects.create(user=test_user, name='삭제불가', type='income')
        
        # 카테고리를 사용하는 거래 생성
        Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=category, tx_type='IN', amount=Decimal('10000'),
            occurred_at=timezone.now(), merchant_name='고객'
        )

        response = auth_client.post(
            reverse('transactions:category_delete', kwargs={'pk': category.pk})
        )

        # 삭제되지 않음
        assert Category.objects.filter(pk=category.pk).exists()

    def test_system_category_cannot_be_deleted(self, auth_client, income_category):
        """시스템 카테고리 삭제 불가"""
        response = auth_client.post(
            reverse('transactions:category_delete', kwargs={'pk': income_category.pk})
        )

        assert income_category.is_system
        assert Category.objects.filter(pk=income_category.pk).exists()

    def test_category_statistics(self, auth_client, test_user, business, account, expense_category):
        """카테고리별 통계"""
        Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=expense_category, tx_type='OUT', amount=Decimal('10000'),
            occurred_at=timezone.now(), merchant_name='업체'
        )

        response = auth_client.get(reverse('transactions:category_statistics'))

        assert response.status_code == 200
        assert 'category_list' in response.context
        assert 'total_amount' in response.context


@pytest.mark.django_db
class TestMerchantViews:
    def test_merchant_list(self, auth_client, test_user, merchant):
        """거래처 목록"""
        response = auth_client.get(reverse('transactions:merchant_list'))

        assert response.status_code == 200
        assert 'page_obj' in response.context

    def test_merchant_create(self, auth_client, test_user):
        """거래처 생성"""
        response = auth_client.post(reverse('transactions:merchant_create'), {
            'name': '새거래처',
            'business_number': '123-45-67890',
            'contact': '010-1234-5678',
        })

        assert response.status_code == 302
        assert Merchant.objects.filter(user=test_user, name='새거래처').exists()

    def test_merchant_update(self, auth_client, test_user, merchant):
        """거래처 수정"""
        response = auth_client.post(
            reverse('transactions:merchant_update', kwargs={'pk': merchant.pk}),
            {
                'name': '수정된거래처',
            }
        )

        assert response.status_code == 302
        merchant.refresh_from_db()
        assert merchant.name == '수정된거래처'

    def test_merchant_delete(self, auth_client, test_user, merchant):
        """거래처 삭제 (소프트 삭제)"""
        response = auth_client.post(
            reverse('transactions:merchant_delete', kwargs={'pk': merchant.pk})
        )

        assert response.status_code == 302
        merchant.refresh_from_db()
        assert merchant.is_active is False

    def test_merchant_detail(self, auth_client, test_user, merchant):
        """거래처 상세"""
        response = auth_client.get(
            reverse('transactions:merchant_detail', kwargs={'pk': merchant.pk})
        )

        assert response.status_code == 200
        assert response.context['merchant'].id == merchant.id