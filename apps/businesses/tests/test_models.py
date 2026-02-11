# =============================================================================
# businesses/tests/test_models.py - pytest 모델 테스트
# =============================================================================

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from apps.businesses.models import Business, Account


# =============================================================================
# Fixtures (테스트 데이터 준비)
# =============================================================================

@pytest.fixture
def user(db):
    """테스트용 사용자 생성"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def other_user(db):
    """다른 테스트용 사용자 생성"""
    return User.objects.create_user(
        username='otheruser',
        email='other@example.com',
        password='testpass123'
    )


@pytest.fixture
def business(db, user):
    """테스트용 사업장 생성"""
    return Business.objects.create(
        user=user,
        name='강남점',
        location='서울시 강남구',
        business_type='소매업',
        branch_type='main',
        registration_number='123-45-67890'
    )


@pytest.fixture
def account(db, user, business):
    """테스트용 계좌 생성"""
    return Account.objects.create(
        user=user,
        business=business,
        name='국민은행 주거래',
        bank_name='국민은행',
        account_number='1234-5678-9012-3456',
        account_type='business',
        balance=Decimal('1000000.00')
    )


# =============================================================================
# Business 모델 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessModel:
    """사업장(Business) 모델 테스트 클래스"""
    
    def test_business_creation(self, user):
        """사업장 생성 기본 테스트"""
        business = Business.objects.create(
            user=user,
            name='강남점',
            location='서울시 강남구',
            business_type='소매업',
            branch_type='main',
            registration_number='123-45-67890'
        )
        
        assert business.name == '강남점'
        assert business.user == user
        assert business.location == '서울시 강남구'
        assert business.business_type == '소매업'
        assert business.branch_type == 'main'
        assert business.is_active is True
    
    def test_business_unique_constraint_same_user(self, user):
        """같은 사용자의 동일한 사업장명 중복 방지"""
        Business.objects.create(user=user, name='강남점')
        
        with pytest.raises(IntegrityError):
            Business.objects.create(user=user, name='강남점')
    
    def test_business_soft_delete(self, business):
        """소프트 삭제 테스트"""
        business.soft_delete()
        business.refresh_from_db()
        
        assert business.is_active is False
        assert not Business.active.filter(pk=business.pk).exists()


# =============================================================================
# Account 모델 테스트
# =============================================================================

@pytest.mark.django_db
class TestAccountModel:
    """계좌(Account) 모델 테스트 클래스"""
    
    def test_account_creation(self, user, business):
        """계좌 생성 기본 테스트"""
        account = Account.objects.create(
            user=user,
            business=business,
            name='국민은행 주거래',
            bank_name='국민은행',
            account_number='1234-5678-9012-3456',
            account_type='business',
            balance=Decimal('1000000.00')
        )
        
        assert account.name == '국민은행 주거래'
        assert account.balance == Decimal('1000000.00')
        assert account.is_active is True
    
    def test_update_balance_income(self, account):
        """잔액 업데이트 - 입금 테스트"""
        account.update_balance(Decimal('50000.00'), 'IN')
        account.refresh_from_db()
        
        assert account.balance == Decimal('1050000.00')