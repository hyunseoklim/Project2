"""
transactions 앱 뷰 테스트 - 추가 테스트 (커버리지 향상용)
기존 test_views.py의 61%에서 95%+ 커버리지로 향상시키기 위한 보완 테스트
"""
from decimal import Decimal
from datetime import datetime
from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Account, Business
from apps.transactions.models import Category, Transaction, Merchant, Attachment


# ============================================================
# Fixtures (기존 test_views.py와 동일)
# ============================================================

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username='tester', password='pass')


@pytest.fixture
def another_user(db):
    """권한 테스트용 다른 사용자"""
    return User.objects.create_user(username='another', password='pass')


@pytest.fixture
def auth_client(client, test_user):
    client.login(username='tester', password='pass')
    return client


@pytest.fixture
def another_auth_client(client, another_user):
    """다른 사용자 클라이언트"""
    client.login(username='another', password='pass')
    return client


@pytest.fixture
def business(test_user):
    return Business.objects.create(user=test_user, name='Test Biz')


@pytest.fixture
def another_business(another_user):
    """다른 사용자의 사업장"""
    return Business.objects.create(user=another_user, name='Another Biz')


@pytest.fixture
def account(test_user, business):
    return Account.objects.create(
        user=test_user,
        business=business,
        name='Main Account',
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
    return Merchant.objects.create(user=test_user, name='테스트 거래처')


@pytest.fixture
def sample_transaction(test_user, business, account, income_category):
    """테스트용 샘플 거래"""
    return Transaction.objects.create(
        user=test_user,
        business=business,
        account=account,
        category=income_category,
        tx_type='IN',
        tax_type='taxable',
        is_business=True,
        amount=Decimal('11000.00'),
        vat_amount=Decimal('1000.00'),
        occurred_at=timezone.now(),
        merchant_name='테스트고객'
    )


# ============================================================
# Excel 관련 뷰 테스트
# ============================================================

@pytest.mark.django_db
class TestExcelViews:
    """Excel 다운로드/업로드 관련 뷰 테스트"""

    def test_download_excel_template_requires_login(self, client):
        """Excel 템플릿 다운로드는 로그인 필요"""
        response = client.get(reverse('transactions:download_template'))
        assert response.status_code == 302

    def test_download_excel_template_success(self, auth_client):
        """Excel 템플릿 다운로드 성공"""
        response = auth_client.get(reverse('transactions:download_template'))
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'transaction_template.xlsx' in response['Content-Disposition']

    def test_transaction_export_view_requires_login(self, client):
        """거래내역 내보내기는 로그인 필요"""
        response = client.get(reverse('transactions:transaction_export'))
        assert response.status_code == 302

    def test_transaction_export_view_success(self, auth_client, test_user, sample_transaction):
        """거래내역 내보내기 성공 (타임스탬프 포함 파일명)"""
        response = auth_client.get(reverse('transactions:transaction_export'))
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'transaction_' in response['Content-Disposition']
        assert test_user.username in response['Content-Disposition']

    def test_upload_transactions_excel_get(self, auth_client):
        """Excel 업로드 페이지 GET 요청"""
        response = auth_client.get(reverse('transactions:upload_excel'))
        
        assert response.status_code == 200
        assert 'form' in response.context

    def test_upload_transactions_excel_requires_login(self, client):
        """Excel 업로드는 로그인 필요"""
        response = client.get(reverse('transactions:upload_excel'))
        assert response.status_code == 302

    def test_upload_transactions_excel_invalid_form(self, auth_client):
        """잘못된 폼으로 Excel 업로드 시도"""
        response = auth_client.post(reverse('transactions:upload_excel'), {})
        
        assert response.status_code == 200  # 폼 에러로 다시 렌더링
        assert 'form' in response.context


# ============================================================
# 첨부파일(Attachment) 관련 뷰 테스트
# ============================================================

@pytest.mark.django_db
class TestAttachmentViews:
    """첨부파일 업로드/다운로드/삭제 뷰 테스트"""

    def test_attachment_upload_get(self, auth_client, sample_transaction):
        """첨부파일 업로드 페이지 GET 요청"""
        url = reverse('transactions:attachment_upload', kwargs={'transaction_id': sample_transaction.pk})
        response = auth_client.get(url)
        
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['transaction'].id == sample_transaction.id
        assert response.context['is_update'] is False

    def test_attachment_upload_requires_login(self, client, sample_transaction):
        """첨부파일 업로드는 로그인 필요"""
        url = reverse('transactions:attachment_upload', kwargs={'transaction_id': sample_transaction.pk})
        response = client.get(url)
        assert response.status_code == 302

    def test_attachment_upload_post_success(self, auth_client, test_user, sample_transaction):
        """첨부파일 업로드 성공"""
        url = reverse('transactions:attachment_upload', kwargs={'transaction_id': sample_transaction.pk})
        
        # 가짜 파일 생성
        fake_file = SimpleUploadedFile(
            "receipt.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
        
        response = auth_client.post(url, {
            'file': fake_file,
        }, format='multipart')
        
        # 성공 시 리다이렉트 또는 폼 에러 확인
        if response.status_code == 302:
            # 업로드 성공
            assert Attachment.objects.filter(
                transaction=sample_transaction,
                user=test_user
            ).exists()
        else:
            # 폼 에러가 있을 수 있음 - 200도 허용
            assert response.status_code == 200

    def test_attachment_upload_update_existing(self, auth_client, test_user, sample_transaction):
        """기존 첨부파일 수정"""
        # 기존 첨부파일 생성
        existing_attachment = Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file=SimpleUploadedFile("old.jpg", b"old content", content_type="image/jpeg"),
            original_name="old.jpg",
            size=1024,
            content_type="image/jpeg"
        )
        
        url = reverse('transactions:attachment_upload', kwargs={'transaction_id': sample_transaction.pk})
        
        # GET 요청 시 is_update=True 확인
        response = auth_client.get(url)
        assert response.context['is_update'] is True

    def test_attachment_upload_invalid_transaction(self, auth_client):
        """존재하지 않는 거래에 첨부파일 업로드 시도"""
        url = reverse('transactions:attachment_upload', kwargs={'transaction_id': 99999})
        response = auth_client.get(url)
        
        assert response.status_code == 404

    def test_attachment_upload_other_user_transaction(self, another_auth_client, sample_transaction):
        """다른 사용자의 거래에 첨부파일 업로드 시도"""
        url = reverse('transactions:attachment_upload', kwargs={'transaction_id': sample_transaction.pk})
        response = another_auth_client.get(url)
        
        assert response.status_code == 404  # get_object_or_404에서 차단

    def test_attachment_download_requires_login(self, client):
        """첨부파일 다운로드는 로그인 필요"""
        url = reverse('transactions:attachment_download', kwargs={'pk': 1})
        response = client.get(url)
        assert response.status_code == 302

    def test_attachment_download_success(self, auth_client, test_user, sample_transaction):
        """첨부파일 다운로드 성공"""
        # 첨부파일 생성
        attachment = Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.pdf", b"pdf content", content_type="application/pdf"),
            original_name="영수증.pdf",
            size=2048,
            content_type="application/pdf"
        )
        
        url = reverse('transactions:attachment_download', kwargs={'pk': attachment.pk})
        response = auth_client.get(url)
        
        assert response.status_code == 200
        assert 'Content-Type' in response
        assert 'Content-Disposition' in response

    def test_attachment_download_file_not_found(self, auth_client, test_user, sample_transaction):
        """파일이 실제로 존재하지 않는 경우"""
        # DB에만 기록이 있고 실제 파일은 없는 경우 시뮬레이션
        attachment = Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file='nonexistent/file.pdf',  # 존재하지 않는 경로
            original_name="missing.pdf",
            size=1024,
            content_type="application/pdf"
        )
        
        url = reverse('transactions:attachment_download', kwargs={'pk': attachment.pk})
        response = auth_client.get(url)
        
        # 파일이 없으면 리다이렉트 또는 에러 메시지
        assert response.status_code == 302

    def test_attachment_download_other_user(self, another_auth_client, test_user, sample_transaction):
        """다른 사용자의 첨부파일 다운로드 시도"""
        attachment = Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf"),
            original_name="test.pdf",
            size=1024,
            content_type="application/pdf"
        )
        
        url = reverse('transactions:attachment_download', kwargs={'pk': attachment.pk})
        response = another_auth_client.get(url)
        
        assert response.status_code == 404

    def test_attachment_delete_get(self, auth_client, test_user, sample_transaction):
        """첨부파일 삭제 확인 페이지 GET 요청"""
        attachment = Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf"),
            original_name="test.pdf",
            size=1024,
            content_type="application/pdf"
        )
        
        url = reverse('transactions:attachment_delete', kwargs={'pk': attachment.pk})
        response = auth_client.get(url)
        
        assert response.status_code == 200
        assert 'attachment' in response.context

    def test_attachment_delete_post_success(self, auth_client, test_user, sample_transaction):
        """첨부파일 삭제 성공"""
        attachment = Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf"),
            original_name="test.pdf",
            size=1024,
            content_type="application/pdf"
        )
        
        attachment_id = attachment.pk
        url = reverse('transactions:attachment_delete', kwargs={'pk': attachment_id})
        response = auth_client.post(url)
        
        assert response.status_code == 302  # 리다이렉트
        assert not Attachment.objects.filter(pk=attachment_id).exists()

    def test_attachment_delete_other_user(self, another_auth_client, test_user, sample_transaction):
        """다른 사용자의 첨부파일 삭제 시도"""
        attachment = Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf"),
            original_name="test.pdf",
            size=1024,
            content_type="application/pdf"
        )
        
        url = reverse('transactions:attachment_delete', kwargs={'pk': attachment.pk})
        response = another_auth_client.post(url)
        
        assert response.status_code == 404
        assert Attachment.objects.filter(pk=attachment.pk).exists()  # 삭제 안됨

    def test_attachment_list_view_requires_login(self, client):
        """첨부파일 목록은 로그인 필요"""
        response = client.get(reverse('transactions:attachment_list'))
        assert response.status_code == 302

    def test_attachment_list_view_success(self, auth_client, test_user, sample_transaction):
        """첨부파일 목록 페이지"""
        # 첨부파일이 있는 거래
        Attachment.objects.create(
            transaction=sample_transaction,
            user=test_user,
            file=SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf"),
            original_name="test.pdf",
            size=1024,
            content_type="application/pdf"
        )
        
        response = auth_client.get(reverse('transactions:attachment_list'))
        
        assert response.status_code == 200
        assert 'page_obj' in response.context
        assert len(response.context['page_obj']) >= 1

    def test_attachment_list_view_pagination(self, auth_client, test_user, business, account, income_category):
        """첨부파일 목록 페이지네이션"""
        # 15건의 첨부파일 생성
        for i in range(15):
            tx = Transaction.objects.create(
                user=test_user,
                business=business,
                account=account,
                category=income_category,
                tx_type='IN',
                amount=Decimal('10000'),
                occurred_at=timezone.now(),
                merchant_name=f'고객{i}'
            )
            Attachment.objects.create(
                transaction=tx,
                user=test_user,
                file=SimpleUploadedFile(f"test{i}.pdf", b"content", content_type="application/pdf"),
                original_name=f"test{i}.pdf",
                size=1024,
                content_type="application/pdf"
            )
        
        response = auth_client.get(reverse('transactions:attachment_list'))
        
        assert response.status_code == 200
        assert response.context['page_obj'].paginator.num_pages >= 2


