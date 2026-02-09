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
from django.db.models.signals import pre_save

logger = logging.getLogger(__name__)

# 상수
ATTACHMENT_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

class MerchantCategory(TimeStampedModel):
    """거래처 분류 (도매처, 소매처, 고정지출처 등)"""
    # [수정] null=True, blank=True를 추가하여 공통 카테고리 생성이 가능하게 변경
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='merchant_categories', null=True, blank=True)
    name = models.CharField(max_length=50)
    
    class Meta:
        db_table = 'merchant_categories'
        constraints = [
            # 이름 중복 방지
            models.UniqueConstraint(
                fields=['user', 'name'], 
                condition=models.Q(user__isnull=False), 
                name='unique_merchant_category_per_user'
            ),
            models.UniqueConstraint(
                fields=['name'], 
                condition=models.Q(user__isnull=True), 
                name='unique_global_merchant_category_name'
            )
        ]

    def __str__(self):
        return self.name

class Merchant(SoftDeleteModel):
    """거래처/공급업체"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='merchants', db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    business_number = models.CharField(max_length=12, blank=True, db_index=True)
    contact = models.CharField(max_length=50, blank=True)
    category = models.ForeignKey('MerchantCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='merchants')
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
    income_type = models.CharField(max_length=30, choices=INCOME_TYPE_CHOICES, blank=True, null=True, db_index=True)
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
            models.UniqueConstraint(
                fields=['user', 'name'],
                condition=models.Q(user__isnull=False),
                name='unique_user_category_name'
            ),
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
    def income(self): return self.filter(tx_type='IN')
    def expense(self): return self.filter(tx_type='OUT')
    def business_only(self): return self.filter(is_business=True)
    def by_month(self, year, month): return self.filter(occurred_at__year=year, occurred_at__month=month)
    def by_date_range(self, start_date, end_date): return self.filter(occurred_at__gte=start_date, occurred_at__lte=end_date)
    def with_relations(self): return self.select_related('account', 'merchant', 'category', 'business', 'user').prefetch_related('attachment')


class TransactionManager(models.Manager):
    """Transaction Manager (active + QuerySet 결합)"""
    def get_queryset(self): return TransactionQuerySet(self.model, using=self._db).filter(is_active=True)
    def income(self): return self.get_queryset().income()
    def expense(self): return self.get_queryset().expense()
    def business_only(self): return self.get_queryset().business_only()
    def by_month(self, year, month): return self.get_queryset().by_month(year, month)
    def with_relations(self): return self.get_queryset().with_relations()


class Transaction(SoftDeleteModel):
    """거래 내역 (핵심 모델)"""
    TX_TYPE_CHOICES = [('IN', '수입'), ('OUT', '지출')]
    TAX_TYPE_CHOICES = [('taxable', '과세 (부가세 10%)'), ('tax_free', '면세'), ('zero_rated', '영세율 (수출)')]
    
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
    
    objects = models.Manager()
    active = TransactionManager()

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
        return self.merchant.name if self.merchant else (self.merchant_name or '(미지정)')
    
    def clean(self):
        errors = {}
        if not self.merchant and not self.merchant_name:
            errors['merchant'] = '거래처를 선택하거나 직접 입력하세요'
        if self.is_business and self.tax_type == 'taxable' and not self.vat_amount:
            errors['vat_amount'] = '과세 거래는 부가세 금액이 필수입니다'
        if self.tax_type in ['tax_free', 'zero_rated'] and self.vat_amount:
            errors['vat_amount'] = '면세/영세율 거래는 부가세가 없어야 합니다'
        if self.category:
            if self.tx_type == 'IN' and self.category.type != 'income':
                errors['category'] = '수입 거래는 수입 카테고리를 사용해야 합니다'
            elif self.tx_type == 'OUT' and self.category.type != 'expense':
                errors['category'] = '지출 거래는 지출 카테고리를 사용해야 합니다'
        if errors: raise ValidationError(errors)

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.is_business and self.tax_type == 'taxable' and not self.vat_amount:
            self.vat_amount = (self.amount * Decimal('0.1')).quantize(Decimal('0.01'))
        self.full_clean()
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
        super().save(*args, **kwargs)
        try:
            if is_new:
                self.account.update_balance(self.amount, self.tx_type)
            else:
                if old_account != self.account or old_amount != self.amount or old_tx_type != self.tx_type:
                    reverse_type = 'OUT' if old_tx_type == 'IN' else 'IN'
                    old_account.update_balance(old_amount, reverse_type)
                    self.account.update_balance(self.amount, self.tx_type)
        except Exception as e:
            logger.error(f"잔액 업데이트 실패: {e}")
            raise
    
    def delete(self, *args, **kwargs):
        try:
            reverse_type = 'OUT' if self.tx_type == 'IN' else 'IN'
            self.account.update_balance(self.amount, reverse_type)
        except Exception as e:
            logger.error(f"잔액 복구 실패: {e}")
            raise
        super().delete(*args, **kwargs)

    @property
    def supply_value(self):
        if self.amount and self.vat_amount:
            return self.amount - self.vat_amount
        return self.amount or 0
    
    # imsi_cjy_delete_fo_rms.py 적용시 사용될 코드
    @property
    def total_amount(self):
        """총금액 = 입력 금액 (부가세 포함 기준)"""
        return self.amount or Decimal('0')
    
    @property
    def has_attachment(self):
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
    ATTACHMENT_TYPE_CHOICES = [('receipt', '영수증'), ('tax_invoice', '세금계산서'), ('simple_receipt', '간이영수증')]
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
        indexes = [models.Index(fields=['user', '-uploaded_at']), models.Index(fields=['transaction'])]
        constraints = [models.CheckConstraint(condition=models.Q(size__lte=ATTACHMENT_MAX_FILE_SIZE), name='attachment_file_size_limit')]

    def __str__(self): return f"{self.get_attachment_type_display()} - {self.original_name}"
    
    def clean(self):
        if self.file and hasattr(self.file, 'size') and self.file.size > ATTACHMENT_MAX_FILE_SIZE:
            raise ValidationError({'file': f'파일 크기는 {ATTACHMENT_MAX_FILE_SIZE // (1024*1024)}MB를 초과할 수 없습니다'})

@receiver(pre_save, sender=Attachment)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    파일이 수정될 때 기존의 물리 파일을 삭제
    """
    # 1. 처음 생성되는 레코드라면(PK가 없다면) 비교할 대상이 없으므로 종료
    if not instance.pk:
        return False

    try:
        # 2. DB에 저장되어 있는 기존 레코드를 가져옴
        old_file = sender.objects.get(pk=instance.pk).file
    except sender.DoesNotExist:
        return False

    # 3. 새로 업로드된 파일과 기존 파일이 다르다면?
    new_file = instance.file
    if not old_file == new_file:
        # 4. 기존 파일이 존재한다면 삭제
        if old_file and os.path.isfile(old_file.path):
            os.remove(old_file.path)
            logger.info(f"기존 파일 삭제 완료 (수정됨): {old_file.path}")

@receiver(post_delete, sender=Attachment)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    레코드가 삭제된 후(post_delete) 실제 물리 파일을 삭제
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
            logger.info(f"물리 파일 삭제 완료 (레코드 삭제됨): {instance.file.path}")