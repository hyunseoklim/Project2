from django.db import migrations


def seed_system_categories(apps, schema_editor):
    Category = apps.get_model('transactions', 'Category')

    income_names = [
        '매출',
        '이자수익',
        '기타수입',
    ]

    expense_items = [
        ('인건비', 'salary'),
        ('임차료', 'rent'),
        ('광고선전비', 'advertising'),
        ('소모품비', 'supplies'),
        ('접대비', 'entertainment'),
        ('통신비', 'communication'),
        ('전기·수도·가스비', 'utilities'),
        ('수선비', 'repair'),
        ('차량유지비', 'vehicle'),
        ('보험료', 'insurance'),
        ('세금과공과', 'tax'),
        ('기타 경비', 'other'),
    ]

    order = 0
    for name in income_names:
        Category.objects.get_or_create(
            name=name,
            is_system=True,
            defaults={
                'type': 'income',
                'expense_type': None,
                'order': order,
            },
        )
        order += 1

    order = 0
    for name, expense_type in expense_items:
        Category.objects.get_or_create(
            name=name,
            is_system=True,
            defaults={
                'type': 'expense',
                'expense_type': expense_type,
                'order': order,
            },
        )
        order += 1


def unseed_system_categories(apps, schema_editor):
    Category = apps.get_model('transactions', 'Category')
    Category.objects.filter(is_system=True, user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0003_alter_category_name'),
    ]

    operations = [
        migrations.RunPython(seed_system_categories, unseed_system_categories),
    ]
