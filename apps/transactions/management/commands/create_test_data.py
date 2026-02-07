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
        income_cats = list(Category.objects.filter(user=user, type='income')[:3])
        if not income_cats:
            self.stdout.write(self.style.ERROR("❌ 수입 카테고리가 없습니다. 시드 데이터를 먼저 로드하세요."))
            return
        
        # expense 카테고리 가져오기
        expense_cats = list(Category.objects.filter(user=user, type='expense')[:8])
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
        
        # 6. 거래 생성
        total_created = 0
        
        for year in years:
            self.stdout.write(f"\n📅 {year}년 데이터 생성 중...")
            year_created = 0
            
            for month in range(1, 13):
                month_created = 0
                
                for day in range(1, 29):  # 1~28일
                    # 하루에 몇 건씩
                    daily_txs = random.randint(1, 3)
                    
                    for _ in range(daily_txs):
                        # 수입 or 지출
                        is_income = random.random() > 0.3  # 70% 수입
                        
                        if is_income:
                            # === 수입 거래 ===
                            category = random.choice(income_cats)
                            amount = Decimal(random.randint(50, 500)) * 100  # 5천~5만원
                            merchant = merchants[-1]  # 수입은 거래처 없음
                            tax_type = 'taxable'
                            tx_type = 'IN'
                            
                        else:
                            # === 지출 거래 ===
                            category = random.choice(expense_cats)
                            
                            # 카테고리별 금액 범위
                            if '인건비' in category.name:
                                amount = Decimal(random.randint(15, 30)) * 100000  # 150~300만원
                            elif '임차료' in category.name:
                                amount = Decimal(2000000)  # 200만원 고정
                            elif '광고' in category.name:
                                amount = Decimal(random.randint(50, 200)) * 1000  # 5~20만원
                            else:
                                amount = Decimal(random.randint(10, 100)) * 1000  # 1만~10만원
                            
                            merchant = random.choice(merchants[:-1])
                            merchant_name = merchant.name
                            tax_type = random.choice(['taxable', 'tax_free'])
                            tx_type = 'OUT'
                        
                        # 거래 생성
                        try:
                            tx = Transaction.objects.create(
                                user=user,
                                business=business,
                                account=account,
                                category=category,
                                merchant=merchant,
                                merchant_name=merchant_name,
                                tx_type=tx_type,
                                tax_type=tax_type,
                                amount=amount,
                                occurred_at=datetime(year, month, day, 
                                                   random.randint(9, 20), 
                                                   random.randint(0, 59)),
                                is_business=True,
                                memo=f'{category.name} - {year}.{month:02d}.{day:02d}'
                            )
                            
                            month_created += 1
                            
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(
                                f"거래 생성 실패: {e} "
                                f"(category={category.name}, type={category.type}, tx_type={tx_type})"
                            ))
                            continue
                        
                        if month_created >= txs_per_month:
                            break
                    
                    if month_created >= txs_per_month:
                        break
                
                year_created += month_created
                self.stdout.write(f"  {month}월: {month_created}건")
            
            total_created += year_created
            self.stdout.write(self.style.SUCCESS(f"✅ {year}년 총 {year_created}건 생성"))
        
        self.stdout.write(self.style.SUCCESS(f"\n🎉 완료! 총 {total_created}건의 거래 생성"))
        self.stdout.write(f"\n접속 정보:")
        self.stdout.write(f"  Username: {username}")
        if created:
            self.stdout.write(f"  Password: test1234")