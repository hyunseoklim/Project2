import random
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from apps.businesses.models import Business, Account
from apps.transactions.models import Category, Merchant, Transaction
from decimal import Decimal

# 1. 객체 미리 가져오기 (반복문 안에서 쿼리 방지)
user = User.objects.get(username='admin')
business = Business.objects.get(user=user)
account = Account.objects.get(user=user, business=business)
merchant = Merchant.objects.get_or_create(name="주요 거래처", user=user)[0]

income_cat = Category.objects.get_or_create(name="서비스매출", type="income", user=user)[0]
expense_cat = Category.objects.get_or_create(name="운영비", type="expense", user=user)[0]

year = 2025

for month in range(1, 13):
    transactions_batch = []
    print(f"{month}월 데이터 생성 중...")

    # 수입 5000건
    for i in range(5000):
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
    print(f"{month}월 완료! (현재 누적 약 {month * 5100}건)")

print("모든 데이터 생성이 완료되었습니다!")