"""
transactions 앱 admin.py 테스트
Django Admin 인터페이스 및 커스텀 메서드 테스트
"""
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.admin import (
    TransactionAdmin,
    MerchantAdmin,
    CategoryAdmin,
    AttachmentAdmin,
    AttachmentInline,
)
from apps.transactions.models import Transaction, Merchant, Category, Attachment


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def admin_user(db):
    """관리자 유저"""
    return User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='admin123'
    )


@pytest.fixture
def test_user(db):
    """일반 테스트 유저"""
    return User.objects.create_user(username='tester', password='pass')


@pytest.fixture
def request_factory():
    """Django RequestFactory"""
    return RequestFactory()


@pytest.fixture
def admin_request(request_factory, admin_user):
    """관리자 권한 요청 객체"""
    request = request_factory.get('/admin/')
    request.user = admin_user
    return request


@pytest.fixture
def business(test_user):
    return Business.objects.create(user=test_user, name='Test Business')


@pytest.fixture
def account(test_user, business):
    return Account.objects.create(
        user=test_user,
        business=business,
        name='Test Account',
        bank_name='Test Bank',
        account_number='123-456',
        balance=Decimal('1000000.00'),
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
    return Merchant.objects.create(
        user=test_user,
        name='테스트 거래처',
        business_number='123-45-67890'
    )


@pytest.fixture
def income_transaction(test_user, business, account, income_category, merchant):
    """수입 거래"""
    return Transaction.objects.create(
        user=test_user,
        business=business,
        account=account,
        merchant=merchant,
        category=income_category,
        tx_type='IN',
        tax_type='taxable',
        is_business=True,
        amount=Decimal('110000.00'),
        vat_amount=Decimal('10000.00'),
        occurred_at=timezone.now(),
        merchant_name='고객사'
    )


@pytest.fixture
def expense_transaction(test_user, business, account, expense_category, merchant):
    """지출 거래"""
    return Transaction.objects.create(
        user=test_user,
        business=business,
        account=account,
        merchant=merchant,
        category=expense_category,
        tx_type='OUT',
        tax_type='taxable',
        is_business=True,
        amount=Decimal('55000.00'),
        vat_amount=Decimal('5000.00'),
        occurred_at=timezone.now(),
        merchant_name='공급업체'
    )


@pytest.fixture
def attachment(test_user, income_transaction):
    """첨부파일"""
    return Attachment.objects.create(
        transaction=income_transaction,
        user=test_user,
        file=SimpleUploadedFile("receipt.pdf", b"pdf content", content_type="application/pdf"),
        original_name="영수증.pdf",
        size=2048,
        content_type="application/pdf"
    )


# ============================================================
# TransactionAdmin 테스트
# ============================================================

@pytest.mark.django_db
class TestTransactionAdmin:
    """TransactionAdmin 테스트"""

    def test_list_display_fields(self):
        """list_display 필드 확인"""
        admin = TransactionAdmin(Transaction, AdminSite())
        
        expected_fields = [
            'occurred_at',
            'get_tx_type_display_colored',
            'get_amount_display',
            'merchant',
            'business',
            'category',
            'is_active'
        ]
        
        assert admin.list_display == expected_fields

    def test_get_queryset_includes_inactive(self, admin_request, test_user, business, account, income_category):
        """get_queryset가 비활성 거래도 포함하는지 확인"""
        # 활성 거래
        active_tx = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000'),
            occurred_at=timezone.now(),
            merchant_name='활성',
            is_active=True
        )
        
        # 비활성 거래 (소프트 삭제)
        inactive_tx = Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('20000'),
            occurred_at=timezone.now(),
            merchant_name='비활성',
            is_active=False
        )
        
        admin = TransactionAdmin(Transaction, AdminSite())
        queryset = admin.get_queryset(admin_request)
        
        # 둘 다 포함되어야 함
        assert queryset.count() == 2
        assert active_tx in queryset
        assert inactive_tx in queryset

    def test_get_tx_type_display_colored_income(self, income_transaction):
        """수입 거래 색상 표시"""
        admin = TransactionAdmin(Transaction, AdminSite())
        result = admin.get_tx_type_display_colored(income_transaction)
        
        # HTML에 파란색 + "수입" 포함
        assert 'blue' in result
        assert 'font-weight:bold' in result
        assert '수입' in result

    def test_get_tx_type_display_colored_expense(self, expense_transaction):
        """지출 거래 색상 표시"""
        admin = TransactionAdmin(Transaction, AdminSite())
        result = admin.get_tx_type_display_colored(expense_transaction)
        
        # HTML에 빨간색 + "지출" 포함
        assert 'red' in result
        assert 'font-weight:bold' in result
        assert '지출' in result

    def test_get_amount_display_income(self, income_transaction):
        """수입 금액 표시"""
        admin = TransactionAdmin(Transaction, AdminSite())
        result = admin.get_amount_display(income_transaction)
        
        # HTML에 파란색 + 금액 포함
        assert 'blue' in result
        assert '110,000원' in result

    def test_get_amount_display_expense(self, expense_transaction):
        """지출 금액 표시"""
        admin = TransactionAdmin(Transaction, AdminSite())
        result = admin.get_amount_display(expense_transaction)
        
        # HTML에 빨간색 + 금액 포함
        assert 'red' in result
        assert '55,000원' in result

    def test_search_fields(self):
        """검색 필드 확인"""
        admin = TransactionAdmin(Transaction, AdminSite())
        
        expected_search_fields = ['memo', 'merchant__name', 'business__name']
        assert admin.search_fields == expected_search_fields

    def test_list_filter(self):
        """필터 필드 확인"""
        admin = TransactionAdmin(Transaction, AdminSite())
        
        expected_filters = [
            'is_active',
            'tx_type',
            'tax_type',
            'is_business',
            'business__name'
        ]
        assert admin.list_filter == expected_filters

    def test_inlines_includes_attachment(self):
        """인라인에 AttachmentInline 포함 확인"""
        admin = TransactionAdmin(Transaction, AdminSite())
        
        assert AttachmentInline in admin.inlines


