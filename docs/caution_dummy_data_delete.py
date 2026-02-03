from apps.transactions.models import Transaction
print(f"삭제 전 개수: {Transaction.objects.count()}")
Transaction.objects.all().delete()
print(f"삭제 후 개수: {Transaction.objects.count()}")