"""
Tax Utils 테스트 (Pytest)

핵심 비즈니스 로직:
- calculate_tax() 세율 구간별 계산
- calculate_simple_expense_method() 업종별 경비율 계산
"""
import pytest
from decimal import Decimal
from apps.tax.utils import (
    calculate_tax,
    calculate_simple_expense_method,
    TAX_BRACKETS_2024,
    SIMPLE_EXPENSE_RATES,
)


class TestCalculateTax:
    """세액 계산 함수 테스트"""
    
    @pytest.mark.parametrize("taxable_income,expected_rate,expected_tax_min,expected_tax_max", [
        # (과세표준, 예상세율, 최소세액, 최대세액)
        # 1구간: 1,400만원 이하 (6%)
        (Decimal('10000000'), Decimal('0.06'), Decimal('600000'), Decimal('660000')),
        (Decimal('14000000'), Decimal('0.06'), Decimal('840000'), Decimal('924000')),
        
        # 2구간: 1,400만원 ~ 5,000만원 (15%)
        (Decimal('20000000'), Decimal('0.15'), Decimal('1740000'), Decimal('1914000')),
        (Decimal('50000000'), Decimal('0.15'), Decimal('6240000'), Decimal('6864000')),
        
        # 3구간: 5,000만원 ~ 8,800만원 (24%)
        (Decimal('70000000'), Decimal('0.24'), Decimal('11040000'), Decimal('12144000')),
        (Decimal('88000000'), Decimal('0.24'), Decimal('15360000'), Decimal('16896000')),
        
        # 4구간: 8,800만원 ~ 1.5억원 (35%)
        (Decimal('100000000'), Decimal('0.35'), Decimal('19560000'), Decimal('21516000')),
        (Decimal('150000000'), Decimal('0.35'), Decimal('37060000'), Decimal('40766000')),
        
        # 5구간: 1.5억원 ~ 3억원 (38%)
        (Decimal('200000000'), Decimal('0.38'), Decimal('56060000'), Decimal('61666000')),
        (Decimal('300000000'), Decimal('0.38'), Decimal('94060000'), Decimal('103466000')),
        
        # 6구간: 3억원 ~ 5억원 (40%)
        (Decimal('400000000'), Decimal('0.40'), Decimal('134060000'), Decimal('147466000')),
        (Decimal('500000000'), Decimal('0.40'), Decimal('174060000'), Decimal('191466000')),
        
        # 7구간: 5억원 ~ 10억원 (42%)
        (Decimal('700000000'), Decimal('0.42'), Decimal('258060000'), Decimal('283866000')),
        (Decimal('1000000000'), Decimal('0.42'), Decimal('384060000'), Decimal('422466000')),
        
        # 8구간: 10억원 초과 (45%)
        (Decimal('1500000000'), Decimal('0.45'), Decimal('609060000'), Decimal('669966000')),
        (Decimal('2000000000'), Decimal('0.45'), Decimal('834060000'), Decimal('917466000')),
    ])
    def test_tax_calculation_by_bracket(self, taxable_income, expected_rate, expected_tax_min, expected_tax_max):
        """세율 구간별 정확한 계산 (지방소득세 포함)"""
        result = calculate_tax(taxable_income)
        
        # 세율 확인
        assert result['rate'] == expected_rate, f"세율이 {expected_rate}여야 합니다"
        
        # 총 세액 범위 확인 (국세 + 지방소득세 10%)
        assert expected_tax_min <= result['total'] <= expected_tax_max, \
            f"총 세액이 {expected_tax_min}~{expected_tax_max} 범위여야 합니다 (실제: {result['total']})"
        
        # 지방소득세 = 국세의 10%
        expected_local = result['tax'] * Decimal('0.1')
        assert abs(result['local_tax'] - expected_local) < Decimal('0.01'), \
            "지방소득세는 국세의 10%여야 합니다"
        
        # 총 세액 = 국세 + 지방소득세
        assert result['total'] == result['tax'] + result['local_tax'], \
            "총 세액 = 국세 + 지방소득세"
    
    def test_tax_zero_or_negative(self):
        """0원 또는 음수 입력 시 세금 0원"""
        result_zero = calculate_tax(Decimal('0'))
        assert result_zero['total'] == Decimal('0')
        assert result_zero['tax'] == Decimal('0')
        
        result_negative = calculate_tax(Decimal('-1000000'))
        assert result_negative['total'] == Decimal('0')
        assert result_negative['tax'] == Decimal('0')
    
    @pytest.mark.parametrize("boundary", [
        Decimal('14000000'),   # 1구간 → 2구간
        Decimal('50000000'),   # 2구간 → 3구간
        Decimal('88000000'),   # 3구간 → 4구간
        Decimal('150000000'),  # 4구간 → 5구간
        Decimal('300000000'),  # 5구간 → 6구간
        Decimal('500000000'),  # 6구간 → 7구간
        Decimal('1000000000'), # 7구간 → 8구간
    ])
    def test_tax_boundary_values(self, boundary):
        """세율 구간 경계값에서 정확한 계산"""
        # 경계값 직전
        result_before = calculate_tax(boundary - Decimal('1'))
        
        # 경계값
        result_boundary = calculate_tax(boundary)
        
        # 경계값 직후
        result_after = calculate_tax(boundary + Decimal('1'))
        
        # 경계값 직후는 세율이 같거나 높아야 함
        assert result_after['rate'] >= result_boundary['rate']
        
        # 세금은 단조증가
        assert result_after['total'] > result_boundary['total']
        assert result_boundary['total'] > result_before['total']
    
    def test_tax_decimal_precision(self):
        """Decimal 소수점 2자리 정확성"""
        result = calculate_tax(Decimal('12345678.99'))
        
        # 모든 금액은 소수점 2자리
        assert result['tax'] == result['tax'].quantize(Decimal('0.01'))
        assert result['local_tax'] == result['local_tax'].quantize(Decimal('0.01'))
        assert result['total'] == result['total'].quantize(Decimal('0.01'))
    
    def test_tax_rate_percent_conversion(self):
        """세율 퍼센트 변환 확인"""
        result = calculate_tax(Decimal('20000000'))
        
        # rate는 Decimal, rate_percent는 float
        assert isinstance(result['rate'], Decimal)
        assert isinstance(result['rate_percent'], float)
        
        # 15% = 0.15
        assert result['rate_percent'] == 15.0


