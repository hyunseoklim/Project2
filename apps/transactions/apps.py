from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.transactions'  # ← 전체 경로로!

    def ready(self):
    # 이 부분이 없으면 signals.py는 그냥 장식일 뿐입니다.
        import apps.accounts.signals