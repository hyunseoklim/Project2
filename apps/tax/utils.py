"""
종합소득세 계산 유틸리티

TODO: 향후 세율 정보가 빈번하게 변경될 경우,
관리자 페이지에서 수정 가능하도록 DB(Table)화 및 캐싱 로직 도입 검토 예정
"""
from decimal import Decimal
from typing import Dict, Optional, List


# 2024년 종합소득세 세율표
TAX_BRACKETS_2024 = [
    {'limit': Decimal('14000000'), 'rate': Decimal('0.06'), 'deduction': Decimal('0')},
    {'limit': Decimal('50000000'), 'rate': Decimal('0.15'), 'deduction': Decimal('1260000')},
    {'limit': Decimal('88000000'), 'rate': Decimal('0.24'), 'deduction': Decimal('5760000')},
    {'limit': Decimal('150000000'), 'rate': Decimal('0.35'), 'deduction': Decimal('15440000')},
    {'limit': Decimal('300000000'), 'rate': Decimal('0.38'), 'deduction': Decimal('19940000')},
    {'limit': Decimal('500000000'), 'rate': Decimal('0.40'), 'deduction': Decimal('25940000')},
    {'limit': Decimal('1000000000'), 'rate': Decimal('0.42'), 'deduction': Decimal('35940000')},
    {'limit': Decimal('9999999999999'), 'rate': Decimal('0.45'), 'deduction': Decimal('65940000')},  # 무한대 대신 큰 수
]

# 2025년 세율표 (동일)
TAX_BRACKETS_2025 = TAX_BRACKETS_2024.copy()


# 단순경비율 (주요 업종만)
SIMPLE_EXPENSE_RATES = {
    'restaurant': {
        'name': '음식점 및 주점업',
        'rate': Decimal('0.90'),
        'limit': Decimal('36000000')
    },
    'retail': {
        'name': '도소매업',
        'rate': Decimal('0.75'),
        'limit': Decimal('36000000')
    },
    'manufacturing': {
        'name': '제조업',
        'rate': Decimal('0.78'),
        'limit': Decimal('36000000')
    },
    'service': {
        'name': '서비스업',
        'rate': Decimal('0.70'),
        'limit': Decimal('24000000')
    },
    'it': {
        'name': 'IT/정보통신업',
        'rate': Decimal('0.45'),
        'limit': Decimal('24000000')
    },
    'education': {
        'name': '교육 서비스업',
        'rate': Decimal('0.38'),
        'limit': Decimal('24000000')
    },
}


def get_tax_brackets(year: int) -> List[Dict]:
    """연도별 세율표 반환"""
    if year >= 2024:
        return TAX_BRACKETS_2024
    else:
        return TAX_BRACKETS_2024  # 과거 연도도 동일 적용


def calculate_tax(taxable_income: Decimal) -> Dict[str, Decimal]:
    """
    과세표준에 세율 적용
    
    Args:
        taxable_income: 과세표준 (소득금액 - 소득공제)
    
    Returns:
        {
            'tax': 산출세액,
            'rate': 적용 세율,
            'deduction': 누진공제,
            'local_tax': 지방소득세,
            'total': 총 세액
        }
    """
    if taxable_income <= 0:
        return {
            'tax': Decimal('0'),
            'rate': Decimal('0'),
            'deduction': Decimal('0'),
            'local_tax': Decimal('0'),
            'total': Decimal('0')
        }
    
    # 해당 세율 구간 찾기
    for bracket in TAX_BRACKETS_2024:
        if taxable_income <= bracket['limit']:
            tax = (taxable_income * bracket['rate']) - bracket['deduction']
            tax = max(tax, Decimal('0'))  # 음수 방지
            
            local_tax = tax * Decimal('0.1')  # 지방소득세 10%
            total = tax + local_tax
            
            return {
                'tax': tax.quantize(Decimal('0.01')),
                'rate': bracket['rate'],
                'rate_percent': float(bracket['rate'] * 100),
                'deduction': bracket['deduction'],
                'local_tax': local_tax.quantize(Decimal('0.01')),
                'total': total.quantize(Decimal('0.01'))
            }
    
    # 여기 도달하면 안 됨
    return {
        'tax': Decimal('0'),
        'rate': Decimal('0'),
        'deduction': Decimal('0'),
        'local_tax': Decimal('0'),
        'total': Decimal('0')
    }


