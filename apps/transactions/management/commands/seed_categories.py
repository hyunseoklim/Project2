from django.core.management.base import BaseCommand
from apps.transactions.models import Category

class Command(BaseCommand):
    help = '기본 카테고리 데이터 생성'

    def handle(self, *args, **kwargs):
        categories = [
            # 수입
            {'name': '매출', 'type': 'income', 'order': 1},
            {'name': '기타수입', 'type': 'income', 'order': 2},
            {'name': '이자수입', 'type': 'income', 'income_type': 'interest', 'order': 3},
            {'name': '임대수입', 'type': 'income', 'income_type': 'rental', 'order': 4},
            {'name': '투자수익', 'type': 'income', 'income_type': 'investment', 'order': 5},
            
            # 지출
            {'name': '인건비', 'type': 'expense', 'expense_type': 'salary', 'order': 1},
            {'name': '임차료', 'type': 'expense', 'expense_type': 'rent', 'order': 2},
            {'name': '광고선전비', 'type': 'expense', 'expense_type': 'advertising', 'order': 3},
            {'name': '소모품비', 'type': 'expense', 'expense_type': 'supplies', 'order': 4},
            {'name': '접대비', 'type': 'expense', 'expense_type': 'entertainment', 'order': 5},
            {'name': '통신비', 'type': 'expense', 'expense_type': 'communication', 'order': 6},
            {'name': '전기·수도·가스비', 'type': 'expense', 'expense_type': 'utilities', 'order': 7},
            {'name': '수선비', 'type': 'expense', 'expense_type': 'repair', 'order': 8},
            {'name': '차량유지비', 'type': 'expense', 'expense_type': 'vehicle', 'order': 9},
            {'name': '보험료', 'type': 'expense', 'expense_type': 'insurance', 'order': 10},
            {'name': '세금과공과', 'type': 'expense', 'expense_type': 'tax', 'order': 11},
            {'name': '기타 경비', 'type': 'expense', 'expense_type': 'other', 'order': 12},
        ]
        
        created = 0
        updated = 0
        for cat_data in categories:
            category, created_flag = Category.objects.update_or_create(
                name=cat_data['name'],
                is_system=True,
                defaults=cat_data
            )
            if created_flag:
                created += 1
            else:
                updated += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ 카테고리 생성: {created}개, 업데이트: {updated}개')
        )