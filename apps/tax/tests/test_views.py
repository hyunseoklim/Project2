"""
Tax Views 테스트 (Pytest)

핵심 비즈니스 로직:
- income_tax_report() 실제지출 vs 단순경비율 비교
- 자동 추천 로직
- 카테고리별 절세 효과
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.urls import reverse

from datetime import datetime, timezone as dt_timezone  # 파이썬 표준 라이브러리
from django.utils import timezone  # 장고 유틸리티

from apps.transactions.models import Transaction, Category
from apps.businesses.models import Business, Account

timezone.utc = dt_timezone.utc
@pytest.fixture
def user(db):
    """테스트 사용자 생성"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def business(db, user):
    """테스트 사업장 생성"""
    return Business.objects.create(
        user=user,
        name='테스트 사업장',
        business_type='음식점',
        branch_type='main'
    )


@pytest.fixture
def account(db, user, business):
    """테스트 계좌 생성"""
    return Account.objects.create(
        user=user,
        business=business,
        name='테스트 계좌',
        bank_name='테스트은행',
        account_number='1234567890',
        balance=Decimal('0')
    )


@pytest.fixture
def income_category(db):
    """수입 카테고리 생성"""
    return Category.objects.create(
        name='매출',
        type='income',
        is_system=True,
        order=1
    )


@pytest.fixture
def expense_categories(db):
    """지출 카테고리들 생성"""
    categories = []
    expense_types = [
        ('인건비', 'salary'),
        ('임차료', 'rent'),
        ('광고선전비', 'advertising'),
        ('소모품비', 'supplies'),
    ]
    
    for idx, (name, exp_type) in enumerate(expense_types):
        cat = Category.objects.create(
            name=name,
            type='expense',
            expense_type=exp_type,
            is_system=True,
            order=idx + 1
        )
        categories.append(cat)
    
    return categories