# ============================================================
# MerchantAdmin 테스트
# ============================================================

@pytest.mark.django_db
class TestMerchantAdmin:
    """MerchantAdmin 테스트"""

    def test_list_display_fields(self):
        """list_display 필드 확인"""
        admin = MerchantAdmin(Merchant, AdminSite())
        
        expected_fields = [
            'name',
            'business_number',
            'category',
            'get_transaction_count',
            'is_active'
        ]
        
        assert admin.list_display == expected_fields

    def test_get_queryset_annotates_transaction_count(self, admin_request, test_user, business, account, income_category):
        """get_queryset가 거래 횟수를 annotate하는지 확인"""
        # 거래처 생성
        merchant1 = Merchant.objects.create(user=test_user, name='거래처1')
        merchant2 = Merchant.objects.create(user=test_user, name='거래처2')
        
        # merchant1에 거래 3건
        for i in range(3):
            Transaction.objects.create(
                user=test_user,
                business=business,
                account=account,
                merchant=merchant1,
                category=income_category,
                tx_type='IN',
                amount=Decimal('10000'),
                occurred_at=timezone.now(),
                merchant_name=merchant1.name
            )
        
        # merchant2에 거래 1건
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            merchant=merchant2,
            category=income_category,
            tx_type='IN',
            amount=Decimal('5000'),
            occurred_at=timezone.now(),
            merchant_name=merchant2.name
        )
        
        admin = MerchantAdmin(Merchant, AdminSite())
        queryset = admin.get_queryset(admin_request)
        
        # annotate된 tx_count 확인
        merchant1_qs = queryset.get(id=merchant1.id)
        merchant2_qs = queryset.get(id=merchant2.id)
        
        assert hasattr(merchant1_qs, 'tx_count')
        assert merchant1_qs.tx_count == 3
        assert merchant2_qs.tx_count == 1

    def test_get_transaction_count_display(self, admin_request, test_user, business, account, income_category):
        """거래 횟수 표시 메서드"""
        merchant = Merchant.objects.create(user=test_user, name='테스트거래처')
        
        # 거래 5건 생성
        for i in range(5):
            Transaction.objects.create(
                user=test_user,
                business=business,
                account=account,
                merchant=merchant,
                category=income_category,
                tx_type='IN',
                amount=Decimal('10000'),
                occurred_at=timezone.now(),
                merchant_name=merchant.name
            )
        
        admin = MerchantAdmin(Merchant, AdminSite())
        queryset = admin.get_queryset(admin_request)
        merchant_qs = queryset.get(id=merchant.id)
        
        result = admin.get_transaction_count(merchant_qs)
        assert result == "5건"

    def test_get_transaction_count_zero(self, admin_request, test_user):
        """거래가 없는 거래처"""
        merchant = Merchant.objects.create(user=test_user, name='거래없음')
        
        admin = MerchantAdmin(Merchant, AdminSite())
        queryset = admin.get_queryset(admin_request)
        merchant_qs = queryset.get(id=merchant.id)
        
        result = admin.get_transaction_count(merchant_qs)
        assert result == "0건"


