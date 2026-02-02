from django.db import models

# tax/models.py
"""
Tax 앱은 자체 모델을 가지지 않습니다.
Transaction 모델의 tax_type 및 vat_amount 필드를 사용합니다.

주요 기능:
- 부가세 신고 준비 (분기별)
  * 과세/면세/영세율 분류
  * 매출세액 / 매입세액 계산
  
- 종합소득세 준비 (연간)
  * 총 수입금액
  * 카테고리별 필요경비

모든 데이터는 Django ORM 집계 함수를 사용하여 뷰에서 계산됩니다.
"""

# No models needed