class TestCalculateSimpleExpenseMethod:
    """단순경비율 계산 함수 테스트"""
    
    @pytest.mark.parametrize("business_type,total_income,expected_expense_rate", [
        ('restaurant', Decimal('30000000'), Decimal('0.90')),  # 음식점 90%
        ('retail', Decimal('30000000'), Decimal('0.75')),      # 도소매 75%
        ('manufacturing', Decimal('30000000'), Decimal('0.78')),# 제조업 78%
        ('service', Decimal('20000000'), Decimal('0.70')),     # 서비스 70%
        ('it', Decimal('20000000'), Decimal('0.45')),          # IT 45%
        ('education', Decimal('20000000'), Decimal('0.38')),   # 교육 38%
    ])
    def test_simple_expense_calculation(self, business_type, total_income, expected_expense_rate):
        """업종별 경비율 정확한 적용"""
        result = calculate_simple_expense_method(total_income, business_type)
        
        assert result is not None, "결과가 None이 아니어야 합니다"
        assert result['can_use'] is True, "수입 한도 이내이므로 사용 가능해야 합니다"
        
        # 경비율 확인
        assert result['rate'] == expected_expense_rate, \
            f"{business_type}의 경비율은 {expected_expense_rate}여야 합니다"
        
        # 경비 계산 확인
        expected_expense = total_income * expected_expense_rate
        assert result['expense'] == expected_expense.quantize(Decimal('0.01')), \
            "경비는 수입 × 경비율이어야 합니다"
        
        # 소득금액 = 수입 - 경비
        expected_income = total_income - expected_expense
        assert result['income_amount'] == expected_income.quantize(Decimal('0.01')), \
            "소득금액 = 수입 - 경비"
    
    @pytest.mark.parametrize("business_type,over_limit_income", [
        ('restaurant', Decimal('40000000')),  # 한도 3,600만원 초과
        ('retail', Decimal('40000000')),      # 한도 3,600만원 초과
        ('service', Decimal('30000000')),     # 한도 2,400만원 초과
        ('it', Decimal('30000000')),          # 한도 2,400만원 초과
    ])
    def test_simple_expense_over_limit(self, business_type, over_limit_income):
        """수입 한도 초과 시 사용 불가"""
        result = calculate_simple_expense_method(over_limit_income, business_type)
        
        assert result is not None
        assert result['can_use'] is False, "한도 초과 시 사용 불가해야 합니다"
        assert 'reason' in result, "사용 불가 사유가 있어야 합니다"
        assert '초과' in result['reason'], "초과 메시지가 포함되어야 합니다"
    
    def test_simple_expense_invalid_business_type(self):
        """잘못된 업종 코드는 None 반환"""
        result = calculate_simple_expense_method(
            Decimal('30000000'),
            'invalid_type'
        )
        
        assert result is None, "잘못된 업종은 None을 반환해야 합니다"
    
    @pytest.mark.parametrize("business_type", list(SIMPLE_EXPENSE_RATES.keys()))
    def test_simple_expense_all_business_types(self, business_type):
        """모든 업종에 대한 기본 계산 확인"""
        rate_info = SIMPLE_EXPENSE_RATES[business_type]
        
        # 한도 내 수입
        safe_income = rate_info['limit'] - Decimal('1000000')
        
        result = calculate_simple_expense_method(safe_income, business_type)
        
        assert result is not None
        assert result['can_use'] is True
        assert result['business_type_name'] == rate_info['name']
        assert result['rate'] == rate_info['rate']
    
    def test_simple_expense_decimal_precision(self):
        """Decimal 소수점 2자리 정확성"""
        result = calculate_simple_expense_method(
            Decimal('12345678.99'),
            'restaurant'
        )
        
        # 모든 금액은 소수점 2자리
        assert result['expense'] == result['expense'].quantize(Decimal('0.01'))
        assert result['income_amount'] == result['income_amount'].quantize(Decimal('0.01'))
    
    def test_simple_expense_boundary_income(self):
        """수입 한도 경계값 테스트"""
        business_type = 'restaurant'
        limit = SIMPLE_EXPENSE_RATES[business_type]['limit']
        
        # 한도 직전 - 사용 가능
        result_ok = calculate_simple_expense_method(limit - Decimal('1'), business_type)
        assert result_ok['can_use'] is True
        
        # 한도 정확히 - 사용 가능
        result_exact = calculate_simple_expense_method(limit, business_type)
        assert result_exact['can_use'] is True
        
        # 한도 초과 - 사용 불가
        result_over = calculate_simple_expense_method(limit + Decimal('1'), business_type)
        assert result_over['can_use'] is False