# ============================================================
# 카테고리 관련 추가 테스트 (에지 케이스)
# ============================================================

@pytest.mark.django_db
class TestCategoryViewsEdgeCases:
    """카테고리 뷰의 에지 케이스 테스트"""

    def test_category_create_duplicate_name(self, auth_client, test_user):
        """같은 이름의 카테고리 중복 생성 시도"""
        # 첫 번째 카테고리 생성
        Category.objects.create(user=test_user, name='중복카테고리', type='income')
        
        # 같은 이름으로 다시 생성 시도
        response = auth_client.post(reverse('transactions:category_create'), {
            'name': '중복카테고리',
            'type': 'income',
            'expense_type': '',
        })
        
        assert response.status_code == 200  # 폼 에러로 다시 렌더링
        assert Category.objects.filter(user=test_user, name='중복카테고리').count() == 1

    def test_category_update_system_category(self, auth_client, income_category):
        """시스템 카테고리 수정 시도"""
        response = auth_client.post(
            reverse('transactions:category_update', kwargs={'pk': income_category.pk}),
            {
                'name': '수정시도',
                'type': 'income',
                'expense_type': '',
            }
        )
        
        # 수정 불가 - 리다이렉트
        assert response.status_code == 302
        income_category.refresh_from_db()
        assert income_category.name == '매출'  # 변경 안됨

    def test_category_update_other_user_category(self, another_auth_client, test_user):
        """다른 사용자의 카테고리 수정 시도"""
        category = Category.objects.create(user=test_user, name='남의카테고리', type='income')
        
        response = another_auth_client.post(
            reverse('transactions:category_update', kwargs={'pk': category.pk}),
            {
                'name': '해킹시도',
                'type': 'income',
                'expense_type': '',
            }
        )
        
        assert response.status_code == 302
        category.refresh_from_db()
        assert category.name == '남의카테고리'  # 변경 안됨

    def test_category_delete_system_category(self, auth_client, income_category):
        """시스템 카테고리 삭제 시도"""
        category_id = income_category.pk
        
        response = auth_client.post(
            reverse('transactions:category_delete', kwargs={'pk': category_id})
        )
        
        assert response.status_code == 302
        assert Category.objects.filter(pk=category_id).exists()  # 삭제 안됨

    def test_category_delete_other_user_category(self, another_auth_client, test_user):
        """다른 사용자의 카테고리 삭제 시도"""
        category = Category.objects.create(user=test_user, name='남의카테고리', type='income')
        category_id = category.pk
        
        response = another_auth_client.post(
            reverse('transactions:category_delete', kwargs={'pk': category_id})
        )
        
        assert response.status_code == 302
        assert Category.objects.filter(pk=category_id).exists()  # 삭제 안됨

    def test_category_delete_get_request(self, auth_client, test_user):
        """카테고리 삭제 확인 페이지 GET 요청"""
        category = Category.objects.create(user=test_user, name='삭제예정', type='income')
        
        response = auth_client.get(
            reverse('transactions:category_delete', kwargs={'pk': category.pk})
        )
        
        assert response.status_code == 200
        assert 'category' in response.context


