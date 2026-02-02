# =============================================================================
# businesses/models.py - 사업장 및 계좌 관리
# =============================================================================

"""
사업장 및 계좌 관리

다중 사업장(지점) 운영을 지원하며, 각 사업장별로 계좌를 연결할 수 있습니다.
"""
import logging
import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F, Sum
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.core.models import SoftDeleteModel
logger = logging.getLogger(__name__)


class Business(SoftDeleteModel):
    """사업장/지점 (다중 사업장 지원)"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='businesses', db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    location = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(max_length=50, blank=True)
    registration_number = models.CharField(max_length=12, blank=True)

    class Meta:
        db_table = 'businesses'
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'is_active', 'name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                condition=models.Q(is_active=True),
                name='unique_active_business_name_per_user'
            )
        ]

    def __str__(self):
        return self.name
    
    def get_total_revenue(self, start_date=None, end_date=None):
        """
        총 수입 계산 (역참조 사용 - 순환 import 방지)
        
        Args:
            start_date: 시작일 (선택)
            end_date: 종료일 (선택)
        """
        qs = self.transactions.filter(tx_type='IN', is_active=True)
        
        if start_date:
            qs = qs.filter(occurred_at__gte=start_date)
        if end_date:
            qs = qs.filter(occurred_at__lte=end_date)
        
        total = qs.aggregate(total=Sum('amount'))['total']
        return total or Decimal('0.00')


class Account(SoftDeleteModel):
    """은행 계좌 (잔액 자동 추적)"""
    
    ACCOUNT_TYPE_CHOICES = [
        ('business', '사업용'),
        ('personal', '개인용'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts', db_index=True)
    business = models.ForeignKey(Business, on_delete=models.SET_NULL, null=True, blank=True, related_name='accounts')
    name = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=50)
    account_number = models.CharField(max_length=50)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='business', db_index=True)
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        db_table = 'accounts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active', 'account_type']),
            models.Index(fields=['business', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.bank_name})"
    
    def get_masked_account_number(self):
        """계좌번호 마스킹 (중간 항상 4개 별표)"""
        if not self.account_number:
            return '****'

        num = self.account_number.replace('-', '').replace(' ', '')

        if len(num) < 8:
            return '****'

        front = num[:4]
        back = num[8:]  # 8번째 이후 전부

        # 중간은 항상 4개 별표 (실제 자리수와 무관)
        return f"{front}-****-{back}" if back else f"{front}-****"

    def update_balance(self, amount, tx_type):
        if tx_type not in ['IN', 'OUT']:
            raise ValueError(f"잘못된 tx_type: {tx_type}")
        
        with transaction.atomic():
            # select_for_update(of='self')를 쓰면 PostgreSQL 등에서 더 정밀한 잠금이 가능합니다.
            account = Account.objects.select_for_update().get(pk=self.pk)
            
            if tx_type == 'OUT' and account.balance < amount:
                raise ValidationError({
                    'balance': f'잔액 부족 (현재: {account.balance:,.0f}원, 요청: {amount:,.0f}원)'
                })
            
            if tx_type == 'IN':
                account.balance = F('balance') + amount
            else:
                account.balance = F('balance') - amount
            
            # updated_at이 확실히 존재하는지 core/models.py 확인 필수!
            account.save(update_fields=['balance', 'updated_at'])
            
            # 1. DB에서 계산된 값을 메모리로 즉시 반영
            account.refresh_from_db(fields=['balance'])
            
            # 2. 현재 인스턴스(self)의 balance 필드도 업데이트
            self.balance = account.balance