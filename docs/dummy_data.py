import random
from django.utils import timezone
from django.contrib.auth.models import User
from apps.businesses.models import Business, Account
from apps.transactions.models import Category, Merchant, Transaction
from decimal import Decimal

# 1. 유저 생성 (없으면 생성)
user, created = User.objects.get_or_create(username='admin')
if created:
    user.set_password('password123')
    user.save()

# 2. 사업자(Business) 생성 (다른 앱 모델)
business, _ = Business.objects.get_or_create(
    user=user,
    name="내 연습용 가게",
    defaults={'registration_number': '123-45-67890'}
)

# 3. 계좌(Account) 생성 (다른 앱 모델)
account, _ = Account.objects.get_or_create(
    user=user,
    business=business,
    name="주거래 은행",
    defaults={'balance': Decimal('1000000')} # 초기 잔액 100만 원
)

# 4. 카테고리(Category) 생성
income_cat, _ = Category.objects.get_or_create(name="일반매출", type="income", user=user)
expense_cat, _ = Category.objects.get_or_create(
    name="재료비", type="expense", expense_type="supplies", user=user
)

# 5. 거래처(Merchant) 생성
merchant, _ = Merchant.objects.get_or_create(name="연습용 공급처", user=user)

# 6. 거래 내역(Transaction) 30개 생성
for i in range(30):
    tx_type = random.choice(['IN', 'OUT'])
    amount = Decimal(random.randrange(5000, 50000, 500))
    
    Transaction.active.create(
        user=user,
        business=business,
        account=account,
        merchant=merchant,
        category=income_cat if tx_type == 'IN' else expense_cat,
        tx_type=tx_type,
        amount=amount,
        occurred_at=timezone.now() - timezone.timedelta(days=random.randint(0, 30)),
        tax_type='taxable',
        is_business=True,
        memo=f"자동 생성된 거래 {i+1}"
    )

print("모든 연관 데이터와 거래 내역 30개가 생성되었습니다!")