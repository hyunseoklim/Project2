from django.db import models

"""
Dashboard 앱은 자체 모델을 가지지 않습니다.
기존 모델(Transaction, Account, Business)의 데이터를 집계합니다.

주요 기능:
- 월별 손익 요약
- 사업장별 비교
- 거래처별 집계
- 카테고리별 분석

모든 데이터는 Django ORM 집계 함수를 사용하여 뷰에서 계산됩니다.
"""