def calculate_simple_expense_method(
    total_income: Decimal,
    business_type: str
) -> Optional[Dict]:
    """
    단순경비율 방식 계산
    
    Args:
        total_income: 총 수입금액
        business_type: 업종 코드
    
    Returns:
        계산 결과 또는 None (적용 불가 시)
    """
    if business_type not in SIMPLE_EXPENSE_RATES:
        return None
    
    rate_info = SIMPLE_EXPENSE_RATES[business_type]
    
    # 수입 한도 확인
    if total_income > rate_info['limit']:
        return {
            'can_use': False,
            'reason': f"수입금액이 {rate_info['limit']:,.0f}원을 초과합니다",
            'limit': rate_info['limit'],
            'business_type_name': rate_info['name']
        }
    
    # 경비 계산
    expense = total_income * rate_info['rate']
    income_amount = total_income - expense
    
    return {
        'can_use': True,
        'business_type_name': rate_info['name'],
        'rate': rate_info['rate'],
        'rate_percent': float(rate_info['rate'] * 100),
        'expense': expense.quantize(Decimal('0.01')),
        'income_amount': income_amount.quantize(Decimal('0.01')),
        'limit': rate_info['limit']
    }


def get_category_tax_impact(
    categories_data: Dict[str, Decimal],
    avg_tax_rate: Decimal = Decimal('0.15')
) -> List[Dict]:
    """
    카테고리별 절세 효과 계산
    
    Args:
        categories_data: {카테고리명: 금액}
        avg_tax_rate: 평균 세율 (기본 15%)
    
    Returns:
        카테고리별 절세 효과 리스트
    """
    results = []
    
    for category, amount in categories_data.items():
        tax_saved = amount * avg_tax_rate
        
        results.append({
            'category': category or '미분류',
            'amount': amount,
            'tax_saved': tax_saved.quantize(Decimal('0.01'))
        })
    
    # 금액 큰 순으로 정렬
    results.sort(key=lambda x: x['amount'], reverse=True)
    
    return results


def calculate_next_bracket_distance(taxable_income: Decimal) -> Optional[Dict]:
    """
    다음 세율 구간까지 거리 계산
    
    Args:
        taxable_income: 현재 과세표준
    
    Returns:
        다음 구간 정보 또는 None (최고 구간)
    """
    for i, bracket in enumerate(TAX_BRACKETS_2024):
        if taxable_income <= bracket['limit']:
            # 현재 구간
            current_rate = bracket['rate']
            
            # 다음 구간이 있는지 확인
            if i < len(TAX_BRACKETS_2024) - 1:
                next_bracket = TAX_BRACKETS_2024[i + 1]
                distance = bracket['limit'] - taxable_income
                
                return {
                    'current_rate': current_rate,
                    'current_rate_percent': float(current_rate * 100),
                    'next_rate': next_bracket['rate'],
                    'next_rate_percent': float(next_bracket['rate'] * 100),
                    'distance': distance.quantize(Decimal('0.01')),
                    'next_limit': bracket['limit']
                }
            else:
                # 최고 구간
                return {
                    'current_rate': current_rate,
                    'current_rate_percent': float(current_rate * 100),
                    'next_rate': None,
                    'next_rate_percent': None,
                    'distance': None,
                    'next_limit': None,
                    'is_max': True
                }
    
    return None


def get_tax_saving_tip(
    actual_tax: Decimal,
    simple_tax: Optional[Decimal],
    categories: List[Dict]
) -> str:
    """
    절세 팁 생성
    
    Args:
        actual_tax: 실제지출 방식 세금
        simple_tax: 단순경비율 방식 세금
        categories: 카테고리별 데이터
    
    Returns:
        절세 팁 메시지
    """
    tips = []
    
    # 1. 단순경비율 vs 실제지출
    if simple_tax and simple_tax < actual_tax:
        savings = actual_tax - simple_tax
        tips.append(f"💡 단순경비율로 신고하면 {savings:,.0f}원 절세 가능합니다!")
    
    # 2. 경비 추가 팁
    if categories:
        top_category = categories[0]
        additional_expense = Decimal('1000000')  # 100만원
        # 현재는 평균 세율 15%를 기준으로 계산됨, 가장 보편적인 소득구간 (1,400만 ~ 5,000만)
        tax_saved = additional_expense * Decimal('0.15')
        tips.append(
            f"💡 {top_category['category']} 항목에서 경비를 100만원 더 쓰면 "
            f"약 {tax_saved:,.0f}원 세금이 줄어듭니다."
        )
    
    # 3. 기본 공제 팁
    tips.append("💡 부양가족이 있다면 추가 인적공제를 받을 수 있습니다 (1인당 150만원).")
    
    return " ".join(tips)