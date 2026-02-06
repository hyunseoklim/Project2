import openpyxl
from io import BytesIO
from datetime import datetime
from decimal import Decimal
from django.db import transaction, models
from apps.businesses.models import Business, Account
from .models import Transaction, Category

def process_transaction_excel(excel_file, user):
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    success_count = 0

    # 전체를 하나의 트랜잭션으로 묶어 하나라도 실패하면 롤백
    with transaction.atomic():
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row): continue
            
            try:
                # 엑셀 8열 데이터 읽기
                raw_date, b_name, a_number, tx_type_kor, cat_name, m_name, amount, memo = row

                # 1. 사업장 및 계좌 조회
                business = Business.active.filter(user=user, name=b_name).first()
                account = Account.active.filter(user=user, account_number=a_number).first()

                if not account:
                    raise ValueError(f"'{a_number}' 계좌를 찾을 수 없습니다.")

                # 2. 카테고리 조회 (유형 검증을 위해 반드시 필요)
                clean_cat_name = str(cat_name).strip() if cat_name else ""
                category = Category.objects.filter(
                    models.Q(user=user) | models.Q(is_system=True),
                    name=clean_cat_name
                ).first()

                if not category:
                    raise ValueError(f"'{clean_cat_name}' 카테고리가 등록되어 있지 않습니다.")

                # 3. 거래 유형(tx_type) 확정 (모델의 TX_TYPE_CHOICES 'IN'/'OUT' 기준)
                # 엑셀에 적힌 글자보다 '카테고리의 실제 유형'을 우선시하여 에러를 방지합니다.
                actual_tx_type = 'IN' if tx_type_kor == '수입' else 'OUT'

                # 4. 부가세 처리 (int 에러 방지를 위해 Decimal로 변환)
                # amount가 None일 경우를 대비해 0으로 처리합니다.
                current_amount = Decimal(str(amount or 0))
                
                if actual_tx_type == 'OUT':
                    # 지출일 때만 부가세 10% 계산
                    vat_val = (current_amount * Decimal('0.1')).quantize(Decimal('1'))
                else:
                    # 수입일 때는 부가세 0
                    vat_val = Decimal('0')

                # 5. Transaction 객체 생성
                Transaction.active.create(
                    user=user,
                    business=business,
                    account=account,
                    category=category,
                    tx_type=actual_tx_type,
                    tax_type='taxable' if actual_tx_type == 'OUT' else 'tax_free',
                    merchant_name=m_name or (category.name if category else "미지정"),
                    amount=current_amount,  # 여기도 Decimal 적용
                    vat_amount=vat_val,    # 계산된 Decimal 적용
                    occurred_at=raw_date if isinstance(raw_date, datetime) else datetime.strptime(str(raw_date), '%Y-%m-%d %H:%M'),
                    memo=memo or '',
                    is_business=True
                )
                success_count += 1

            except Exception as e:
                # 터미널에 에러 원인 출력
                print(f"🚨 엑셀 {i}행 저장 중 에러 발생: {str(e)}")
                raise ValueError(f"{i}행 저장 실패: {str(e)}")

    return success_count

def generate_transaction_template():
    """사용자용 8열 엑셀 양식 생성"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "거래내역_양식"
    headers = ['거래일시', '사업장명', '계좌번호', '거래유형(수입/지출)', '카테고리', '거래처명', '금액', '메모']
    ws.append(headers)
    
    # 가이드 데이터
    ws.append(['2026-02-06 12:00', '강남본점', '1234-5678-9012', '수입', '테스트', '시드머니', '30000000', '초기자본'])
    ws.append(['YYYY-MM-DD HH:MM', '예시1)', '기존 데이터랑 동일하게', '수입', '수입-카테고리', '시드머니', '30000000', ''])
    ws.append(['YYYY-MM-DD HH:MM', '예시2)', '기존 데이터랑 동일하게', '지출', '지출-카테고리', '시드머니', '30000', '지출은 금액이 잔금을 넘으면 오류'])
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_transactions_to_excel(queryset):
    """
    필터링된 거래 내역(queryset)을 엑셀 파일로 변환합니다.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "거래내역_내보내기"

    # 1. 헤더 작성 (업로드 양식과 동일하게 맞추면 나중에 다시 올리기도 편해요)
    headers = ['거래일시', '사업장명', '계좌번호', '거래유형', '카테고리', '거래처명', '금액', '부가세', '메모']
    ws.append(headers)

    # 2. 데이터 채우기
    for tx in queryset:
        # 날짜 포맷팅 (시간까지)
        occurred_at = tx.occurred_at.strftime('%Y-%m-%d %H:%M') if tx.occurred_at else ''
        
        row = [
            occurred_at,
            tx.business.name if tx.business else '',
            tx.account.account_number if tx.account else '',
            tx.get_tx_type_display(),  # 'IN' 대신 '수입'으로 출력
            tx.category.name if tx.category else '',
            tx.merchant_name or '',
            tx.amount,
            tx.vat_amount or 0,
            tx.memo or ''
        ]
        ws.append(row)

    # 메모리에 저장 후 반환
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output