@pytest.mark.django_db
class TestIncomeTaxReportView:
    """종합소득세 리포트 뷰 테스트"""
    
    def test_login_required(self, client):
        """로그인 필수 확인"""
        url = reverse('tax:income_tax_report')
        response = client.get(url)
        
        # 로그인 페이지로 리다이렉트
        assert response.status_code == 302
        assert 'login' in response.url
    
    def test_no_transactions_message(self, client, user):
        """거래 없는 경우 안내 메시지"""
        client.force_login(user)
        url = reverse('tax:income_tax_report')
        
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'has_data' in response.context
        assert response.context['has_data'] is False
    
    def test_basic_tax_calculation(
        self, 
        client, 
        user, 
        business, 
        account, 
        income_category, 
        expense_categories
    ):
        """기본 세금 계산 로직"""
        client.force_login(user)
        
        # 2024년 거래 생성
        year = 2024
        base_date = datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        # 수입: 5,000만원
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('50000000'),
            occurred_at=base_date,
            merchant_name='고객',
            is_business=True
        )
        
        # 지출: 2,000만원 (카테고리별)
        expenses = [
            ('인건비', Decimal('10000000')),
            ('임차료', Decimal('5000000')),
            ('광고선전비', Decimal('3000000')),
            ('소모품비', Decimal('2000000')),
        ]
        
        for cat_name, amount in expenses:
            cat = next(c for c in expense_categories if c.name == cat_name)
            Transaction.objects.create(
                user=user,
                business=business,
                account=account,
                category=cat,
                tx_type='OUT',
                amount=amount,
                occurred_at=base_date + timedelta(days=1),
                merchant_name='공급업체',
                is_business=True
            )
        
        # 리포트 요청
        url = reverse('tax:income_tax_report')
        response = client.get(url, {'year': year})
        
        assert response.status_code == 200
        assert response.context['has_data'] is True
        
        # 금액 집계 확인
        assert response.context['total_income'] == Decimal('50000000')
        assert response.context['total_expense'] == Decimal('20000000')
        
        # 소득금액 = 수입 - 지출 = 3,000만원
        assert response.context['actual_income_amount'] == Decimal('30000000')
        
        # 과세표준 = 소득금액 - 소득공제(150만원) = 2,850만원
        expected_taxable = Decimal('30000000') - Decimal('1500000')
        assert response.context['actual_taxable'] == expected_taxable
        
        # 세액 계산 확인
        actual_result = response.context['actual_result']
        assert actual_result['total'] > Decimal('0'), "세금이 계산되어야 합니다"
    
    def test_simple_vs_actual_comparison(
        self,
        client,
        user,
        business,
        account,
        income_category,
        expense_categories
    ):
        """실제지출 vs 단순경비율 비교"""
        client.force_login(user)
        
        year = 2024
        base_date = datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        # 수입: 3,000만원
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('30000000'),
            occurred_at=base_date,
            merchant_name='고객',
            is_business=True
        )
        
        # 지출: 2,500만원 (많이 씀)
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=expense_categories[0],
            tx_type='OUT',
            amount=Decimal('25000000'),
            occurred_at=base_date + timedelta(days=1),
            merchant_name='공급업체',
            is_business=True
        )
        
        # 음식점 업종으로 조회 (경비율 90%)
        url = reverse('tax:income_tax_report')
        response = client.get(url, {
            'year': year,
            'business_type': 'restaurant'
        })
        
        assert response.status_code == 200
        
        # 실제지출: 소득금액 = 3,000 - 2,500 = 500만원
        assert response.context['actual_income_amount'] == Decimal('5000000')
        
        # 단순경비율: 경비 = 3,000 × 0.9 = 2,700만원
        #            소득금액 = 3,000 - 2,700 = 300만원
        simple_result = response.context['simple_result']
        assert simple_result is not None
        assert simple_result['can_use'] is True
        assert simple_result['income_amount'] == Decimal('3000000')
        
        # 단순경비율이 유리 (소득금액이 적음)
        assert response.context['recommended'] == 'simple'
        assert response.context['savings'] > Decimal('0')
    
    def test_actual_method_better(
        self,
        client,
        user,
        business,
        account,
        income_category,
        expense_categories
    ):
        """실제지출 방식이 유리한 경우"""
        client.force_login(user)
        
        year = 2024
        base_date = datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        # 수입: 2,000만원
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('20000000'),
            occurred_at=base_date,
            merchant_name='고객',
            is_business=True
        )
        
        # 지출: 1,800만원 (많이 씀)
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=expense_categories[0],
            tx_type='OUT',
            amount=Decimal('18000000'),
            occurred_at=base_date + timedelta(days=1),
            merchant_name='공급업체',
            is_business=True
        )
        
        # IT 업종으로 조회 (경비율 45% - 낮음)
        url = reverse('tax:income_tax_report')
        response = client.get(url, {
            'year': year,
            'business_type': 'it'
        })
        
        # 실제지출: 소득금액 = 2,000 - 1,800 = 200만원
        assert response.context['actual_income_amount'] == Decimal('2000000')
        
        # 단순경비율: 경비 = 2,000 × 0.45 = 900만원
        #            소득금액 = 2,000 - 900 = 1,100만원
        simple_result = response.context['simple_result']
        assert simple_result['income_amount'] == Decimal('11000000')
        
        # 실제지출이 유리 (소득금액이 적음)
        assert response.context['recommended'] == 'actual'
    
    def test_category_tax_impact(
        self,
        client,
        user,
        business,
        account,
        income_category,
        expense_categories
    ):
        """카테고리별 절세 효과 계산"""
        client.force_login(user)
        
        year = 2024
        base_date = datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        # 수입
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('30000000'),
            occurred_at=base_date,
            merchant_name='고객',
            is_business=True
        )
        
        # 지출 (카테고리별 차등)
        expenses = [
            ('인건비', Decimal('10000000')),   # 가장 큼
            ('임차료', Decimal('5000000')),
            ('광고선전비', Decimal('2000000')),
            ('소모품비', Decimal('1000000')),  # 가장 작음
        ]
        
        for cat_name, amount in expenses:
            cat = next(c for c in expense_categories if c.name == cat_name)
            Transaction.objects.create(
                user=user,
                business=business,
                account=account,
                category=cat,
                tx_type='OUT',
                amount=amount,
                occurred_at=base_date + timedelta(days=1),
                merchant_name='공급업체',
                is_business=True
            )
        
        url = reverse('tax:income_tax_report')
        response = client.get(url, {'year': year})
        
        # 카테고리별 절세 효과 확인
        category_impact = response.context['category_impact']
        
        assert len(category_impact) == 4
        
        # 금액 큰 순으로 정렬되어야 함
        assert category_impact[0]['category'] == '인건비'
        assert category_impact[0]['amount'] == Decimal('10000000')
        
        # 절세액 = 금액 × 세율
        assert category_impact[0]['tax_saved'] > Decimal('0')
    
    def test_monthly_cumulative_data(
        self,
        client,
        user,
        business,
        account,
        income_category,
        expense_categories
    ):
        """월별 누적 데이터 생성"""
        client.force_login(user)
        
        year = 2024
        
        # 1월부터 6월까지 거래 생성
        for month in range(1, 7):
            month_date = datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc)
            
            # 매월 수입 500만원
            Transaction.objects.create(
                user=user,
                business=business,
                account=account,
                category=income_category,
                tx_type='IN',
                amount=Decimal('5000000'),
                occurred_at=month_date,
                merchant_name='고객',
                is_business=True
            )
            
            # 매월 지출 300만원
            Transaction.objects.create(
                user=user,
                business=business,
                account=account,
                category=expense_categories[0],
                tx_type='OUT',
                amount=Decimal('3000000'),
                occurred_at=month_date + timedelta(days=1),
                merchant_name='공급업체',
                is_business=True
            )
        
        url = reverse('tax:income_tax_report')
        response = client.get(url, {'year': year})
        
        # 월별 데이터 확인
        monthly_data = response.context['monthly_data']
        
        assert len(monthly_data) == 6, "6개월 데이터가 있어야 합니다"
        
        # 누적 소득금액 확인 (매월 +200만원)
        expected_incomes = [
            Decimal('2000000'),   # 1월: 500-300
            Decimal('4000000'),   # 2월: 누적
            Decimal('6000000'),   # 3월: 누적
            Decimal('8000000'),   # 4월: 누적
            Decimal('10000000'),  # 5월: 누적
            Decimal('12000000'),  # 6월: 누적
        ]
        
        for idx, data in enumerate(monthly_data):
            assert data['month'] == idx + 1
            assert data['income'] == expected_incomes[idx]
            assert data['tax'] > Decimal('0'), f"{idx+1}월 세금이 계산되어야 합니다"
        
        # 마지막 월 세금 확인
        assert response.context['last_month_tax'] == monthly_data[-1]['tax']
    
    def test_different_years(self, client, user, business, account, income_category):
        """연도별 데이터 분리"""
        client.force_login(user)
        
        # 2023년 거래
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000000'),
            occurred_at=datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            merchant_name='고객',
            is_business=True
        )
        
        # 2024년 거래
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('20000000'),
            occurred_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            merchant_name='고객',
            is_business=True
        )
        
        # 2024년 조회
        url = reverse('tax:income_tax_report')
        response_2024 = client.get(url, {'year': 2024})
        
        # 2024년 데이터만 나와야 함
        assert response_2024.context['total_income'] == Decimal('20000000')
        
        # 2023년 조회
        response_2023 = client.get(url, {'year': 2023})
        assert response_2023.context['total_income'] == Decimal('10000000')
    
    def test_deduction_amount_effect(
        self,
        client,
        user,
        business,
        account,
        income_category
    ):
        """소득공제액 변경 시 세금 변화"""
        client.force_login(user)
        
        year = 2024
        
        # 수입 2,000만원
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('20000000'),
            occurred_at=datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            merchant_name='고객',
            is_business=True
        )
        
        url = reverse('tax:income_tax_report')
        
        # 기본 공제 150만원
        response_base = client.get(url, {
            'year': year,
            'deduction_amount': '1500000'
        })
        
        # 추가 공제 300만원
        response_more = client.get(url, {
            'year': year,
            'deduction_amount': '3000000'
        })
        
        # 공제가 많으면 세금이 적어야 함
        tax_base = response_base.context['actual_result']['total']
        tax_more = response_more.context['actual_result']['total']
        
        assert tax_more < tax_base, "공제액이 많으면 세금이 줄어야 합니다"


