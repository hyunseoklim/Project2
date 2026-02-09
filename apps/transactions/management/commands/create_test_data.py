"""
2025-2026년 테스트 데이터 생성

사용법:
    python manage.py create_test_data
    ID : testuser
    PWD : test1234
"""
import random
from decimal import Decimal
from datetime import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction

from apps.businesses.models import Business, Account
from apps.transactions.models import Category, Merchant, Transaction

from django.db.models import Q

User = get_user_model()


class Command(BaseCommand):
    help = '2025-2026년 테스트 거래 데이터 생성'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='testuser',
            help='사용자명 (기본: testuser)'
        )
        parser.add_argument(
            '--year',
            type=int,
            nargs='+',
            default=[2025, 2026],
            help='생성할 연도 (기본: 2025 2026)'
        )
        parser.add_argument(
            '--transactions-per-month',
            type=int,
            default=50,
            help='월별 거래 건수 (기본: 50)'
        )
    
    @db_transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        years = options['year']
        txs_per_month = options['transactions_per_month']
        
        self.stdout.write(f"=== 테스트 데이터 생성 시작 ===")
        self.stdout.write(f"사용자: {username}")
        self.stdout.write(f"연도: {years}")
        self.stdout.write(f"월별 거래: {txs_per_month}건")
        
        # 1. 사용자 가져오기/생성
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@example.com',
                'first_name': '테스트',
                'last_name': '사용자'
            }
        )
        
        if created:
            user.set_password('test1234')
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✅ 사용자 생성: {username}"))
        else:
            self.stdout.write(f"📌 기존 사용자 사용: {username}")
        
        # 2. 사업장 생성
        business, _ = Business.objects.get_or_create(
            user=user,
            name='테스트 카페',
            defaults={
                'registration_number': '123-45-67890',
                'business_type': '음식점업',
                'location': '서울시 강남구',
            }
        )
        self.stdout.write(f"✅ 사업장: {business.name}")
        
        # 3. 계좌 생성
        account, _ = Account.objects.get_or_create(
            user=user,
            business=business,
            name='기업은행 주거래',
            defaults={
                'account_type': 'checking',
                'bank_name': '기업은행',
                'account_number': '123-456789-01'
            }
        )
        self.stdout.write(f"✅ 계좌: {account.name}")
        
        # 4. 카테고리 - 기존 시드 데이터 활용
        # income 카테고리 가져오기
        income_cats = list(Category.objects.filter(
            Q(is_system=True) | Q(user=user), 
            type='income'
        )[:3])
        if not income_cats:
            self.stdout.write(self.style.ERROR("❌ 수입 카테고리가 없습니다. 시드 데이터를 먼저 로드하세요."))
            return
        
        # expense 카테고리 가져오기
        expense_cats = list(Category.objects.filter(
            Q(is_system=True) | Q(user=user),
            type='expense'
        ))
        if not expense_cats:
            self.stdout.write(self.style.ERROR("❌ 지출 카테고리가 없습니다. 시드 데이터를 먼저 로드하세요."))
            return
        
        self.stdout.write(f"✅ 카테고리: 수입 {len(income_cats)}개, 지출 {len(expense_cats)}개")
        
        # 5. 거래처 생성
        merchants_data = [
            ('원두 공급업체', '스타벅스코리아'),
            ('유제품 공급업체', '남양유업'),
            ('편의점 거래처', 'GS25'),
            ('온라인 구매', '쿠팡'),
            ('일반 고객', ''),
        ]
        
        merchants = []
        for name, contact in merchants_data:
            merchant, _ = Merchant.objects.get_or_create(
                user=user,
                name=name,
                defaults={
                    'business_number': f'{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10000,99999)}',
                    'contact': contact
                }
            )
            merchants.append(merchant)
        
        self.stdout.write(f"✅ 거래처: {len(merchants)}개")
        
        total_created = 0
        transactions_to_create = [] # 1. 생성할 객체를 담을 리스트
        
        for year in years:
            self.stdout.write(f"\n📅 {year}년 데이터 생성 중...")
            year_created = 0
            
            for month in range(1, 13):
                month_created = 0
                
                # 월 고정 지출 발생 여부 체크용 (한 달에 한 번만 발생하도록)
                rent_paid = False
                salary_paid = False

                for day in range(1, 29):
                    # 하루에 1~5건의 거래 발생 (빈도 약간 증가)
                    daily_txs = random.randint(1, 5)
                    
                    for _ in range(daily_txs):
                        # 80% 확률로 수입 발생 (수입 비중을 살짝 더 높임)
                        is_income = random.random() > 0.2 
                        
                        if is_income:
                            # === 수입 거래: 카페 하루 매출 단위로 생각 ===
                            category = random.choice(income_cats)
                            # 금액 상향: 20만 원 ~ 100만 원 (일일 매출 규모)
                            amount = Decimal(random.randint(2000, 10000)) * 100 
                            merchant = merchants[-1]
                            tax_type = 'taxable'
                            tx_type = 'IN'
                            merchant_name = "일반 고객"
                        else:
                            # === 지출 거래 ===
                            category = random.choice(expense_cats)
                            tx_type = 'OUT'
                            tax_type = random.choice(['taxable', 'tax_free'])
                            
                            # 카테고리별 금액 및 발생 빈도 제어
                            if '인건비' in category.name:
                                if not salary_paid: # 월 1회만 발생
                                    amount = Decimal(random.randint(150, 300)) * 10000 
                                    salary_paid = True
                                else: continue # 이미 나갔으면 이번 루프는 스킵
                            elif '임차료' in category.name:
                                if not rent_paid: # 월 1회만 발생
                                    amount = Decimal(2000000)
                                    rent_paid = True
                                else: continue
                            elif '광고' in category.name:
                                amount = Decimal(random.randint(5, 20)) * 10000 # 5~20만원
                            else:
                                # 일반 잡비: 5천원 ~ 5만원
                                amount = Decimal(random.randint(50, 500)) * 100
                            
                            merchant = random.choice(merchants[:-1])
                            merchant_name = merchant.name

                        # 거래 생성 실행
                        transactions_to_create.append(
                            Transaction(
                                user=user,
                                business=business,
                                account=account,
                                category=category,
                                merchant=merchant,
                                merchant_name=merchant_name,
                                tx_type=tx_type,
                                tax_type=tax_type,
                                amount=amount,
                                occurred_at=datetime(year, month, day, random.randint(9, 20), random.randint(0, 59)),
                        )
                    )
                    month_created += 1
                    total_created += 1 # 카운트 증가

                    if month_created >= txs_per_month: break
                if month_created >= txs_per_month: break
                self.stdout.write(f"  {month}월: {month_created}건 생성 완료")
        
        self.stdout.write(self.style.SUCCESS(f"\n🎉 완료! 총 {total_created}건의 거래 생성"))
        self.stdout.write(f"\n접속 정보:")
        self.stdout.write(f"  Username: {username}")
        if created:
            self.stdout.write(f"  Password: test1234")