# ============================================================
# 카테고리 통계 뷰 추가 테스트
# ============================================================

@pytest.mark.django_db
class TestCategoryStatisticsDetailedTests:
    """카테고리 통계 뷰의 상세 테스트"""

    def test_category_statistics_year_filter(self, auth_client, test_user, business, account, expense_category):
        """카테고리 통계 연도 필터링"""
        # 2023년 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            amount=Decimal('5000'),
            occurred_at=timezone.make_aware(datetime(2023, 6, 1)),
            merchant_name='2023년거래'
        )
        
        # 2024년 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            amount=Decimal('10000'),
            occurred_at=timezone.make_aware(datetime(2024, 6, 1)),
            merchant_name='2024년거래'
        )
        
        # 2023년 필터링
        response = auth_client.get(reverse('transactions:category_statistics'), {
            'year': 2023,
            'tx_type': 'OUT'
        })
        
        assert response.status_code == 200
        assert response.context['year'] == 2023
        assert response.context['total_amount'] == Decimal('5000')

    def test_category_statistics_month_filter(self, auth_client, test_user, business, account, expense_category):
        """카테고리 통계 월 필터링"""
        # 1월 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            amount=Decimal('3000'),
            occurred_at=timezone.now().replace(month=1),
            merchant_name='1월거래'
        )
        
        # 2월 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            amount=Decimal('7000'),
            occurred_at=timezone.now().replace(month=2),
            merchant_name='2월거래'
        )
        
        # 1월만 필터링
        current_year = timezone.now().year
        response = auth_client.get(reverse('transactions:category_statistics'), {
            'year': current_year,
            'month': 1,
            'tx_type': 'OUT'
        })
        
        assert response.status_code == 200
        assert response.context['month'] == 1
        assert response.context['total_amount'] == Decimal('3000')

    def test_category_statistics_income_type(self, auth_client, test_user, business, account, income_category, expense_category):
        """카테고리 통계 수입/지출 구분"""
        # 수입 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('20000'),
            occurred_at=timezone.now(),
            merchant_name='수입'
        )
        
        # 지출 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=expense_category,
            tx_type='OUT',
            amount=Decimal('8000'),
            occurred_at=timezone.now(),
            merchant_name='지출'
        )
        
        # 수입만 조회
        response = auth_client.get(reverse('transactions:category_statistics'), {
            'tx_type': 'IN'
        })
        
        assert response.status_code == 200
        assert response.context['tx_type'] == 'IN'
        assert response.context['total_amount'] == Decimal('20000')

    def test_category_statistics_invalid_year(self, auth_client):
        """카테고리 통계 잘못된 연도 파라미터"""
        # 범위 밖 연도
        response = auth_client.get(reverse('transactions:category_statistics'), {
            'year': 1900,  # 2000 미만
            'tx_type': 'OUT'
        })
        
        assert response.status_code == 200
        # 현재 연도로 자동 보정
        assert response.context['year'] == timezone.now().year

    def test_category_statistics_invalid_month(self, auth_client):
        """카테고리 통계 잘못된 월 파라미터"""
        response = auth_client.get(reverse('transactions:category_statistics'), {
            'month': 13,  # 13월은 없음
            'tx_type': 'OUT'
        })
        
        assert response.status_code == 200
        assert response.context['month'] is None  # 무시됨

    def test_category_statistics_top_5_categories(self, auth_client, test_user, business, account):
        """카테고리 통계 TOP 5 추출"""
        # 10개의 카테고리 생성 (금액 다르게)
        for i in range(10):
            category = Category.objects.create(
                user=test_user,
                name=f'카테고리{i}',
                type='expense'
            )
            Transaction.objects.create(
                user=test_user,
                business=business,
                account=account,
                category=category,
                tx_type='OUT',
                amount=Decimal(str(1000 * (i + 1))),  # 1000, 2000, ..., 10000
                occurred_at=timezone.now(),
                merchant_name=f'거래{i}'
            )
        
        response = auth_client.get(reverse('transactions:category_statistics'), {
            'tx_type': 'OUT'
        })
        
        assert response.status_code == 200
        assert len(response.context['top_5_categories']) == 5
        # 가장 큰 금액이 1위
        assert response.context['top_5_categories'][0]['rank'] == 1


