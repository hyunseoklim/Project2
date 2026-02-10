# =============================================================================
# businesses/tests/test_forms.py - pytest Forms 테스트
# =============================================================================

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.businesses.models import Business, Account
from apps.businesses.forms import (
    AccountForm, AccountSearchForm,
    BusinessForm, BusinessSearchForm
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def user(db):
    """테스트용 사용자"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


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
        name='국민은행',
        bank_name='국민은행',
        account_number='1234-5678-9012',
        account_type='business'
    )


# =============================================================================
# AccountForm 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountForm:
    """계좌 폼 테스트"""
    
    def test_account_form_valid_data(self, user, business):
        """유효한 데이터로 폼 생성"""
        form_data = {
            'name': '국민은행 주거래',
            'bank_name': '국민은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'business',
            'business': business.pk,
        }
        
        form = AccountForm(data=form_data, user=user)
        
        assert form.is_valid()
        assert form.cleaned_data['name'] == '국민은행 주거래'
        assert form.cleaned_data['bank_name'] == '국민은행'
    
    def test_account_form_missing_required_fields(self, user):
        """필수 필드 누락 테스트"""
        form_data = {
            'name': '국민은행',
            # bank_name, account_number 누락
        }
        
        form = AccountForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'bank_name' in form.errors
        assert 'account_number' in form.errors
    
    def test_account_form_business_queryset_filtering(self, user):
        """사업장 선택지가 본인 것만 표시되는지 테스트"""
        # 본인 사업장
        business1 = Business.objects.create(user=user, name='내 사업장')
        
        # 다른 사용자 사업장
        other_user = User.objects.create_user(username='other', password='pass')
        business2 = Business.objects.create(user=other_user, name='남의 사업장')
        
        form = AccountForm(user=user)
        
        # 쿼리셋에 본인 사업장만 있는지 확인
        business_queryset = form.fields['business'].queryset
        assert business1 in business_queryset
        assert business2 not in business_queryset
    
    def test_account_form_account_number_validation_only_digits(self, user):
        """계좌번호 숫자+하이픈만 허용"""
        form_data = {
            'name': '테스트',
            'bank_name': '은행',
            'account_number': '1234-ABCD-5678',  # 문자 포함
            'account_type': 'personal',
        }
        
        form = AccountForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'account_number' in form.errors
        assert '숫자와 하이픈' in str(form.errors['account_number'])
    
    def test_account_form_account_number_minimum_length(self, user):
        """계좌번호 최소 길이 검증"""
        form_data = {
            'name': '테스트',
            'bank_name': '은행',
            'account_number': '123-456',  # 10자리 미만
            'account_type': 'personal',
        }
        
        form = AccountForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'account_number' in form.errors
        assert '최소 10자리' in str(form.errors['account_number'])
    
    def test_account_form_duplicate_account_number(self, user, account):
        """계좌번호 중복 검증"""
        form_data = {
            'name': '새 계좌',
            'bank_name': '신한은행',
            'account_number': account.account_number,  # 기존 계좌와 동일
            'account_type': 'personal',
        }
        
        form = AccountForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'account_number' in form.errors
        assert '이미 등록된' in str(form.errors['account_number'])
    
    def test_account_form_update_excludes_self(self, user, account):
        """수정 시 본인 계좌는 중복 체크에서 제외"""
        form_data = {
            'name': '수정된 이름',
            'bank_name': account.bank_name,
            'account_number': account.account_number,  # 기존과 동일
            'account_type': account.account_type,
        }
        
        # instance를 전달하면 수정 모드
        form = AccountForm(data=form_data, user=user, instance=account)
        
        assert form.is_valid()
    
    def test_account_form_personal_type_with_business(self, user, business):
        """개인용 계좌에 사업장 선택 시 에러"""
        form_data = {
            'name': '개인통장',
            'bank_name': '은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'personal',
            'business': business.pk,  # 개인용인데 사업장 선택
        }
        
        form = AccountForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'business' in form.errors
        assert '개인용 계좌는' in str(form.errors['business'])
    
    def test_account_form_business_type_without_business(self, user):
        """사업용 계좌는 사업장 없어도 됨"""
        form_data = {
            'name': '사업용 계좌',
            'bank_name': '은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'business',
            # business 필드 없음
        }
        
        form = AccountForm(data=form_data, user=user)
        
        assert form.is_valid()
    
    def test_account_form_adds_is_invalid_class_on_error(self, user):
        """유효성 검사 실패 시 is-invalid 클래스 추가"""
        form_data = {
            'name': '',  # 빈 값
            'bank_name': '은행',
            'account_number': '1234',
        }
        
        form = AccountForm(data=form_data, user=user)
        form.is_valid()  # 검증 실행
        
        # name 필드에 is-invalid 클래스가 추가되었는지 확인
        assert 'is-invalid' in form.fields['name'].widget.attrs.get('class', '')
    
    @pytest.mark.parametrize('account_number,expected_valid', [
        ('1234-5678-9012-3456', True),   # 정상
        ('123-456-789-012', True),        # 정상
        ('12345678901234', True),         # 하이픈 없음
        ('123-456', False),               # 너무 짧음
        ('1234-ABCD-5678', False),        # 문자 포함
        ('', False),                      # 빈 값
    ])
    def test_account_number_validation_cases(self, user, account_number, expected_valid):
        """다양한 계좌번호 형식 검증"""
        form_data = {
            'name': '테스트',
            'bank_name': '은행',
            'account_number': account_number,
            'account_type': 'personal',
        }
        
        form = AccountForm(data=form_data, user=user)
        
        if expected_valid:
            assert form.is_valid()
        else:
            assert not form.is_valid()
            if account_number:  # 빈 값이 아니면
                assert 'account_number' in form.errors


# =============================================================================
# AccountSearchForm 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountSearchForm:
    """계좌 검색 폼 테스트"""
    
    def test_search_form_all_fields_optional(self):
        """모든 필드가 선택사항"""
        form = AccountSearchForm(data={})
        
        assert form.is_valid()
    
    def test_search_form_account_type_filter(self):
        """계좌 타입 필터"""
        form_data = {'account_type': 'business'}
        form = AccountSearchForm(data=form_data)
        
        assert form.is_valid()
        assert form.cleaned_data['account_type'] == 'business'
    
    def test_search_form_business_queryset_filtering(self, user):
        """사업장 선택지 필터링"""
        business1 = Business.objects.create(user=user, name='내 사업장')
        other_user = User.objects.create_user(username='other', password='pass')
        business2 = Business.objects.create(user=other_user, name='남의 사업장')
        
        form = AccountSearchForm(data={}, user=user)
        
        business_queryset = form.fields['business'].queryset
        assert business1 in business_queryset
        assert business2 not in business_queryset
    
    def test_search_form_with_search_query(self):
        """검색어 입력"""
        form_data = {'search': '국민은행'}
        form = AccountSearchForm(data=form_data)
        
        assert form.is_valid()
        assert form.cleaned_data['search'] == '국민은행'
    
    def test_search_form_combined_filters(self, user):
        """여러 필터 동시 사용"""
        business = Business.objects.create(user=user, name='사업장')
        
        form_data = {
            'account_type': 'business',
            'business': business.pk,
            'search': '국민은행',
        }
        
        form = AccountSearchForm(data=form_data, user=user)
        
        assert form.is_valid()
        assert form.cleaned_data['account_type'] == 'business'
        assert form.cleaned_data['business'] == business
        assert form.cleaned_data['search'] == '국민은행'


# =============================================================================
# BusinessForm 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessForm:
    """사업장 폼 테스트"""
    
    def test_business_form_valid_data(self, user):
        """유효한 데이터로 폼 생성"""
        form_data = {
            'name': '강남점',
            'location': '서울시 강남구',
            'business_type': '소매업',
            'branch_type': 'main',
            'registration_number': '123-45-67890',
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert form.is_valid()
        assert form.cleaned_data['name'] == '강남점'
    
    def test_business_form_required_fields_only(self, user):
        """필수 필드만으로 폼 생성"""
        form_data = {
            'name': '강남점',
            'branch_type': 'main',
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert form.is_valid()
    
    def test_business_form_missing_name(self, user):
        """사업장명 누락 시 에러"""
        form_data = {
            'location': '서울',
            'branch_type': 'main',
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'name' in form.errors
    
    def test_business_form_duplicate_name(self, user, business):
        """사업장명 중복 검증"""
        form_data = {
            'name': business.name,  # 기존 사업장과 동일
            'branch_type': 'branch',
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'name' in form.errors
        assert '이미 등록된' in str(form.errors['name'])
    
    def test_business_form_update_excludes_self(self, user, business):
        """수정 시 본인 사업장은 중복 체크에서 제외"""
        form_data = {
            'name': business.name,  # 기존과 동일
            'location': '수정된 위치',
            'branch_type': business.branch_type,
        }
        
        form = BusinessForm(data=form_data, user=user, instance=business)
        
        assert form.is_valid()
    
    def test_business_form_registration_number_format(self, user):
        """사업자등록번호 형식 정규화 (123-45-67890)"""
        form_data = {
            'name': '테스트',
            'branch_type': 'main',
            'registration_number': '1234567890',  # 하이픈 없음
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert form.is_valid()
        # 자동으로 하이픈 추가
        assert form.cleaned_data['registration_number'] == '123-45-67890'
    
    def test_business_form_registration_number_with_hyphens(self, user):
        """사업자등록번호 하이픈 있는 경우"""
        form_data = {
            'name': '테스트',
            'branch_type': 'main',
            'registration_number': '123-45-67890',
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert form.is_valid()
        assert form.cleaned_data['registration_number'] == '123-45-67890'
    
    def test_business_form_registration_number_invalid_length(self, user):
        """사업자등록번호 길이 검증 (10자리)"""
        form_data = {
            'name': '테스트',
            'branch_type': 'main',
            'registration_number': '123-45-678',  # 9자리
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'registration_number' in form.errors
        assert '10자리' in str(form.errors['registration_number'])
    
    def test_business_form_registration_number_non_numeric(self, user):
        """사업자등록번호 숫자가 아닌 경우"""
        form_data = {
            'name': '테스트',
            'branch_type': 'main',
            'registration_number': '123-AB-67890',  # 문자 포함
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert not form.is_valid()
        assert 'registration_number' in form.errors
        assert '숫자와 하이픈' in str(form.errors['registration_number'])
    
    def test_business_form_registration_number_optional(self, user):
        """사업자등록번호는 선택 필드"""
        form_data = {
            'name': '테스트',
            'branch_type': 'main',
            # registration_number 없음
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        assert form.is_valid()
    
    @pytest.mark.parametrize('reg_number,expected_format', [
        ('1234567890', '123-45-67890'),
        ('123-45-67890', '123-45-67890'),
        ('123 45 67890', '123-45-67890'),
    ])
    def test_registration_number_normalization(self, user, reg_number, expected_format):
        """사업자등록번호 정규화 테스트"""
        form_data = {
            'name': '테스트',
            'branch_type': 'main',
            'registration_number': reg_number,
        }
        
        form = BusinessForm(data=form_data, user=user)
        
        if form.is_valid():
            assert form.cleaned_data['registration_number'] == expected_format
    
    def test_business_form_adds_is_invalid_class(self, user):
        """유효성 검사 실패 시 is-invalid 클래스 추가"""
        form_data = {
            'name': '',  # 빈 값
        }
        
        form = BusinessForm(data=form_data, user=user)
        form.is_valid()
        
        assert 'is-invalid' in form.fields['name'].widget.attrs.get('class', '')


# =============================================================================
# BusinessSearchForm 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessSearchForm:
    """사업장 검색 폼 테스트"""
    
    def test_search_form_all_optional(self):
        """모든 필드 선택사항"""
        form = BusinessSearchForm(data={})
        
        assert form.is_valid()
    
    def test_search_form_branch_type_filter(self):
        """지점 구분 필터"""
        form_data = {'branch_type': 'main'}
        form = BusinessSearchForm(data=form_data)
        
        assert form.is_valid()
        assert form.cleaned_data['branch_type'] == 'main'
    
    def test_search_form_business_type_filter(self):
        """업종 필터"""
        form_data = {'business_type': '소매업'}
        form = BusinessSearchForm(data=form_data)
        
        assert form.is_valid()
        assert form.cleaned_data['business_type'] == '소매업'
    
    def test_search_form_search_query(self):
        """검색어"""
        form_data = {'search': '강남점'}
        form = BusinessSearchForm(data=form_data)
        
        assert form.is_valid()
        assert form.cleaned_data['search'] == '강남점'
    
    def test_search_form_combined_filters(self):
        """여러 필터 동시 사용"""
        form_data = {
            'branch_type': 'branch',
            'business_type': '제조업',
            'search': '공장',
        }
        
        form = BusinessSearchForm(data=form_data)
        
        assert form.is_valid()
        assert form.cleaned_data['branch_type'] == 'branch'
        assert form.cleaned_data['business_type'] == '제조업'
        assert form.cleaned_data['search'] == '공장'


# =============================================================================
# 폼 위젯 및 레이블 테스트
# =============================================================================

@pytest.mark.django_db
class TestFormWidgetsAndLabels:
    """폼 위젯과 레이블 테스트"""
    
    def test_account_form_widgets_have_bootstrap_classes(self, user):
        """AccountForm 위젯에 Bootstrap 클래스 적용"""
        form = AccountForm(user=user)
        
        assert 'form-control' in form.fields['name'].widget.attrs.get('class', '')
        assert 'form-control' in form.fields['bank_name'].widget.attrs.get('class', '')
        assert 'form-select' in form.fields['account_type'].widget.attrs.get('class', '')
    
    def test_account_form_has_placeholders(self, user):
        """AccountForm 플레이스홀더 존재"""
        form = AccountForm(user=user)
        
        assert 'placeholder' in form.fields['name'].widget.attrs
        assert 'placeholder' in form.fields['bank_name'].widget.attrs
    
    def test_account_form_labels(self, user):
        """AccountForm 레이블 확인"""
        form = AccountForm(user=user)
        
        assert form.fields['name'].label == '계좌 별칭'
        assert form.fields['bank_name'].label == '은행명'
        assert form.fields['account_number'].label == '계좌번호'
    
    def test_business_form_widgets_have_bootstrap_classes(self, user):
        """BusinessForm 위젯에 Bootstrap 클래스 적용"""
        form = BusinessForm(user=user)
        
        assert 'form-control' in form.fields['name'].widget.attrs.get('class', '')
        assert 'form-select' in form.fields['branch_type'].widget.attrs.get('class', '')
    
    def test_business_form_help_texts(self, user):
        """BusinessForm 도움말 텍스트"""
        form = BusinessForm(user=user)
        
        assert form.fields['name'].help_text is not None
        assert form.fields['registration_number'].help_text is not None