# ============================================================
# CategoryAdmin 테스트
# ============================================================

@pytest.mark.django_db
class TestCategoryAdmin:
    """CategoryAdmin 테스트"""

    def test_list_display_fields(self):
        """list_display 필드 확인"""
        admin = CategoryAdmin(Category, AdminSite())
        
        expected_fields = ['name', 'type', 'user', 'order']
        assert admin.list_display == expected_fields

    def test_list_filter(self):
        """필터 필드 확인"""
        admin = CategoryAdmin(Category, AdminSite())
        assert admin.list_filter == ['type']

    def test_ordering(self):
        """정렬 순서 확인"""
        admin = CategoryAdmin(Category, AdminSite())
        assert admin.ordering == ['type', 'order']

    def test_search_fields(self):
        """검색 필드 확인"""
        admin = CategoryAdmin(Category, AdminSite())
        assert admin.search_fields == ['name']


# ============================================================
# AttachmentAdmin 테스트
# ============================================================

@pytest.mark.django_db
class TestAttachmentAdmin:
    """AttachmentAdmin 테스트"""

    def test_list_display_fields(self):
        """list_display 필드 확인"""
        admin = AttachmentAdmin(Attachment, AdminSite())
        
        expected_fields = [
            'original_name',
            'get_size_display',
            'transaction',
            'uploaded_at'
        ]
        assert admin.list_display == expected_fields

    def test_get_size_display_bytes(self, test_user, income_transaction):
        """파일 크기 표시 - Bytes"""
        attachment = Attachment.objects.create(
            transaction=income_transaction,
            user=test_user,
            file=SimpleUploadedFile("small.txt", b"x" * 500),
            original_name="small.txt",
            size=500,  # 500 bytes
            content_type="text/plain"
        )
        
        admin = AttachmentAdmin(Attachment, AdminSite())
        result = admin.get_size_display(attachment)
        
        assert result == "500 B"

    def test_get_size_display_kilobytes(self, test_user, income_transaction):
        """파일 크기 표시 - Kilobytes"""
        attachment = Attachment.objects.create(
            transaction=income_transaction,
            user=test_user,
            file=SimpleUploadedFile("medium.txt", b"x" * 2048),
            original_name="medium.txt",
            size=2048,  # 2 KB
            content_type="text/plain"
        )
        
        admin = AttachmentAdmin(Attachment, AdminSite())
        result = admin.get_size_display(attachment)
        
        assert result == "2.0 KB"

    def test_get_size_display_megabytes(self, test_user, income_transaction):
        """파일 크기 표시 - Megabytes"""
        attachment = Attachment.objects.create(
            transaction=income_transaction,
            user=test_user,
            file=SimpleUploadedFile("large.pdf", b"x" * (5 * 1024 * 1024)),
            original_name="large.pdf",
            size=5 * 1024 * 1024,  # 5 MB
            content_type="application/pdf"
        )
        
        admin = AttachmentAdmin(Attachment, AdminSite())
        result = admin.get_size_display(attachment)
        
        assert result == "5.0 MB"

    def test_get_size_display_zero(self, test_user, income_transaction):
        """파일 크기가 0인 경우"""
        attachment = Attachment.objects.create(
            transaction=income_transaction,
            user=test_user,
            file=SimpleUploadedFile("empty.txt", b""),
            original_name="empty.txt",
            size=0,
            content_type="text/plain"
        )
        
        admin = AttachmentAdmin(Attachment, AdminSite())
        result = admin.get_size_display(attachment)
        
        assert result == "0 B"


# ============================================================
# AttachmentInline 테스트
# ============================================================