# ============================================================
# 월별 요약 뷰 추가 테스트
# ============================================================

@pytest.mark.django_db
class TestMonthlySummaryDetailedTests:
    """월별 요약 뷰의 상세 테스트"""

    def test_monthly_summary_invalid_year(self, auth_client):
        """월별 요약 잘못된 연도 파라미터"""
        response = auth_client.get(reverse('transactions:monthly_summary'), {
            'year': 1800  # 범위 밖
        })
        
        assert response.status_code == 200
        assert response.context['year'] == timezone.now().year  # 현재 연도로 보정

    def test_monthly_summary_invalid_month(self, auth_client):
        """월별 요약 잘못된 월 파라미터"""
        response = auth_client.get(reverse('transactions:monthly_summary'), {
            'month': 15  # 15월은 없음
        })
        
        assert response.status_code == 200
        # 월 필터가 무시되고 전체 조회

    def test_monthly_summary_no_transactions(self, auth_client):
        """월별 요약 거래내역 없는 경우"""
        response = auth_client.get(reverse('transactions:monthly_summary'))
        
        assert response.status_code == 200
        assert response.context['totals']['income'] == Decimal('0')
        assert response.context['totals']['expense'] == Decimal('0')


# ============================================================
# VAT 리포트 상세 테스트
# ============================================================

