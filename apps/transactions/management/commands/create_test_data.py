import random
from decimal import Decimal
from datetime import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.utils import timezone  # 시간대 처리를 위해 추가

from apps.businesses.models import Business, Account
from apps.transactions.models import Category, Merchant, Transaction
from django.db.models import Q

User = get_user_model()

class Command(BaseCommand):
    help = '2025-2026년 테스트 거래 데이터 생성'
    
    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='testuser', help='사용자명')
        parser.add_argument('--year', type=int, nargs='+', default=[2025, 2026], help='생성할 연도')
        parser.add_argument('--transactions-per-month', type=int, default=50, help='월별 거래 건수')
    
    @db_transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        years = options['year']
        txs_per_month = options['transactions_per_month']
        
        self.stdout.write(f"=== 테스트 데이터 생성 시작 ===")
        
        # 1. 사용자
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@example.com', 'first_name': '테스트', 'last_name': '사용자'}
        )
        if created:
            user.set_password('test1234')
            user.save()

        # 2. 사업장
        business, _ = Business.objects.get_or_create(
            user=user,
            name='테스트 카페',
            defaults={'registration_number': '123-45-67890', 'business_type': '음식점업'}
        )

        # 3. 계좌
        account, _ = Account.objects.get_or_create(
            user=user,
            business=business,
            name='기업은행 주거래',
            defaults={'account_type': 'checking', 'bank_name': '기업은행'}
        )

        # 4. 카테고리
        income_cats = list(Category.objects.filter(Q(is_system=True) | Q(user=user), type='income')[:3])
        expense_cats = list(Category.objects.filter(Q(is_system=True) | Q(user=user), type='expense'))
        
        if not income_cats or not expense_cats:
            self.stdout.write(self.style.ERROR("❌ 카테고리 데이터가 부족합니다."))
            return

        # 5. 거래처
        merchants_data = [('스타벅스코리아', '원두'), ('남양유업', '우유'), ('GS25', '편의점'), ('쿠팡', '비품'), ('일반 고객', '')]
        merchants = []
        for name, contact in merchants_data:
            m, _ = Merchant.objects.get_or_create(
                user=user, name=name, 
                defaults={'business_number': '000-00-00000', 'contact': contact}
            )
            merchants.append(m)

        # === 데이터 생성 로직 ===
        transactions_to_create = [] 
        total_created = 0

        
        for year in years:
            self.stdout.write(f"📅 {year}년 데이터 준비 중...")
            for month in range(1, 13):
                month_created = 0
                rent_paid = False
                salary_paid = False

                for day in range(1, 29):
                    daily_txs = random.randint(1, 5)
                    for _ in range(daily_txs):
                        
                        # 확률 및 로직 (기존과 동일)
                        is_income = random.random() > 0.2
                        
                        if is_income:
                            category = random.choice(income_cats)
                            amount = Decimal(random.randint(2000, 10000)) * 100
                            merchant = merchants[-1]
                            tx_type = 'IN'
                            tax_type = 'taxable'
                            merchant_name = "일반 고객"
                        else:
                            category = random.choice(expense_cats)
                            tx_type = 'OUT'
                            tax_type = random.choice(['taxable', 'tax_free'])
                            
                            if '인건비' in category.name:
                                if salary_paid: continue
                                amount = Decimal(random.randint(150, 300)) * 10000
                                salary_paid = True
                            elif '임차료' in category.name:
                                if rent_paid: continue
                                amount = Decimal(2000000)
                                rent_paid = True
                            elif '광고' in category.name:
                                amount = Decimal(random.randint(5, 20)) * 10000
                            else:
                                amount = Decimal(random.randint(50, 500)) * 100
                            
                            merchant = random.choice(merchants[:-1])
                            merchant_name = merchant.name

                        # 날짜 생성 (timezone aware로 변환)
                        naive_datetime = datetime(year, month, day, random.randint(9, 20), random.randint(0, 59))
                        aware_datetime = timezone.make_aware(naive_datetime)

                        # 리스트에 객체 추가 (저장 X)
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
                                vat_amount=amount * Decimal('0.1') if tax_type == 'taxable' else Decimal('0'),  # 추가!
                                occurred_at=aware_datetime, # 수정됨
                                is_business=True,
                                memo=f'{category.name} - {year}.{month:02d}.{day:02d}'
                            )
                        )
                        month_created += 1
                        total_created += 1

                        if month_created >= txs_per_month: break
                    if month_created >= txs_per_month: break

        # === 데이터 생성 로직 ===
        transactions_to_create = [] 
        total_created = 0

        # === 여기가 핵심입니다 ===
        if transactions_to_create:
            self.stdout.write(f"💾 {len(transactions_to_create)}건의 거래 저장 중...")
            Transaction.objects.bulk_create(transactions_to_create)
            
            # 계좌 잔액 재계산
            self.stdout.write("💰 계좌 잔액 계산 중...")
            all_txs = Transaction.objects.filter(account=account).order_by('occurred_at')
            
            account.balance = Decimal('0')
            for tx in all_txs:
                if tx.tx_type == 'IN':
                    account.balance += tx.amount
                else:
                    account.balance -= tx.amount
            
            account.save(update_fields=['balance'])
            
            self.stdout.write(self.style.SUCCESS(
                f"\n🎉 완료! 총 {total_created}건의 거래 저장 + 잔액 {account.balance:,.0f}원 업데이트"
            ))
        for year in years:
            self.stdout.write(f"📅 {year}년 데이터 준비 중...")
            for month in range(1, 13):
                month_created = 0
                rent_paid = False
                salary_paid = False

                for day in range(1, 29):
                    daily_txs = random.randint(1, 5)
                    for _ in range(daily_txs):
                        
                        # 확률 및 로직 (기존과 동일)
                        is_income = random.random() > 0.2
                        
                        if is_income:
                            category = random.choice(income_cats)
                            amount = Decimal(random.randint(2000, 10000)) * 100
                            merchant = merchants[-1]
                            tx_type = 'IN'
                            tax_type = 'taxable'
                            merchant_name = "일반 고객"
                        else:
                            category = random.choice(expense_cats)
                            tx_type = 'OUT'
                            tax_type = random.choice(['taxable', 'tax_free'])
                            
                            if '인건비' in category.name:
                                if salary_paid: continue
                                amount = Decimal(random.randint(150, 300)) * 10000
                                salary_paid = True
                            elif '임차료' in category.name:
                                if rent_paid: continue
                                amount = Decimal(2000000)
                                rent_paid = True
                            elif '광고' in category.name:
                                amount = Decimal(random.randint(5, 20)) * 10000
                            else:
                                amount = Decimal(random.randint(50, 500)) * 100
                            
                            merchant = random.choice(merchants[:-1])
                            merchant_name = merchant.name

                        # 날짜 생성 (timezone aware로 변환)
                        naive_datetime = datetime(year, month, day, random.randint(9, 20), random.randint(0, 59))
                        aware_datetime = timezone.make_aware(naive_datetime)

                        # 리스트에 객체 추가 (저장 X)
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
                                vat_amount=amount * Decimal('0.1') if tax_type == 'taxable' else Decimal('0'),  # 추가!
                                occurred_at=aware_datetime, # 수정됨
                                is_business=True,
                                memo=f'{category.name} - {year}.{month:02d}.{day:02d}'
                            )
                        )
                        month_created += 1
                        total_created += 1

                        if month_created >= txs_per_month: break
                    if month_created >= txs_per_month: break

        # 2️⃣ 모든 데이터 생성 완료 후 한 번에 저장
        if transactions_to_create:
            self.stdout.write(f"💾 {len(transactions_to_create)}건의 거래 저장 중...")
            Transaction.objects.bulk_create(transactions_to_create)
            
            # 계좌 잔액 재계산
            self.stdout.write("💰 계좌 잔액 계산 중...")
            all_txs = Transaction.objects.filter(account=account).order_by('occurred_at')
            
            account.balance = Decimal('0')
            for tx in all_txs:
                if tx.tx_type == 'IN':
                    account.balance += tx.amount
                else:
                    account.balance -= tx.amount
            
            account.save(update_fields=['balance'])
            
            self.stdout.write(self.style.SUCCESS(
                f"\n🎉 완료! 총 {total_created}건의 거래 저장 + 잔액 {account.balance:,.0f}원 업데이트"
            ))