@pytest.mark.django_db
class TestIncomeTaxReportEdgeCases:
    """엣지 케이스 테스트"""
    
    def test_zero_income(self, client, user):
        """수입이 0원인 경우"""
        client.force_login(user)
        
        url = reverse('tax:income_tax_report')
        response = client.get(url, {'year': 2024})
        
        # 거래가 없으면 has_data=False
        assert response.context['has_data'] is False
    
    def test_loss_situation(
        self,
        client,
        user,
        business,
        account,
        income_category,
        expense_categories
    ):
        """지출이 수입보다 많은 경우 (적자)"""
        client.force_login(user)
        
        year = 2024
        base_date = datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        # 수입 1,000만원
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('10000000'),
            occurred_at=base_date,
            merchant_name='고객',
            is_business=True
        )
        
        # 지출 1,500만원 (적자!)
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=expense_categories[0],
            tx_type='OUT',
            amount=Decimal('15000000'),
            occurred_at=base_date + timedelta(days=1),
            merchant_name='공급업체',
            is_business=True
        )
        
        url = reverse('tax:income_tax_report')
        response = client.get(url, {'year': year})
        
        # 소득금액이 음수
        assert response.context['actual_income_amount'] == Decimal('-5000000')
        
        # 과세표준은 0 (음수는 0으로 처리)
        assert response.context['actual_taxable'] == Decimal('0')
        
        # 세금도 0
        assert response.context['actual_result']['total'] == Decimal('0')
    
    def test_large_amounts(
        self,
        client,
        user,
        business,
        account,
        income_category
    ):
        """대용량 금액 처리 (10억 이상)"""
        client.force_login(user)
        
        year = 2024
        
        # 수입 20억원
        Transaction.objects.create(
            user=user,
            business=business,
            account=account,
            category=income_category,
            tx_type='IN',
            amount=Decimal('2000000000'),
            occurred_at=datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            merchant_name='대형 고객',
            is_business=True
        )
        
        url = reverse('tax:income_tax_report')
        response = client.get(url, {'year': year})
        
        assert response.status_code == 200
        assert response.context['total_income'] == Decimal('2000000000')
        
        # 최고 세율 구간 (45%)
        assert response.context['actual_result']['rate'] == Decimal('0.45')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])