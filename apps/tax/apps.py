from django.apps import AppConfig


class TaxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tax'  # ← 전체 경로로!