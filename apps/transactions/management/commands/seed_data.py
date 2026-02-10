import random
from decimal import Decimal
from datetime import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.utils import timezone
from django.db.models import Q

from apps.businesses.models import Business, Account
from apps.transactions.models import Category, Merchant, Transaction

User = get_user_model()

class Command(BaseCommand):
    help = '업종별 맞춤형 테스트 거래 데이터 생성 (2025-2026)'

    # 1. 업종별 설정 정의 (이 부분만 수정하면 새로운 업종 추가 가능)
    BIZ_CONFIG = {
        'cafe': {
            'biz_name': '테스트 카페',
            'income_cats': ['식음료 판매', '원두 판매', '케이터링'],
            'expense_cats': ['식재료비', '소모품비', '임차료', '인건비(알바)'],
            'merchants': [
                ('스타벅스코리아', '원두'), ('매일유업', '우유'), ('다이소', '소모품'), 
                ('건물주', '월세'), ('일반 고객', '')
            ]
        },
        'retail': {
            'biz_name': '테스트 의류매장',
            'income_cats': ['의류 판매', '잡화 판매', '수선비'],
            'expense_cats': ['상품매입비', '포장재', '임차료', '광고선전비'],
            'merchants': [
                ('동대문도매', '의류'), ('CJ대한통운', '택배'), ('네이버광고', '마케팅'), 
                ('건물주', '월세'), ('일반 고객', '')
            ]
        },
        'it': {
            'biz_name': '테스트 개발사',
            'income_cats': ['유지보수비', '개발 용역비', '구독료'],
            'expense_cats': ['서버비', '소프트웨어 구독', '인건비(직원)', '복리후생'],
            'merchants': [
                ('AWS', '클라우드'), ('JetBrains', 'IDE'), ('슬랙', '협업툴'), 
                ('김개발', '급여'), ('클라이언트A', '')
            ]
        }
    }

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='testuser', help='사용자명')
        parser.add_argument('--year', type=int, nargs='+', default=[2025, 2026], help='생성할 연도')
        parser.add_argument('--transactions-per-month', type=int, default=50, help='월별 거래 건수')
        # 추가된 인자: 업종 선택
        parser.add_argument('--biz-type', type=str, default='cafe', choices=['cafe', 'retail', 'it'], help='업종 선택 (cafe, retail, it)')

    @db_transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        years = options['year']
        txs_per_month = options['transactions_per_month']
        biz_type = options['biz_type']
        
        # 선택된 업종 설정 로드
        config = self.BIZ_CONFIG[biz_type]

        self.stdout.write(f"=== [{biz_type}] 모드로 데이터 생성 시작 ===")
        
        # 1. 사용자
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@example.com', 'first_name': '테스트', 'last_name': '사용자'}
        )
        if created:
            user.set_password('test1234')
            user.save()

        # 2. 사업장 (설정된 이름 사용)
        business, _ = Business.objects.get_or_create(
            user=user,
            name=config['biz_name'],
            defaults={'registration_number': '123-45-67890', 'business_type': biz_type}
        )

        # 3. 계좌
        account, _ = Account.objects.get_or_create(
            user=user,
            business=business,
            name=f'{config["biz_name"]} 주거래',
            defaults={'account_type': 'checking', 'bank_name': '기업은행'}
        )

        # 4. 카테고리 준비 (설정에 있는 카테고리가 없으면 생성해서라도 가져옴)
        income_cats_objs = []
        for cat_name in config['income_cats']:
            c, _ = Category.objects.get_or_create(user=user, name=cat_name, type='income', defaults={'is_system': False})
            income_cats_objs.append(c)

        expense_cats_objs = []
        for cat_name in config['expense_cats']:
            c, _ = Category.objects.get_or_create(user=user, name=cat_name, type='expense', defaults={'is_system': False})
            expense_cats_objs.append(c)

        # 5. 거래처 준비 (설정에 있는 거래처 생성)
        merchants_objs = []
        for name, contact in config['merchants']:
            m, _ = Merchant.objects.get_or_create(
                user=user, name=name, 
                defaults={'business_number': '000-00-00000', 'contact': contact}
            )
            merchants_objs.append(m)

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
                        
                        is_income = random.random() > 0.3  # 지출 비중을 약간 늘림
                        
                        if is_income:
                            category = random.choice(income_cats_objs)
                            amount = Decimal(random.randint(2000, 30000)) * 100
                            # 수입의 경우 마지막 거래처(보통 '일반 고객'이나 '클라이언트') 사용
                            merchant = merchants_objs[-1] 
                            tx_type = 'IN'
                            tax_type = 'taxable'
                            merchant_name = merchant.name
                        else:
                            category = random.choice(expense_cats_objs)
                            tx_type = 'OUT'
                            tax_type = random.choice(['taxable', 'tax_free'])
                            
                            # 특수 카테고리 로직 (이름에 포함되어 있으면 동작)
                            if '인건비' in category.name or '급여' in category.name:
                                if salary_paid: continue
                                amount = Decimal(random.randint(200, 400)) * 10000
                                salary_paid = True
                            elif '임차료' in category.name or '월세' in category.name:
                                if rent_paid: continue
                                amount = Decimal(2000000)
                                rent_paid = True
                            elif '광고' in category.name:
                                amount = Decimal(random.randint(5, 50)) * 10000
                            elif '서버' in category.name:
                                amount = Decimal(random.randint(5, 20)) * 10000
                            else:
                                amount = Decimal(random.randint(50, 500)) * 100
                            
                            # 지출은 '일반 고객'을 제외한 나머지 거래처 중 랜덤
                            merchant = random.choice(merchants_objs[:-1])
                            merchant_name = merchant.name

                        # 날짜 생성
                        naive_datetime = datetime(year, month, day, random.randint(9, 20), random.randint(0, 59))
                        aware_datetime = timezone.make_aware(naive_datetime)

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
                                vat_amount=amount * Decimal('0.1') if tax_type == 'taxable' else Decimal('0'),
                                occurred_at=aware_datetime,
                                is_business=True,
                                memo=f'{category.name} - {year}.{month:02d}.{day:02d}'
                            )
                        )
                        month_created += 1
                        total_created += 1

                        if month_created >= txs_per_month: break
                    if month_created >= txs_per_month: break

        # 저장 및 잔액 업데이트
        if transactions_to_create:
            self.stdout.write(f"💾 {len(transactions_to_create)}건의 거래 저장 중...")
            Transaction.objects.bulk_create(transactions_to_create)
            
            self.stdout.write("💰 계좌 잔액 계산 중...")
            # Django ORM의 aggregate를 사용하여 메모리 효율적으로 계산 (팁 적용)
            from django.db.models import Sum
            
            sums = Transaction.objects.filter(account=account).aggregate(
                total_in=Sum('amount', filter=Q(tx_type='IN')),
                total_out=Sum('amount', filter=Q(tx_type='OUT'))
            )
            
            inflow = sums['total_in'] or Decimal('0')
            outflow = sums['total_out'] or Decimal('0')
            
            account.balance = inflow - outflow
            account.save(update_fields=['balance'])
            
            self.stdout.write(self.style.SUCCESS(
                f"\n🎉 완료! [{biz_type}] 타입 {total_created}건 생성. 잔액: {account.balance:,.0f}원"
            ))