from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.businesses.models import Business, Account
from apps.transactions.models import Transaction, Merchant, Category

User = get_user_model()

class Command(BaseCommand):
    help = '테스트용으로 생성된 모든 데이터를 삭제합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='testuser')

    def handle(self, *args, **options):
        username = options['username']
        self.stdout.write(f"⚠️ {username}의 데이터를 삭제하기 시작합니다...")

        try:
            user = User.objects.get(username=username)
            
            # Cascade 설정에 따라 관련 데이터가 자동으로 지워질 수도 있지만,
            # 명시적으로 지워주는 것이 가장 확실합니다.
            count, _ = Transaction.objects.filter(user=user).delete()
            self.stdout.write(f"- 삭제된 거래: {count}건")
            
            Merchant.objects.filter(user=user).delete()
            Account.objects.filter(user=user).delete()
            Business.objects.filter(user=user).delete()
            Category.objects.filter(user=user, is_system=False).delete()
            
            self.stdout.write(self.style.SUCCESS(f"✅ {username} 관련 모든 데이터 삭제 완료!"))
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ '{username}' 사용자를 찾을 수 없습니다."))