@pytest.mark.django_db
class TestAttachmentInline:
    """AttachmentInline 테스트"""

    def test_inline_model(self):
        """인라인 모델 확인"""
        inline = AttachmentInline(Transaction, AdminSite())
        assert inline.model == Attachment

    def test_inline_fields(self):
        """인라인 필드 확인"""
        inline = AttachmentInline(Transaction, AdminSite())
        
        expected_fields = ['original_name', 'get_size_display', 'uploaded_at']
        assert inline.fields == expected_fields

    def test_inline_readonly_fields(self):
        """인라인 읽기 전용 필드 확인"""
        inline = AttachmentInline(Transaction, AdminSite())
        
        expected_readonly = ['original_name', 'get_size_display', 'uploaded_at']
        assert inline.readonly_fields == expected_readonly

    def test_inline_can_delete(self):
        """인라인 삭제 가능 여부"""
        inline = AttachmentInline(Transaction, AdminSite())
        assert inline.can_delete is True

    def test_inline_show_change_link(self):
        """인라인 수정 링크 표시 여부"""
        inline = AttachmentInline(Transaction, AdminSite())
        assert inline.show_change_link is True

    def test_get_size_display_bytes(self, test_user, income_transaction):
        """인라인 파일 크기 표시 - Bytes"""
        attachment = Attachment.objects.create(
            transaction=income_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.txt", b"x" * 100),
            original_name="test.txt",
            size=100,
            content_type="text/plain"
        )
        
        inline = AttachmentInline(Transaction, AdminSite())
        result = inline.get_size_display(attachment)
        
        assert result == "100 B"

    def test_get_size_display_kilobytes(self, test_user, income_transaction):
        """인라인 파일 크기 표시 - KB"""
        attachment = Attachment.objects.create(
            transaction=income_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.pdf", b"x" * 3072),
            original_name="test.pdf",
            size=3072,  # 3 KB
            content_type="application/pdf"
        )
        
        inline = AttachmentInline(Transaction, AdminSite())
        result = inline.get_size_display(attachment)
        
        assert result == "3.0 KB"

    def test_get_size_display_megabytes(self, test_user, income_transaction):
        """인라인 파일 크기 표시 - MB"""
        attachment = Attachment.objects.create(
            transaction=income_transaction,
            user=test_user,
            file=SimpleUploadedFile("large.pdf", b"x" * (2 * 1024 * 1024)),
            original_name="large.pdf",
            size=2 * 1024 * 1024,  # 2 MB
            content_type="application/pdf"
        )
        
        inline = AttachmentInline(Transaction, AdminSite())
        result = inline.get_size_display(attachment)
        
        assert result == "2.0 MB"


# ============================================================
# 통합 테스트
# ============================================================

@pytest.mark.django_db
class TestAdminIntegration:
    """Admin 통합 테스트"""

    def test_transaction_admin_with_attachment(self, admin_request, income_transaction, attachment):
        """거래에 첨부파일이 있는 경우"""
        admin = TransactionAdmin(Transaction, AdminSite())
        queryset = admin.get_queryset(admin_request)
        
        tx = queryset.get(id=income_transaction.id)
        assert tx.attachment == attachment

    def test_merchant_with_multiple_transactions(self, admin_request, test_user, business, account, income_category):
        """여러 거래가 있는 거래처"""
        merchant = Merchant.objects.create(user=test_user, name='주요거래처')
        
        # 10건의 거래 생성
        for i in range(10):
            Transaction.objects.create(
                user=test_user,
                business=business,
                account=account,
                merchant=merchant,
                category=income_category,
                tx_type='IN',
                amount=Decimal('10000'),
                occurred_at=timezone.now(),
                merchant_name=merchant.name
            )
        
        admin = MerchantAdmin(Merchant, AdminSite())
        queryset = admin.get_queryset(admin_request)
        merchant_qs = queryset.get(id=merchant.id)
        
        assert merchant_qs.tx_count == 10
        assert admin.get_transaction_count(merchant_qs) == "10건"

    def test_soft_deleted_transactions_visible_in_admin(self, admin_request, test_user, business, account, income_category, expense_category):
        """소프트 삭제된 거래도 admin에서 보임"""
        # 활성 거래 (수입)
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000'),
            occurred_at=timezone.now(),
            merchant_name='활성',
            is_active=True
        )
        
        # 비활성 거래 (지출 - 지출 카테고리 사용)
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,  # 지출 카테고리 사용
            tx_type='OUT',
            amount=Decimal('5000'),
            occurred_at=timezone.now(),
            merchant_name='비활성',
            is_active=False
        )
        
        admin = TransactionAdmin(Transaction, AdminSite())
        queryset = admin.get_queryset(admin_request)
        
        # 둘 다 포함
        assert queryset.count() == 2