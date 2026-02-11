"""
사업장 및 계좌 관리

다중 사업장(지점) 운영을 지원하며, 각 사업장별로 계좌를 연결할 수 있습니다.
"""
import logging
import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum

from apps.core.models import SoftDeleteModel

logger = logging.getLogger(__name__)


class Business(SoftDeleteModel):
    """사업장/지점 (다중 사업장 지원)"""
    
    BRANCH_TYPE_CHOICES = [
        ('main', '본점'),
        ('branch', '지점'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='businesses', db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    location = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(max_length=50, blank=True)
    registration_number = models.CharField(
        max_length=12, 
        blank=True, 
        verbose_name='사업자등록번호',
        help_text='000-00-00000 형식'
    )
    branch_code = models.CharField(
        max_length=4,
        default='0001',
        verbose_name='분류코드',
        help_text='같은 사업자번호의 사업장 구분 (0001~9999)'
    )
    branch_type = models.CharField(
        max_length=10,
        choices=BRANCH_TYPE_CHOICES,
        default='main',
        verbose_name='점포 구분'
    )

    memo = models.TextField(blank=True, null=True, verbose_name="사업장 메모")

    
    branch_type = models.CharField(max_length=10, choices=BRANCH_TYPE_CHOICES, default='main', db_index=True)

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

    def get_masked_registration_number(self):
        if not self.registration_number:
            return "-"

        original = str(self.registration_number)
        nums_only = re.sub(r"[^0-9]", "", original)
        if len(nums_only) < 5:
            return "*****"

        count = 0
        masked_list = list(original)
        for i in range(len(masked_list) - 1, -1, -1):
            if masked_list[i].isdigit():
                masked_list[i] = "*"
                count += 1
            if count == 5:
                break

        return "".join(masked_list)
    
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
    
    def get_total_expense(self, start_date=None, end_date=None):
        """
        총 지출 계산 (tx_type='OUT' 필터링)
        """
        # transactions 역참조를 통해 지출(OUT)만 가져옵니다.
        qs = self.transactions.filter(tx_type='OUT', is_active=True)
        
        if start_date:
            qs = qs.filter(occurred_at__gte=start_date)
        if end_date:
            qs = qs.filter(occurred_at__lte=end_date)
        
        total = qs.aggregate(total=Sum('amount'))['total']
        return total or Decimal('0.00')
    
    def get_full_registration_number(self):
        """사업자번호 + 분류코드"""
        if self.registration_number:
            return f"{self.registration_number} ({self.branch_code})"
        return "-"
    
    def get_next_branch_code(self):
        """같은 사업자번호의 다음 분류코드 생성"""
        if not self.registration_number:
            return "0001"
        
        existing = Business.objects.filter(
            user=self.user,
            registration_number=self.registration_number
        ).exclude(pk=self.pk).count()
        
        return str(existing + 1).zfill(4)
    
    def save(self, *args, **kwargs):
        # 새로 생성 시 branch_code 자동 설정
        if not self.pk and self.registration_number:
            if self.branch_code == '0001':  # 기본값인 경우
                self.branch_code = self.get_next_branch_code()
        
        super().save(*args, **kwargs)



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
        """
        계좌번호 마스킹 (입력 형식 유지)
        규칙: 마지막 5글자 마스킹 + 중간 일부 마스킹
        """
        if not self.account_number:
            return "****"

        original = self.account_number
        # 1. 숫자만 추출 (마지막 5자리를 찾기 위함)
        nums_only = re.sub(r'[^0-9]', '', original)
        
        if len(nums_only) < 5:
            return "****"

        # 2. 뒤에서부터 5개의 숫자를 찾아 '*'로 변환
        count = 0
        masked_list = list(original)
        
        for i in range(len(masked_list) - 1, -1, -1):
            if masked_list[i].isdigit():
                masked_list[i] = '*'
                count += 1
            if count == 5:
                break
                
        masked_res = "".join(masked_list)
        
        # 3. 추가로 "중간" 부분 (예: 앞 4자리 이후 ~ 마스킹 시작 전) 처리
        # 이 부분은 기획에 따라 '고정 4글자 별표'로 치환하거나 조절 가능합니다.
        # 예: "201-55****-**-***" 형태
        
        return masked_res

    def update_balance(self, amount, tx_type):
    
    # 계좌 잔액 업데이트 (동시성 안전)

    # F() 표현식을 사용하여 Race Condition 방지:
    # - 일반적인 방법: balance = balance + amount (위험!)
    #   → 동시에 2개 요청이 들어오면 한 번만 반영될 수 있음
    
    # - F() 사용: UPDATE balance = balance + amount (안전!)
    #   → DB 레벨에서 원자적으로 처리, 동시성 문제 없음
    
    # Args:
    #     amount: 변경할 금액
    #     tx_type: 'IN' (입금) 또는 'OUT' (출금)
    
    # Example:
    #     # 10,000원 입금
    #     account.update_balance(Decimal('10000'), 'IN')
        
    #     # 5,000원 출금
    #     account.update_balance(Decimal('5000'), 'OUT')

        if tx_type not in ['IN', 'OUT']:
            raise ValueError(f"잘못된 tx_type: {tx_type}")
        
        from django.utils import timezone
        
        # F() 표현식으로 DB 레벨에서 직접 연산
        # → 메모리에 로드하지 않고 UPDATE 쿼리 1개로 처리
        if tx_type == 'IN':
            # 입금: 잔액 증가
            Account.objects.filter(pk=self.pk).update(
                balance=F('balance') + amount,
                updated_at=timezone.now()
            )
        else:
            # 출금: 잔액 감소
            Account.objects.filter(pk=self.pk).update(
                balance=F('balance') - amount,
                updated_at=timezone.now()
            )
        
        # DB에서 변경된 값을 메모리에 반영 (self.balance 업데이트)
        self.refresh_from_db(fields=['balance'])

    def hard_delete(self):
        """DB에서 데이터를 완전히 삭제 (복구 불가)"""
        # 부모 클래스(models.Model)의 실제 delete를 호출합니다.
        super().delete()
        logger.info(f"계좌 '{self.name}' (ID: {self.pk}) 가 DB에서 영구 삭제되었습니다.")

    def soft_delete(self):
        """계좌 소프트 삭제 + 연관된 거래도 함께 삭제"""
        from apps.transactions.models import Transaction
        
        # 1. 계좌 삭제
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
        
        # 2. 이 계좌의 활성 거래들도 함께 삭제
        deleted_count = Transaction.objects.filter(
            account=self,
            user=self.user,
            is_active=True
        ).update(is_active=False)
        
        logger.info(
            f"계좌 '{self.name}' 삭제 완료 "
            f"(거래 {deleted_count}건 함께 삭제)"
        )
        
        return deleted_count

    def restore(self):
        """계좌 복구 + 연관된 거래도 함께 복구"""
        from apps.transactions.models import Transaction
        from django.db.models import Sum
        
        # 1. 계좌 복구
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
        
        # 2. 이 계좌의 삭제된 거래들 복구
        restored_count = Transaction.objects.filter(
            account=self,
            user=self.user,
            is_active=False
        ).update(is_active=True)
        
        # 3. 잔액 재계산
        active_txs = Transaction.objects.filter(
            account=self,
            user=self.user,
            is_active=True
        )
        income = active_txs.filter(tx_type='IN').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        expense = active_txs.filter(tx_type='OUT').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        calculated_balance = income - expense
        
        # 4. 잔액이 다르면 수정
        if self.balance != calculated_balance:
            old_balance = self.balance
            self.balance = calculated_balance
            self.save(update_fields=['balance', 'updated_at'])
            logger.warning(
                f"계좌 '{self.name}' 복구 시 잔액 수정: "
                f"{old_balance:,}원 → {calculated_balance:,}원"
            )
        
        logger.info(
            f"계좌 '{self.name}' 복구 완료 "
            f"(거래 {restored_count}건, 잔액 {self.balance:,}원)"
        )
        
        return restored_count