class TestTaxCalculationIntegrity:
    """계산 무결성 검증"""
    
    def test_tax_progression_monotonic(self):
        """소득 증가 → 세금 증가 (단조증가)"""
        incomes = [
            Decimal('10000000'),
            Decimal('20000000'),
            Decimal('50000000'),
            Decimal('100000000'),
            Decimal('200000000'),
        ]
        
        taxes = [calculate_tax(income)['total'] for income in incomes]
        
        # 소득이 증가하면 세금도 증가해야 함
        for i in range(len(taxes) - 1):
            assert taxes[i] < taxes[i + 1], \
                f"소득 증가 시 세금도 증가해야 합니다: {taxes[i]} >= {taxes[i+1]}"
    
    def test_simple_vs_actual_logic(self):
        """단순경비율 vs 실제지출 비교 시나리오"""
        total_income = Decimal('30000000')
        actual_expense = Decimal('20000000')  # 실제 지출
        
        # 실제 지출 방식
        actual_income_amount = total_income - actual_expense  # 1,000만원
        
        # 단순경비율 방식 (음식점 90%)
        simple_result = calculate_simple_expense_method(total_income, 'restaurant')
        simple_income_amount = simple_result['income_amount']  # 300만원
        
        # 단순경비율이 훨씬 유리 (소득금액이 적음)
        assert simple_income_amount < actual_income_amount, \
            "이 케이스에서는 단순경비율이 유리해야 합니다"
    
    def test_no_floating_point_errors(self):
        """부동소수점 오차 없음 (Decimal 사용)"""
        # 문제가 될 수 있는 값들
        test_values = [
            Decimal('0.1'),
            Decimal('0.15'),
            Decimal('0.24'),
            Decimal('12345678.99'),
            Decimal('99999999.99'),
        ]
        
        for value in test_values:
            result = calculate_tax(value * Decimal('1000000'))
            
            # Decimal 연산이므로 float 변환 없이 정확해야 함
            reconstructed = result['tax'] + result['local_tax']
            assert reconstructed == result['total'], \
                "Decimal 연산에서 오차가 발생하지 않아야 합니다"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])