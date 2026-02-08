"""거래 내역 관리 (핵심 모델)"""
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db.models import F
from decimal import Decimal
import uuid
import os
import logging

from apps.core.models import TimeStampedModel, SoftDeleteModel
from apps.businesses.models import Business, Account

logger = logging.getLogger(__name__)

# 상수
ATTACHMENT_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


class Merchant(SoftDeleteModel):
    """거래처/공급업체"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='merchants', db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    business_number = models.CharField(max_length=12, blank=True, db_index=True)
    contact = models.CharField(max_length=50, blank=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='merchants')
    memo = models.TextField(blank=True)

    class Meta:
        db_table = 'merchants'
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'is_active', 'name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                condition=models.Q(is_active=True),
                name='unique_active_merchant_name_per_user'
            )
        ]

    def __str__(self):
        return self.name

    def get_masked_business_number(self):
        """마스킹된 사업자번호 반환"""
        if not self.business_number:
            return '-'
        
        cleaned = self.business_number.replace('-', '')
        if len(cleaned) < 10:
            return self.business_number
        
        return f"{cleaned[:3]}-**-***{cleaned[-2:]}"
    
    def get_business_number_display(self, show_full=False):
        """조건부 마스킹"""
        if show_full:
            return self.business_number
        return self.get_masked_business_number()


class Category(TimeStampedModel):
    """거래 카테고리 (수입/지출 분류)"""
    
    TYPE_CHOICES = [
        ('income', '수입'),
        ('expense', '지출'),
    ]

    INCOME_TYPE_CHOICES = [
        ('sales', '매출'),
        ('service', '용역수입'),
        ('interest', '이자수입'),
        ('rental', '임대수입'),
        ('investment', '투자수익'),
        ('other', '기타 수입'),
    ]
    
    EXPENSE_TYPE_CHOICES = [
        ('salary', '인건비'),
        ('rent', '임차료'),
        ('advertising', '광고선전비'),
        ('supplies', '소모품비'),
        ('entertainment', '접대비'),
        ('communication', '통신비'),
        ('utilities', '전기·수도·가스비'),
        ('repair', '수선비'),
        ('vehicle', '차량유지비'),
        ('insurance', '보험료'),
        ('tax', '세금과공과'),
        ('other', '기타 경비'),
    ]
    
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    income_type = models.CharField(max_length=30, choices=INCOME_TYPE_CHOICES, blank=True, null=True, db_index=True)  # 이 줄 추가
    expense_type = models.CharField(max_length=30, choices=EXPENSE_TYPE_CHOICES, blank=True, null=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='custom_categories')
    order = models.IntegerField(default=0, db_index=True)
    is_system = models.BooleanField(default=False, db_index=True) 

    class Meta:
        db_table = 'categories'
        ordering = ['type', 'order', 'name']
        indexes = [
            models.Index(fields=['type', 'order']),
            models.Index(fields=['user', 'type']),
        ]
        constraints = [
            # 사용자별 이름 중복 방지
            models.UniqueConstraint(
                fields=['user', 'name'],
                condition=models.Q(user__isnull=False),
                name='unique_user_category_name'
            ),
            # 시스템 카테고리 이름 중복 방지
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(is_system=True),
                name='unique_system_category_name'
            )
        ]

    def __str__(self):
        return f"[{self.get_type_display()}] {self.name}"
    
    def clean(self):
        """카테고리 타입 검증"""
        errors = {}
        
        if self.type == 'income' and self.expense_type:
            errors['expense_type'] = '수입 카테고리는 지출 세부 유형을 설정할 수 없습니다'
        
        if self.type == 'expense' and self.income_type:
            errors['income_type'] = '지출 카테고리는 수입 세부 유형을 설정할 수 없습니다'
        
        if errors:
            raise ValidationError(errors)


class TransactionQuerySet(models.QuerySet):
    """Transaction 전용 QuerySet (헬퍼 메서드)"""
    
    def income(self):
        """수입만 필터"""
        return self.filter(tx_type='IN')
    
    def expense(self):
        """지출만 필터"""
        return self.filter(tx_type='OUT')
    
    def business_only(self):
        """사업용만 필터"""
        return self.filter(is_business=True)
    
    def by_month(self, year, month):
        """월별 필터"""
        return self.filter(occurred_at__year=year, occurred_at__month=month)
    
    def by_date_range(self, start_date, end_date):
        """날짜 범위 필터"""
        return self.filter(occurred_at__gte=start_date, occurred_at__lte=end_date)
    
    def with_relations(self):
        """관계 데이터 한번에 조회 (N+1 방지)"""
        return self.select_related('account', 'merchant', 'category', 'business', 'user').prefetch_related('attachment')


class TransactionManager(models.Manager):
    """Transaction Manager (active + QuerySet 결합)"""
    
    def get_queryset(self):
        return TransactionQuerySet(self.model, using=self._db).filter(is_active=True)
    
    def income(self):
        return self.get_queryset().income()
    
    def expense(self):
        return self.get_queryset().expense()
    
    def business_only(self):
        return self.get_queryset().business_only()
    
    def by_month(self, year, month):
        return self.get_queryset().by_month(year, month)
    
    def with_relations(self):
        return self.get_queryset().with_relations()


class Transaction(SoftDeleteModel):
    """
    거래 내역 (핵심 모델)
    
    - 부가세 자동 계산
    - 계좌 잔액 자동 동기화
    - 소프트 삭제 지원
    """
    
    TX_TYPE_CHOICES = [
        ('IN', '수입'),
        ('OUT', '지출'),
    ]
    
    TAX_TYPE_CHOICES = [
        ('taxable', '과세 (부가세 10%)'),
        ('tax_free', '면세'),
        ('zero_rated', '영세율 (수출)'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions', db_index=True)
    business = models.ForeignKey(Business, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions', db_index=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transactions')
    merchant = models.ForeignKey(Merchant, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='transactions')
    
    tx_type = models.CharField(max_length=10, choices=TX_TYPE_CHOICES, db_index=True)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES, default='taxable', db_index=True)
    is_business = models.BooleanField(default=True, db_index=True)
    
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.00'))])
    occurred_at = models.DateTimeField(db_index=True)
    merchant_name = models.CharField(max_length=100, blank=True)
    memo = models.TextField(blank=True)
    
    objects = models.Manager()  # 전체 조회 (Admin용)
    active = TransactionManager()  # 활성만 + 헬퍼 메서드

    class Meta:
        db_table = 'transactions'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['user', '-occurred_at']),
            models.Index(fields=['user', 'is_business', '-occurred_at']),
            models.Index(fields=['user', 'tax_type', '-occurred_at']),
            models.Index(fields=['user', 'tx_type', '-occurred_at']),
            models.Index(fields=['business', '-occurred_at']),
            models.Index(fields=['account', '-occurred_at']),
            models.Index(fields=['user', 'is_business', 'tax_type', 'occurred_at']),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='transaction_amount_positive'),
            models.CheckConstraint(
                condition=models.Q(vat_amount__gte=0) | models.Q(vat_amount__isnull=True),
                name='transaction_vat_non_negative'
            ),
        ]

    def __str__(self):
        return f"{self.get_tx_type_display()} {self.amount:,.0f}원 ({self.occurred_at.date()})"
    
    def get_merchant_display(self):
        """거래처명 반환 (FK 또는 직접 입력)"""
        return self.merchant.name if self.merchant else (self.merchant_name or '(미지정)')
    
    def clean(self):
        """거래 데이터 검증"""
        errors = {}
        
        # 거래처 필수
        if not self.merchant and not self.merchant_name:
            errors['merchant'] = '거래처를 선택하거나 직접 입력하세요'
        
        # 부가세 검증
        if self.is_business and self.tax_type == 'taxable' and not self.vat_amount:
            errors['vat_amount'] = '과세 거래는 부가세 금액이 필수입니다'
        
        if self.tax_type in ['tax_free', 'zero_rated'] and self.vat_amount:
            errors['vat_amount'] = '면세/영세율 거래는 부가세가 없어야 합니다'
        
        # 카테고리 타입 일치
        if self.category:
            if self.tx_type == 'IN' and self.category.type != 'income':
                errors['category'] = '수입 거래는 수입 카테고리를 사용해야 합니다'
            elif self.tx_type == 'OUT' and self.category.type != 'expense':
                errors['category'] = '지출 거래는 지출 카테고리를 사용해야 합니다'
        
        if errors:
            raise ValidationError(errors)
    @transaction.atomic
    def save(self, *args, **kwargs):
        """부가세 자동 계산 및 잔액 업데이트"""
        
        # 부가세 자동 계산 (과세 거래만)
        if self.is_business and self.tax_type == 'taxable' and not self.vat_amount:
            self.vat_amount = (self.amount * Decimal('0.1')).quantize(Decimal('0.01'))
        
        # 검증 실행
        self.full_clean()
        
        # 신규/수정 판별
        is_new = self.pk is None
        old_amount = None
        old_tx_type = None
        old_account = None
        
        if not is_new:
            try:
                old_tx = Transaction.objects.get(pk=self.pk)
                old_amount = old_tx.amount
                old_tx_type = old_tx.tx_type
                old_account = old_tx.account
            except Transaction.DoesNotExist:
                is_new = True
        
        # 저장
        super().save(*args, **kwargs)
        
        # 계좌 잔액 업데이트
        try:
            if is_new:
                # 신규 거래: 현재 계좌에 반영
                self.account.update_balance(self.amount, self.tx_type)
            else:
                # 수정: 변경사항이 있을 때만
                if old_account != self.account or old_amount != self.amount or old_tx_type != self.tx_type:
                    # 이전 계좌에서 취소
                    reverse_type = 'OUT' if old_tx_type == 'IN' else 'IN'
                    old_account.update_balance(old_amount, reverse_type)
                    # 새 계좌에 반영
                    self.account.update_balance(self.amount, self.tx_type)
        except Exception as e:
            logger.error(f"잔액 업데이트 실패: {e}")
            raise
    
    def delete(self, *args, **kwargs):
        """삭제 시 잔액 되돌리기"""
        try:
            reverse_type = 'OUT' if self.tx_type == 'IN' else 'IN'
            self.account.update_balance(self.amount, reverse_type)
        except Exception as e:
            logger.error(f"잔액 복구 실패: {e}")
            raise
        
        super().delete(*args, **kwargs)

    @property
    def supply_value(self):
        """합계에서 부가세를 뺀 공급가액을 반환"""
        if self.amount and self.vat_amount:
            return self.amount - self.vat_amount
        return self.amount or 0
    
    # imsi_cjy_delete_fo_rms.py 적용시 사용될 코드
    @property
    def total_amount(self):
        """총금액 = 공급가액 + 부가세"""
        return self.amount + (self.vat_amount or Decimal('0'))
    
    @property
    def has_attachment(self):
        # 장고가 알려준 'attachment'라는 이름을 사용합니다.
        # hasattr는 "너 이런 이름 가지고 있니?"라고 물어보는 안전한 방법입니다.
        return hasattr(self, 'attachment') and self.attachment is not None

def attachment_upload_path(instance, filename):
    """
    고유한 파일명 생성
    
    원본: 영수증.jpg
    저장: attachments/2026/02/a1b2c3d4e5f6.jpg
    """
    # 확장자 추출
    ext = os.path.splitext(filename)[1]  # .jpg, .pdf 등
    
    # 고유한 파일명 생성 (UUID)
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    
    # 년/월 폴더 + 고유 파일명
    return f'attachments/{instance.transaction.occurred_at:%Y/%m}/{unique_filename}'


class Attachment(TimeStampedModel):
    """첨부파일 (영수증/세금계산서)"""
    
    ATTACHMENT_TYPE_CHOICES = [
        ('receipt', '영수증'),
        ('tax_invoice', '세금계산서'),
        ('simple_receipt', '간이영수증'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attachments', db_index=True)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='attachment')
    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default='receipt')
    file = models.FileField(
        upload_to=attachment_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'pdf'])]
    )
    original_name = models.CharField(max_length=255)
    size = models.IntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attachments'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['user', '-uploaded_at']),
            models.Index(fields=['transaction']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(size__lte=ATTACHMENT_MAX_FILE_SIZE),
                name='attachment_file_size_limit'
            )
        ]

    def __str__(self):
        return f"{self.get_attachment_type_display()} - {self.original_name}"
    
    def clean(self):
        """파일 크기 검증"""
        if self.file and hasattr(self.file, 'size') and self.file.size > ATTACHMENT_MAX_FILE_SIZE:
            raise ValidationError({'file': f'파일 크기는 {ATTACHMENT_MAX_FILE_SIZE // (1024*1024)}MB를 초과할 수 없습니다'})


@receiver(post_delete, sender=Attachment)
def delete_file_on_attachment_delete(sender, instance, **kwargs):
    """첨부파일 삭제 시 물리적 파일도 삭제"""
    if not instance.file:
        return
    
    try:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
            logger.info(f"파일 삭제: {instance.file.path}")
    except Exception as e:
        logger.warning(f"파일 삭제 실패 ({instance.file.name}): {e}")

