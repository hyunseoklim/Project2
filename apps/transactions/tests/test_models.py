from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.models import Category, Transaction, Merchant, MerchantCategory


# Fixtures
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
        balance=Decimal('0.00'),
    )


@pytest.fixture
def income_category():
    return Category.objects.create(name='매출', type='income', is_system=True)


@pytest.fixture
def expense_category():
    return Category.objects.create(name='경비', type='expense', is_system=True)


# Category model tests
@pytest.mark.django_db
class TestCategoryModel:
    def test_category_str_method(self):
        """카테고리 문자열 표현"""
        category = Category.objects.create(name='급여', type='expense', is_system=True)
        assert str(category) == '[지출] 급여'

    def test_income_category_cannot_have_expense_type(self):
        """수입 카테고리는 지출 세부 유형을 가질 수 없음"""
        category = Category(
            name='매출',
            type='income',
            expense_type='salary',  # 잘못된 값
            is_system=True
        )
        
        with pytest.raises(ValidationError) as exc_info:
            category.full_clean()
        
        assert 'expense_type' in exc_info.value.message_dict

    def test_expense_category_cannot_have_income_type(self):
        """지출 카테고리는 수입 세부 유형을 가질 수 없음"""
        category = Category(
            name='경비',
            type='expense',
            income_type='sales',  # 잘못된 값
            is_system=True
        )
        
        with pytest.raises(ValidationError) as exc_info:
            category.full_clean()
        
        assert 'income_type' in exc_info.value.message_dict

    def test_user_category_unique_constraint(self, test_user):
        """사용자별 카테고리 이름 중복 불가"""
        Category.objects.create(user=test_user, name='내카테고리', type='income')
        
        # 같은 이름으로 다시 생성 시도
        with pytest.raises(Exception):  # IntegrityError
            Category.objects.create(user=test_user, name='내카테고리', type='income')

    def test_system_category_unique_constraint(self):
        """시스템 카테고리 이름 중복 불가"""
        Category.objects.create(name='매출', type='income', is_system=True)
        
        with pytest.raises(Exception):  # IntegrityError
            Category.objects.create(name='매출', type='income', is_system=True)


# Merchant model tests
@pytest.mark.django_db
class TestMerchantModel:
    def test_merchant_str_method(self, test_user):
        """거래처 문자열 표현"""
        merchant = Merchant.objects.create(user=test_user, name='네이버')
        assert str(merchant) == '네이버'

    def test_get_masked_business_number(self, test_user):
        """사업자번호 마스킹"""
        merchant = Merchant.objects.create(
            user=test_user,
            name='테스트',
            business_number='123-45-67890'
        )
        
        masked = merchant.get_masked_business_number()
        assert masked == '123-**-***90'

    def test_get_masked_business_number_empty(self, test_user):
        """사업자번호 없을 때 마스킹"""
        merchant = Merchant.objects.create(user=test_user, name='테스트')
        assert merchant.get_masked_business_number() == '-'

    def test_unique_active_merchant_name(self, test_user):
        """활성 거래처 이름은 사용자별로 중복 불가"""
        Merchant.objects.create(user=test_user, name='중복테스트', is_active=True)
        
        with pytest.raises(Exception):  # IntegrityError
            Merchant.objects.create(user=test_user, name='중복테스트', is_active=True)

    def test_soft_delete_allows_same_name(self, test_user):
        """삭제된 거래처는 같은 이름 재사용 가능"""
        merchant1 = Merchant.objects.create(user=test_user, name='재사용테스트')
        merchant1.is_active = False
        merchant1.save()
        
        # 같은 이름으로 재생성 가능
        merchant2 = Merchant.objects.create(user=test_user, name='재사용테스트')
        assert merchant2.is_active is True


