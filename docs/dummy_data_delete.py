from apps.transactions.models import Transaction, Category, Merchant
from apps.businesses.models import Business, Account

# 1. 거래 내역 삭제 (가장 하위 데이터)
Transaction.objects.all().delete()

# 2. 관련 정보 삭제
Category.objects.all().delete()
Merchant.objects.all().delete()
Account.objects.all().delete()

# 3. 사업자 삭제 (상위 데이터)
Business.objects.all().delete()

print("연습용 데이터가 모두 삭제되었습니다.")