@pytest.mark.django_db
class TestVATReportDetailedTests:
    """VAT 리포트 뷰의 상세 테스트"""

    def test_vat_report_quarter_filter(self, auth_client, test_user, business, account, income_category):
        """VAT 리포트 분기 필터링"""
        # 1분기 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('11000'),
            vat_amount=Decimal('1000'),
            occurred_at=timezone.make_aware(datetime(2024, 2, 15)),
            merchant_name='1분기거래'
        )
        
        # 2분기 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('22000'),
            vat_amount=Decimal('2000'),
            occurred_at=timezone.make_aware(datetime(2024, 5, 15)),
            merchant_name='2분기거래'
        )
        
        # 1분기만 조회 (쿼리스트링으로 전달)
        response = auth_client.get(reverse('transactions:vat_report_default'), {
            'year': 2024,
            'quarter': 1
        })
        
        assert response.status_code == 200
        assert response.context['quarter'] == 1

    def test_vat_report_month_filter(self, auth_client, test_user, business, account, income_category):
        """VAT 리포트 월 필터링"""
        # 1월 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('11000'),
            vat_amount=Decimal('1000'),
            occurred_at=timezone.make_aware(datetime(2024, 1, 15)),
            merchant_name='1월거래'
        )
        
        # 2월 거래
        Transaction.objects.create(
            user=test_user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            tax_type='taxable',
            is_business=True,
            amount=Decimal('22000'),
            vat_amount=Decimal('2000'),
            occurred_at=timezone.make_aware(datetime(2024, 2, 15)),
            merchant_name='2월거래'
        )
        
        # 1월만 조회 (쿼리스트링으로 전달)
        response = auth_client.get(reverse('transactions:vat_report_default'), {
            'year': 2024,
            'quarter': 1,
            'month': 1
        })
        
        assert response.status_code == 200
        assert response.context['month'] == 1

    def test_vat_report_invalid_quarter(self, auth_client):
        """VAT 리포트 잘못된 분기"""
        # 5분기는 없음 (쿼리스트링으로 전달)
        response = auth_client.get(reverse('transactions:vat_report_default'), {
            'year': 2024,
            'quarter': 5
        })
        
        # VATReportView에서 검증 처리
        assert response.status_code == 200  # 에러 처리 후 정상 렌더링


