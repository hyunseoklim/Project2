import random
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from apps.businesses.models import Business, Account
from apps.transactions.models import Category, Merchant, Transaction
from decimal import Decimal

# 현재 로그인된 사용자 (id=4)를 위해 데이터 생성
user = User.objects.get(id=4)
print(f"Creating dummy data for user: {user.username}")

# 기존 데이터 확인
business = Business.objects.filter(user=user).first()
if not business:
    print("ERROR: No business found for this user")
    exit(1)

account = Account.objects.filter(user=user, business=business).first()
if not account:
    print("ERROR: No account found for this user")
    exit(1)

# Merchant 생성
merchant = Merchant.objects.get_or_create(name="주요 거래처", user=user)[0]

# Category 생성 또는 가져오기 (이미 존재하는 것 사용)
try:
    income_cat = Category.objects.get(name="서비스매출")
except Category.DoesNotExist:
    income_cat = Category.objects.create(name="서비스매출", type="income")

try:
    expense_cat = Category.objects.get(name="운영비")
except Category.DoesNotExist:
    expense_cat = Category.objects.create(name="운영비", type="expense")

year = 2026

for month in range(1, 13):
    transactions_batch = []
    print(f"{month}월 데이터 생성 중...")

    # 수입 3000건
    for i in range(3000):
        day = random.randint(1, 28)
        occurred_at = timezone.make_aware(datetime(year, month, day, random.randint(9, 23), random.randint(0, 59)))
        transactions_batch.append(Transaction(
            user=user, business=business, account=account, merchant=merchant,
            category=income_cat, tx_type='IN',
            amount=Decimal(random.randrange(1000, 50000, 100)),
            occurred_at=occurred_at, is_business=True
        ))

    # 지출 100건
    for i in range(100):
        day = random.randint(1, 28)
        occurred_at = timezone.make_aware(datetime(year, month, day, random.randint(9, 23), random.randint(0, 59)))
        transactions_batch.append(Transaction(
            user=user, business=business, account=account, merchant=merchant,
            category=expense_cat, tx_type='OUT',
            amount=Decimal(random.randrange(10000, 500000, 1000)),
            occurred_at=occurred_at, is_business=True
        ))

    # 월별로 즉시 저장 (메모리 효율)
    Transaction.objects.bulk_create(transactions_batch, batch_size=1000)
    print(f"{month}월 완료! (현재 누적 약 {month * 3100}건)")

print("모든 데이터 생성이 완료되었습니다!")
print(f"Total transactions created: {Transaction.objects.filter(user=user).count()}")
