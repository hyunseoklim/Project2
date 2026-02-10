from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.forms import TransactionForm, MerchantForm, CategoryForm
from apps.transactions.models import Category, Merchant, MerchantCategory


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


@pytest.fixture
def expense_category():
    return Category.objects.create(name='경비', type='expense', is_system=True)


@pytest.fixture
def merchant_category():
    return MerchantCategory.objects.create(name='도매처', user=None)


@pytest.mark.django_db
class TestTransactionForm:
    def test_requires_merchant_or_name(self, test_user, business, account, income_category):
        """거래처 또는 거래처명 필수 검증"""
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
        """부가세 자동 계산 검증 (과세 거래)"""
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

    def test_no_vat_for_tax_free(self, test_user, business, account, income_category):
        """면세 거래는 부가세 자동 계산 안됨"""
        data = {
            'business': business.id,
            'account': account.id,
            'merchant_name': '면세 거래처',
            'category': income_category.id,
            'tx_type': 'IN',
            'tax_type': 'tax_free',
            'is_business': True,
            'amount': '10000.00',
            'vat_amount': '',
            'occurred_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'memo': '',
        }

        form = TransactionForm(data=data, user=test_user)
        assert form.is_valid()
        assert form.cleaned_data['vat_amount'] is None or form.cleaned_data['vat_amount'] == Decimal('0')

    def test_queryset_filters_by_user(self, test_user, business, account):
        """폼의 queryset이 사용자별로 필터링되는지 검증"""
        form = TransactionForm(user=test_user)
        
        assert form.fields['business'].queryset.filter(user=test_user).exists()
        assert form.fields['account'].queryset.filter(user=test_user).exists()
        assert form.fields['merchant'].queryset.filter(user=test_user).count() == 0  # 아직 거래처 없음

    def test_merchant_field_optional(self, test_user, business, account, income_category):
        """거래처 선택 필드는 선택사항"""
        data = {
            'business': business.id,
            'account': account.id,
            'merchant_name': '직접 입력 거래처',
            'category': income_category.id,
            'tx_type': 'IN',
            'tax_type': 'taxable',
            'is_business': True,
            'amount': '10000.00',
            'occurred_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        }

        form = TransactionForm(data=data, user=test_user)
        assert form.is_valid()

    def test_vat_amount_manual_input(self, test_user, business, account, income_category):
        """수동으로 입력한 부가세는 유지됨"""
        data = {
            'business': business.id,
            'account': account.id,
            'merchant_name': '테스트',
            'category': income_category.id,
            'tx_type': 'IN',
            'tax_type': 'taxable',
            'is_business': True,
            'amount': '11000.00',
            'vat_amount': '500.00',  # 수동 입력
            'occurred_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        }

        form = TransactionForm(data=data, user=test_user)
        assert form.is_valid()
        assert form.cleaned_data['vat_amount'] == Decimal('500.00')


@pytest.mark.django_db
class TestMerchantForm:
    def test_valid_merchant_creation(self, test_user, merchant_category):
        """유효한 거래처 생성"""
        data = {
            'name': '네이버',
            'business_number': '123-45-67890',
            'contact': '010-1234-5678',
            'category': merchant_category.id,
            'memo': '테스트 메모',
        }

        form = MerchantForm(data=data, user=test_user)
        assert form.is_valid()

    def test_business_number_validation_too_short(self, test_user):
        """사업자등록번호 유효성 검증 - 9자리"""
        data = {
            'name': '테스트',
            'business_number': '123456789',
        }
        form = MerchantForm(data=data, user=test_user)
        assert not form.is_valid()
        assert 'business_number' in form.errors

    def test_business_number_validation_too_long(self, test_user):
        """사업자등록번호 유효성 검증 - 11자리"""
        data = {
            'name': '테스트',
            'business_number': '12345678901',
        }
        form = MerchantForm(data=data, user=test_user)
        assert not form.is_valid()
        assert 'business_number' in form.errors

    def test_business_number_validation_non_digit(self, test_user):
        """사업자등록번호 유효성 검증 - 숫자가 아닌 문자"""
        data = {
            'name': '테스트',
            'business_number': '123-45-abcde',
        }
        form = MerchantForm(data=data, user=test_user)
        assert not form.is_valid()
        assert 'business_number' in form.errors

    def test_business_number_formatting(self, test_user):
        """사업자등록번호 자동 포맷팅"""
        data = {
            'name': '테스트',
            'business_number': '1234567890',
        }
        form = MerchantForm(data=data, user=test_user)
        
        if form.is_valid():
            assert form.cleaned_data['business_number'] == '123-45-67890'

    def test_business_number_formatting_with_hyphens(self, test_user):
        """사업자등록번호 하이픈 포함 입력도 처리"""
        data = {
            'name': '테스트',
            'business_number': '123-45-67890',
        }
        form = MerchantForm(data=data, user=test_user)
        
        if form.is_valid():
            assert form.cleaned_data['business_number'] == '123-45-67890'

    def test_optional_fields(self, test_user):
        """선택 필드 검증 - 이름만으로도 생성 가능"""
        data = {
            'name': '최소 정보 거래처',
        }
        form = MerchantForm(data=data, user=test_user)
        assert form.is_valid()

    def test_merchant_category_queryset_filtering(self, test_user):
        """거래처 카테고리 queryset 필터링"""
        # 공용 카테고리
        global_cat = MerchantCategory.objects.create(name='공용카테고리', user=None)
        # 사용자 카테고리
        user_cat = MerchantCategory.objects.create(name='내카테고리', user=test_user)
        # 다른 사용자 카테고리
        other_user = User.objects.create_user(username='other', password='pass')
        other_cat = MerchantCategory.objects.create(name='다른카테고리', user=other_user)

        form = MerchantForm(user=test_user)
        category_ids = list(form.fields['category'].queryset.values_list('id', flat=True))
        
        assert global_cat.id in category_ids
        assert user_cat.id in category_ids
        assert other_cat.id not in category_ids


@pytest.mark.django_db
class TestCategoryForm:
    def test_income_category_creation(self):
        """수입 카테고리 생성"""
        data = {
            'name': '컨설팅 수입',
            'type': 'income',
            'expense_type': '',
        }
        form = CategoryForm(data=data)
        assert form.is_valid()

    def test_expense_category_creation(self):
        """지출 카테고리 생성"""
        data = {
            'name': '사무용품',
            'type': 'expense',
            'expense_type': 'supplies',
        }
        form = CategoryForm(data=data)
        assert form.is_valid()

    def test_expense_type_cleared_for_income(self):
        """수입 카테고리에서 expense_type 자동 제거"""
        data = {
            'name': '서비스 수입',
            'type': 'income',
            'expense_type': 'salary',  # 잘못된 값
        }
        form = CategoryForm(data=data)
        
        if form.is_valid():
            assert form.cleaned_data['expense_type'] is None

    def test_expense_type_optional_for_expense(self):
        """지출 카테고리에서 expense_type은 선택사항"""
        data = {
            'name': '기타 지출',
            'type': 'expense',
            'expense_type': '',
        }
        form = CategoryForm(data=data)
        assert form.is_valid()

    def test_type_field_required(self):
        """카테고리 타입은 필수"""
        data = {
            'name': '테스트 카테고리',
            'type': '',
        }
        form = CategoryForm(data=data)
        assert not form.is_valid()
        assert 'type' in form.errors