# Transaction model tests
@pytest.mark.django_db
class TestTransactionModel:
    def test_vat_auto_calculated_on_save(self, test_user, business, account, income_category):
        """저장 시 부가세 자동 계산"""
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

    def test_account_balance_updated_on_income(self, test_user, business, account, income_category):
        """수입 거래 시 계좌 잔액 증가"""
        initial_balance = account.balance
        
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('11000.00'),
            occurred_at=timezone.now(),
            merchant_name='고객',
        )

        account.refresh_from_db()
        assert account.balance == initial_balance + Decimal('11000.00')

    def test_account_balance_updated_on_expense(self, test_user, business, account, expense_category):
        """지출 거래 시 계좌 잔액 감소"""
        # 초기 잔액 설정
        account.balance = Decimal('50000.00')
        account.save()
        
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('5500.00'),
            occurred_at=timezone.now(),
            merchant_name='업체',
        )

        account.refresh_from_db()
        assert account.balance == Decimal('44500.00')

    def test_tax_free_rejects_vat_amount(self, test_user, business, account, income_category):
        """면세 거래는 부가세 금액 거부"""
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

    def test_transaction_requires_merchant_or_name(self, test_user, business, account, income_category):
        """거래처 또는 거래처명 필수"""
        tx = Transaction(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('10000.00'),
            occurred_at=timezone.now(),
            merchant=None,
            merchant_name='',
        )

        with pytest.raises(ValidationError) as exc_info:
            tx.full_clean()
        
        assert 'merchant' in exc_info.value.message_dict

    def test_income_transaction_requires_income_category(self, test_user, business, account, expense_category):
        """수입 거래는 수입 카테고리 필수"""
        tx = Transaction(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,  # 잘못된 카테고리
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('10000.00'),
            occurred_at=timezone.now(),
            merchant_name='고객',
        )

        with pytest.raises(ValidationError) as exc_info:
            tx.full_clean()
        
        assert 'category' in exc_info.value.message_dict

    def test_expense_transaction_requires_expense_category(self, test_user, business, account, income_category):
        """지출 거래는 지출 카테고리 필수"""
        tx = Transaction(
            user=test_user,
            business=business,
            account=account,
            category=income_category,  # 잘못된 카테고리
            tx_type='OUT',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('10000.00'),
            occurred_at=timezone.now(),
            merchant_name='업체',
        )

        with pytest.raises(ValidationError) as exc_info:
            tx.full_clean()
        
        assert 'category' in exc_info.value.message_dict

    def test_transaction_str_method(self, test_user, business, account, income_category):
        """거래 문자열 표현"""
        tx = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('11000.00'),
            occurred_at=timezone.now(),
            merchant_name='고객',
        )
        
        assert '수입' in str(tx)
        assert '11,000원' in str(tx)

    def test_get_merchant_display(self, test_user, business, account, income_category):
        """거래처 표시명 반환"""
        # merchant_name 사용
        tx1 = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000.00'),
            occurred_at=timezone.now(),
            merchant_name='직접입력',
        )
        assert tx1.get_merchant_display() == '직접입력'

        # merchant 객체 사용
        merchant = Merchant.objects.create(user=test_user, name='등록거래처')
        tx2 = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000.00'),
            occurred_at=timezone.now(),
            merchant=merchant,
        )
        assert tx2.get_merchant_display() == '등록거래처'

    def test_transaction_update_balance(self, test_user, business, account, income_category):
        """거래 수정 시 잔액 재계산"""
        # 초기 잔액
        account.balance = Decimal('100000.00')
        account.save()
        
        # 거래 생성
        tx = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000.00'),
            occurred_at=timezone.now(),
            merchant_name='고객',
        )
        
        account.refresh_from_db()
        assert account.balance == Decimal('110000.00')
        
        # 금액 수정
        tx.amount = Decimal('20000.00')
        tx.save()
        
        account.refresh_from_db()
        assert account.balance == Decimal('120000.00')

    def test_transaction_delete_restores_balance(self, test_user, business, account, income_category):
        """거래 삭제 시 잔액 복구"""
        account.balance = Decimal('100000.00')
        account.save()
        
        tx = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000.00'),
            occurred_at=timezone.now(),
            merchant_name='고객',
        )
        
        account.refresh_from_db()
        assert account.balance == Decimal('110000.00')
        
        # 삭제
        tx.delete()
        
        account.refresh_from_db()
        assert account.balance == Decimal('100000.00')


@pytest.mark.django_db
class TestTransactionQuerySet:
    def test_income_queryset(self, test_user, business, account, income_category):
        """수입 거래 필터링"""
        Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=income_category, tx_type='IN', amount=Decimal('10000'),
            occurred_at=timezone.now(), merchant_name='고객'
        )
        
        assert Transaction.active.income().count() == 1

    def test_expense_queryset(self, test_user, business, account, expense_category):
        """지출 거래 필터링"""
        Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=expense_category, tx_type='OUT', amount=Decimal('5000'),
            occurred_at=timezone.now(), merchant_name='업체'
        )
        
        assert Transaction.active.expense().count() == 1

    def test_business_only_queryset(self, test_user, business, account, income_category):
        """사업용 거래만 필터링"""
        Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=income_category, tx_type='IN', amount=Decimal('10000'),
            is_business=True, occurred_at=timezone.now(), merchant_name='고객'
        )
        Transaction.objects.create(
            user=test_user, business=business, account=account,
            category=income_category, tx_type='IN', amount=Decimal('5000'),
            is_business=False, occurred_at=timezone.now(), merchant_name='개인'
        )
        
        assert Transaction.active.business_only().count() == 1