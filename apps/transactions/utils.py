import openpyxl
from io import BytesIO
from datetime import datetime
from decimal import Decimal
from django.db import transaction, models
from apps.businesses.models import Business, Account
from .models import Transaction, Category, Merchant

def process_transaction_excel(excel_file, user):
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    success_count = 0
    
    # 자동 생성된 항목 추적
    auto_created = {
        'accounts': [],
        'businesses': [],
        'merchants': [],
        'categories_matched': []
    }

    # 전체를 하나의 트랜잭션으로 묶어 하나라도 실패하면 롤백
    with transaction.atomic():
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row): 
                continue
            
            try:
                # 엑셀 8열 데이터 읽기
                raw_date, b_name, a_number, tx_type_kor, cat_name, m_name, amount, memo = row

                # ========================================
                # 1. 사업장 처리 (자동 생성 or 기본값)
                # ========================================
                if b_name:
                    business, created = Business.active.get_or_create(
                        user=user,
                        name=b_name.strip(),
                        defaults={
                            'registration_number': '',
                            'business_type': '미등록',
                            'location': '엑셀 업로드',
                        }
                    )
                    if created:
                        auto_created['businesses'].append(b_name)
                else:
                    # 사업장명 없으면 첫 번째 사업장 사용
                    business = Business.active.filter(user=user).first()
                    if not business:
                        raise ValueError(f"{i}행: 사업장이 없습니다. 먼저 사업장을 생성하세요.")

                # ========================================
                # 2. 계좌 처리 (자동 생성!)
                # ========================================
                a_number_clean = str(a_number).strip() if a_number else ""
                
                if not a_number_clean:
                    raise ValueError(f"{i}행: 계좌번호가 비어있습니다.")
                
                account, created = Account.active.get_or_create(
                    user=user,
                    account_number=a_number_clean,
                    defaults={
                        'business': business,
                        'name': f'엑셀 업로드 계좌 ({a_number_clean})',
                        'bank_name': '미등록',
                        'account_type': 'checking',
                        'balance': Decimal('0')
                    }
                )
                
                if created:
                    auto_created['accounts'].append(a_number_clean)

                # ========================================
                # 3. 거래 유형 확정
                # ========================================
                actual_tx_type = 'IN' if tx_type_kor and '수입' in str(tx_type_kor) else 'OUT'

                # ========================================
                # 4. 카테고리 처리 (똑똑한 매칭!)
                # ========================================
                clean_cat_name = str(cat_name).strip() if cat_name else ""
                category = None
                
                if clean_cat_name:
                    # 정확히 일치하는 카테고리 찾기
                    category = Category.objects.filter(
                        models.Q(user=user) | models.Q(is_system=True),
                        name=clean_cat_name
                    ).first()
                    
                    # 없으면 부분 일치 시도
                    if not category:
                        category = Category.objects.filter(
                            models.Q(user=user) | models.Q(is_system=True),
                            name__icontains=clean_cat_name
                        ).first()
                        
                        if category:
                            auto_created['categories_matched'].append(
                                f"{clean_cat_name} → {category.name}"
                            )
                
                # 그래도 없으면 기본 카테고리 사용
                if not category:
                    category_type = 'income' if actual_tx_type == 'IN' else 'expense'
                    category = Category.objects.filter(
                        models.Q(user=user) | models.Q(is_system=True),
                        type=category_type
                    ).first()
                    
                    if not category:
                        raise ValueError(
                            f"{i}행: '{clean_cat_name}' 카테고리를 찾을 수 없고, "
                            f"기본 카테고리도 없습니다. 먼저 카테고리를 생성하세요."
                        )
                    
                    auto_created['categories_matched'].append(
                        f"{clean_cat_name} → {category.name} (기본값)"
                    )

                # ========================================
                # 5. 거래처 처리 (자동 생성!)
                # ========================================
                merchant = None
                merchant_name_clean = str(m_name).strip() if m_name else ""
                
                if merchant_name_clean:
                    merchant, created = Merchant.objects.get_or_create(
                        user=user,
                        name=merchant_name_clean,
                        defaults={
                            'business_number': '',
                            'contact': '',
                        }
                    )
                    if created:
                        auto_created['merchants'].append(merchant_name_clean)

                # ========================================
                # 6. 금액 및 부가세 처리
                # ========================================
                current_amount = Decimal(str(amount or 0))
                
                if current_amount <= 0:
                    raise ValueError(f"{i}행: 금액은 0보다 커야 합니다.")
                
                # 부가세는 save() 메서드에서 자동 계산됨
                # (지출이고 taxable이면 자동 계산)
                vat_val = Decimal('0')

                # ========================================
                # 7. 날짜 처리
                # ========================================
                if isinstance(raw_date, datetime):
                    occurred_at = raw_date
                else:
                    try:
                        # 여러 날짜 형식 시도
                        date_str = str(raw_date).strip()
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y/%m/%d']:
                            try:
                                occurred_at = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            raise ValueError(f"날짜 형식 오류: {date_str}")
                    except Exception as e:
                        raise ValueError(f"{i}행: 날짜 형식이 잘못되었습니다. ({raw_date})")

                # ========================================
                # 8. Transaction 생성
                # ========================================
                Transaction.objects.create(
                    user=user,
                    business=business,
                    account=account,
                    category=category,
                    merchant=merchant,
                    tx_type=actual_tx_type,
                    tax_type='taxable' if actual_tx_type == 'OUT' else 'tax_free',
                    merchant_name=merchant_name_clean or (category.name if category else ""),
                    amount=current_amount,
                    occurred_at=occurred_at,
                    memo=memo or '',
                    is_business=True
                )
                success_count += 1

            except Exception as e:
                # 터미널에 에러 원인 출력
                print(f"🚨 엑셀 {i}행 저장 중 에러 발생: {str(e)}")
                raise ValueError(f"{i}행 저장 실패: {str(e)}")

    # 자동 생성 요약 반환
    return {
        'success_count': success_count,
        'auto_created': auto_created
    }


def generate_transaction_template():
    """사용자용 8열 엑셀 양식 생성"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "거래내역_양식"
    headers = ['거래일시', '사업장명', '계좌번호', '거래유형(수입/지출)', '카테고리', '거래처명', '금액', '메모']
    ws.append(headers)
    
    # 가이드 데이터
    ws.append(['2026-02-06 12:00', '강남본점', '1234-5678-9012', '수입', '매출', '일반고객', '50000', '커피 판매'])
    ws.append(['2026-02-06 14:30', '강남본점', '1234-5678-9012', '지출', '인건비', '직원급여', '2000000', '월급'])
    ws.append(['', '※ 없는 계좌/거래처는 자동 생성됩니다', '', '', '', '', '', ''])
    
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

    # 1. 헤더 작성
    headers = ['거래일시', '사업장명', '계좌번호', '거래유형', '카테고리', '거래처명', '금액', '부가세', '메모']
    ws.append(headers)

    # 2. 데이터 채우기
    for tx in queryset:
        occurred_at = tx.occurred_at.strftime('%Y-%m-%d %H:%M') if tx.occurred_at else ''
        
        row = [
            occurred_at,
            tx.business.name if tx.business else '',
            tx.account.account_number if tx.account else '',
            tx.get_tx_type_display(),
            tx.category.name if tx.category else '',
            tx.merchant_name or '',
            tx.amount,
            tx.vat_amount or 0,
            tx.memo or ''
        ]
        ws.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output