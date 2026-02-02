from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.transactions'  # ← 전체 경로로!