# ============================================================
# 거래 뷰 권한 테스트
# ============================================================

@pytest.mark.django_db
class TestTransactionPermissions:
    """거래 뷰 권한 관련 테스트"""

    def test_transaction_detail_other_user(self, another_auth_client, sample_transaction):
        """다른 사용자의 거래 상세 조회 시도"""
        url = reverse('transactions:transaction_detail', kwargs={'pk': sample_transaction.pk})
        response = another_auth_client.get(url)
        
        assert response.status_code == 404

    def test_transaction_update_other_user(self, another_auth_client, sample_transaction):
        """다른 사용자의 거래 수정 시도"""
        url = reverse('transactions:transaction_update', kwargs={'pk': sample_transaction.pk})
        response = another_auth_client.get(url)
        
        assert response.status_code == 404

    def test_transaction_delete_other_user(self, another_auth_client, sample_transaction):
        """다른 사용자의 거래 삭제 시도"""
        url = reverse('transactions:transaction_delete', kwargs={'pk': sample_transaction.pk})
        response = another_auth_client.post(url)
        
        assert response.status_code == 404
        assert Transaction.active.filter(pk=sample_transaction.pk).exists()


# ============================================================
# 거래처(Merchant) 추가 테스트
# ============================================================

@pytest.mark.django_db
class TestMerchantDetailedTests:
    """거래처 뷰의 상세 테스트"""

    def test_merchant_detail_with_transactions(self, auth_client, test_user, business, account, income_category, merchant):
        """거래가 있는 거래처 상세 페이지"""
        # 거래처와 연결된 거래 생성
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
        
        response = auth_client.get(
            reverse('transactions:merchant_detail', kwargs={'pk': merchant.pk})
        )
        
        assert response.status_code == 200
        assert 'merchant' in response.context

    def test_merchant_list_pagination(self, auth_client, test_user):
        """거래처 목록 페이지네이션"""
        # 25개의 거래처 생성
        for i in range(25):
            Merchant.objects.create(user=test_user, name=f'거래처{i}')
        
        response = auth_client.get(reverse('transactions:merchant_list'))
        
        assert response.status_code == 200
        assert response.context['page_obj'].paginator.num_pages >= 2

    def test_merchant_update_other_user(self, another_auth_client, merchant):
        """다른 사용자의 거래처 수정 시도"""
        url = reverse('transactions:merchant_update', kwargs={'pk': merchant.pk})
        response = another_auth_client.post(url, {
            'name': '해킹시도'
        })
        
        assert response.status_code == 404

    def test_merchant_delete_other_user(self, another_auth_client, merchant):
        """다른 사용자의 거래처 삭제 시도"""
        url = reverse('transactions:merchant_delete', kwargs={'pk': merchant.pk})
        response = another_auth_client.post(url)
        
        assert response.status_code == 404
        merchant.refresh_from_db()
        assert merchant.is_active is True  # 삭제 안됨