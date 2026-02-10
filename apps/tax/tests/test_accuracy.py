"""
Tax 정확성 검증 테스트 (Pytest)

2순위 테스트:
- Decimal 정확성 심화
- 경계값 테스트 심화  
- 금액 계산 정확성
- 부동소수점 오차 방지
"""
import pytest
from decimal import Decimal, ROUND_HALF_UP, getcontext
from apps.tax.utils import (
    calculate_tax,
    calculate_simple_expense_method,
    get_category_tax_impact,
    calculate_next_bracket_distance,
    TAX_BRACKETS_2024,
    SIMPLE_EXPENSE_RATES,
)


class TestDecimalPrecision:
    """Decimal 정확성 심화 검증"""
    
    def test_no_floating_point_errors(self):
        """부동소수점 오차 완전 제거 검증"""
        # 부동소수점으로 문제가 되는 값들
        problematic_values = [
            (Decimal('0.1') + Decimal('0.2'), Decimal('0.3')),  # 0.1 + 0.2 ≠ 0.3 (float)
            (Decimal('1.1') * Decimal('1.1'), Decimal('1.21')),
            (Decimal('0.15') * Decimal('100'), Decimal('15')),
        ]
        
        for calculated, expected in problematic_values:
            assert calculated == expected, \
                f"Decimal 연산은 정확해야 합니다: {calculated} vs {expected}"
    
    def test_tax_calculation_no_rounding_errors(self):
        """세금 계산에서 반올림 오차 없음"""
        # 복잡한 금액들
        test_amounts = [
            Decimal('12345678.99'),
            Decimal('98765432.11'),
            Decimal('33333333.33'),
            Decimal('77777777.77'),
        ]
        
        for amount in test_amounts:
            result = calculate_tax(amount)
            
            # 재계산으로 검증
            recalculated_total = result['tax'] + result['local_tax']
            
            assert recalculated_total == result['total'], \
                f"총 세액 재계산 오차: {amount}"
            
            # 지방소득세 = 국세 × 0.1 (정확히)
            expected_local = (result['tax'] * Decimal('0.1')).quantize(
                Decimal('0.01'), 
                rounding=ROUND_HALF_UP
            )
            assert result['local_tax'] == expected_local, \
                f"지방소득세 계산 오차: {amount}"
    
    def test_decimal_context_precision(self):
        """Decimal 컨텍스트 정밀도 확인"""
        context = getcontext()
        
        # 충분한 정밀도 (최소 28자리)
        assert context.prec >= 28, "Decimal 정밀도가 충분해야 합니다"
        
        # 대용량 금액 계산
        huge_amount = Decimal('999999999999.99')
        result = calculate_tax(huge_amount)
        
        # 오버플로우 없이 계산
        assert result['total'] > Decimal('0')
        assert result['total'] < Decimal('999999999999999')  # 합리적 범위
    
    def test_quantize_consistency(self):
        """모든 금액이 일관된 소수점 2자리"""
        test_incomes = [
            Decimal('10000000.001'),   # 소수점 3자리 입력
            Decimal('50000000.999'),
            Decimal('100000000.5'),
        ]
        
        for income in test_incomes:
            result = calculate_tax(income)
            
            # 모든 결과는 소수점 2자리
            for key in ['tax', 'local_tax', 'total']:
                value = result[key]
                assert value == value.quantize(Decimal('0.01')), \
                    f"{key}는 소수점 2자리여야 합니다: {value}"
    
    def test_simple_expense_decimal_precision(self):
        """단순경비율 계산의 Decimal 정확성"""
        # 복잡한 경비율 (0.45, 0.78 등)
        test_cases = [
            ('it', Decimal('23456789.12'), Decimal('0.45')),
            ('manufacturing', Decimal('34567890.23'), Decimal('0.78')),
        ]
        
        for biz_type, income, rate in test_cases:
            result = calculate_simple_expense_method(income, biz_type)
            
            if result and result['can_use']:
                # 경비 = 수입 × 경비율 (정확히)
                expected_expense = (income * rate).quantize(
                    Decimal('0.01'),
                    rounding=ROUND_HALF_UP
                )
                assert result['expense'] == expected_expense, \
                    f"경비 계산 오차: {biz_type}"
                
                # 소득금액 = 수입 - 경비 (정확히)
                expected_income = (income - expected_expense).quantize(
                    Decimal('0.01'),
                    rounding=ROUND_HALF_UP
                )
                assert result['income_amount'] == expected_income, \
                    f"소득금액 계산 오차: {biz_type}"


class TestBoundaryValues:
    """경계값 테스트 심화"""
    
    @pytest.mark.parametrize("boundary,lower_rate,upper_rate", [
        (Decimal('14000000'), Decimal('0.06'), Decimal('0.15')),
        (Decimal('50000000'), Decimal('0.15'), Decimal('0.24')),
        (Decimal('88000000'), Decimal('0.24'), Decimal('0.35')),
        (Decimal('150000000'), Decimal('0.35'), Decimal('0.38')),
        (Decimal('300000000'), Decimal('0.38'), Decimal('0.40')),
        (Decimal('500000000'), Decimal('0.40'), Decimal('0.42')),
        (Decimal('1000000000'), Decimal('0.42'), Decimal('0.45')),
    ])
    def test_tax_bracket_boundaries_exact(self, boundary, lower_rate, upper_rate):
        """세율 구간 경계값 정확한 세율 적용"""
        # 경계값 정확히
        result_exact = calculate_tax(boundary)
        assert result_exact['rate'] == lower_rate, \
            f"경계값에서는 하위 세율 적용: {boundary}"
        
        # 경계값 + 1원 (다음 구간)
        result_next = calculate_tax(boundary + Decimal('1'))
        assert result_next['rate'] == upper_rate, \
            f"경계값 초과 시 상위 세율 적용: {boundary + 1}"
        
        # 세금 연속성 (급격한 변화 없음)
        tax_diff = result_next['total'] - result_exact['total']
        
        # 1원 차이로 세금이 비합리적으로 증가하지 않음
        # (누진공제로 인해 오히려 부드럽게 증가)
        assert tax_diff < boundary * Decimal('0.01'), \
            f"경계값에서 세금 급증 없음: {tax_diff}"
    
    def test_zero_and_one_won(self):
        """극단값: 0원, 1원"""
        # 0원
        result_zero = calculate_tax(Decimal('0'))
        assert result_zero['total'] == Decimal('0')
        assert result_zero['rate'] == Decimal('0')
        
        # 1원 (최저 과세)
        result_one = calculate_tax(Decimal('1'))
        assert result_one['rate'] == Decimal('0.06')
        
        # 1원의 6% = 0.06원 → 0.01원으로 반올림
        expected_tax = (Decimal('1') * Decimal('0.06')).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP
        )
        assert result_one['tax'] == expected_tax
    
    def test_negative_values_handled(self):
        """음수 값 안전 처리"""
        negative_values = [
            Decimal('-1'),
            Decimal('-1000000'),
            Decimal('-999999999'),
        ]
        
        for value in negative_values:
            result = calculate_tax(value)
            
            # 모든 결과는 0
            assert result['total'] == Decimal('0')
            assert result['tax'] == Decimal('0')
            assert result['local_tax'] == Decimal('0')
    
    @pytest.mark.parametrize("business_type", list(SIMPLE_EXPENSE_RATES.keys()))
    def test_simple_expense_limit_boundaries(self, business_type):
        """단순경비율 한도 경계값"""
        rate_info = SIMPLE_EXPENSE_RATES[business_type]
        limit = rate_info['limit']
        
        # 한도 - 1원 (사용 가능)
        result_ok = calculate_simple_expense_method(
            limit - Decimal('1'),
            business_type
        )
        assert result_ok['can_use'] is True
        
        # 한도 정확히 (사용 가능)
        result_exact = calculate_simple_expense_method(
            limit,
            business_type
        )
        assert result_exact['can_use'] is True
        
        # 한도 + 1원 (사용 불가)
        result_over = calculate_simple_expense_method(
            limit + Decimal('1'),
            business_type
        )
        assert result_over['can_use'] is False
    
    def test_very_large_amounts(self):
        """매우 큰 금액 처리"""
        huge_amounts = [
            Decimal('10000000000'),    # 100억
            Decimal('100000000000'),   # 1,000억
            Decimal('999999999999'),   # 9,999억
        ]
        
        for amount in huge_amounts:
            result = calculate_tax(amount)
            
            # 최고 세율 적용
            assert result['rate'] == Decimal('0.45')
            
            # 계산 오류 없음
            assert result['total'] > Decimal('0')
            assert result['total'] < amount  # 세금이 원금 초과 불가


class TestCalculationAccuracy:
    """금액 계산 정확성"""
    
    def test_tax_formula_accuracy(self):
        """세액 계산식 정확성: 과세표준 × 세율 - 누진공제"""
        test_cases = [
            # (과세표준, 예상 세율, 예상 누진공제)
            (Decimal('20000000'), Decimal('0.15'), Decimal('1260000')),
            (Decimal('70000000'), Decimal('0.24'), Decimal('5760000')),
            (Decimal('100000000'), Decimal('0.35'), Decimal('15440000')),
        ]
        
        for taxable, rate, deduction in test_cases:
            result = calculate_tax(taxable)
            
            # 세율 확인
            assert result['rate'] == rate
            
            # 누진공제 확인
            assert result['deduction'] == deduction
            
            # 세액 = 과세표준 × 세율 - 누진공제
            expected_tax = (taxable * rate - deduction).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )
            expected_tax = max(expected_tax, Decimal('0'))  # 음수 방지
            
            assert result['tax'] == expected_tax, \
                f"세액 계산 오차: {taxable}"
    
    def test_local_tax_always_10_percent(self):
        """지방소득세는 항상 국세의 정확히 10%"""
        test_incomes = [
            Decimal('10000000'),
            Decimal('50000000'),
            Decimal('100000000'),
            Decimal('500000000'),
        ]
        
        for income in test_incomes:
            result = calculate_tax(income)
            
            # 지방소득세 = 국세 × 0.1
            expected_local = (result['tax'] * Decimal('0.1')).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )
            
            assert result['local_tax'] == expected_local, \
                f"지방소득세는 국세의 10%: {income}"
            
            # 총 세액 = 국세 + 지방소득세
            assert result['total'] == result['tax'] + result['local_tax']
    
    def test_simple_expense_income_formula(self):
        """단순경비율: 소득금액 = 수입 - (수입 × 경비율)"""
        test_cases = [
            ('restaurant', Decimal('30000000'), Decimal('0.90')),
            ('it', Decimal('20000000'), Decimal('0.45')),
        ]
        
        for biz_type, income, rate in test_cases:
            result = calculate_simple_expense_method(income, biz_type)
            
            # 경비 = 수입 × 경비율
            expected_expense = (income * rate).quantize(Decimal('0.01'))
            assert result['expense'] == expected_expense
            
            # 소득금액 = 수입 - 경비
            expected_income_amount = (income - expected_expense).quantize(Decimal('0.01'))
            assert result['income_amount'] == expected_income_amount
            
            # 재계산 검증
            recalculated = income - result['expense']
            assert recalculated == result['income_amount']
    
    def test_category_tax_impact_formula(self):
        """카테고리별 절세액 = 경비 × 세율"""
        categories = {
            '인건비': Decimal('10000000'),
            '임차료': Decimal('5000000'),
            '광고비': Decimal('2000000'),
        }
        
        tax_rate = Decimal('0.24')  # 24%
        
        results = get_category_tax_impact(categories, tax_rate)
        
        for item in results:
            category = item['category']
            amount = item['amount']
            tax_saved = item['tax_saved']
            
            # 절세액 = 금액 × 세율
            expected_saved = (amount * tax_rate).quantize(Decimal('0.01'))
            
            assert tax_saved == expected_saved, \
                f"{category} 절세액 계산 오차"
    
    def test_monotonic_increase(self):
        """소득 증가 → 세금 단조증가 (역전 없음)"""
        incomes = []
        for i in range(1000000, 200000000, 5000000):  # 100만원부터 2억까지
            incomes.append(Decimal(str(i)))
        
        taxes = [calculate_tax(income)['total'] for income in incomes]
        
        # 모든 구간에서 단조증가
        for i in range(len(taxes) - 1):
            assert taxes[i] <= taxes[i + 1], \
                f"세금 역전 발생: {incomes[i]} vs {incomes[i+1]}"


class TestNextBracketDistance:
    """다음 세율 구간까지 거리 정확성"""
    
    @pytest.mark.parametrize("current_income,expected_next_limit", [
        (Decimal('10000000'), Decimal('14000000')),   # 1구간 → 2구간
        (Decimal('30000000'), Decimal('50000000')),   # 2구간 → 3구간
        (Decimal('60000000'), Decimal('88000000')),   # 3구간 → 4구간
    ])
    def test_distance_calculation_accuracy(self, current_income, expected_next_limit):
        """거리 계산 정확성"""
        result = calculate_next_bracket_distance(current_income)
        
        assert result is not None
        assert result['next_limit'] == expected_next_limit
        
        # 거리 = 다음 한도 - 현재 소득
        expected_distance = expected_next_limit - current_income
        assert result['distance'] == expected_distance.quantize(Decimal('0.01'))
    
    def test_max_bracket_no_next(self):
        """최고 구간에서는 다음 구간 없음"""
        max_income = Decimal('1500000000')  # 15억 (최고 구간)
        
        result = calculate_next_bracket_distance(max_income)
        
        assert result['is_max'] is True
        assert result['next_rate'] is None
        assert result['distance'] is None


class TestEdgeCasesAccuracy:
    """엣지 케이스 정확성"""
    
    def test_exact_tax_bracket_limits(self):
        """세율 구간 한도 정확히 계산"""
        # TAX_BRACKETS_2024의 한도값들로 계산
        for bracket in TAX_BRACKETS_2024[:-1]:  # 마지막 제외 (무한대)
            limit = bracket['limit']
            rate = bracket['rate']
            
            result = calculate_tax(limit)
            
            # 한도 금액에서는 해당 세율 적용
            assert result['rate'] == rate, \
                f"한도 {limit}에서 세율 {rate} 적용되어야 함"
    
    def test_zero_deduction_effect(self):
        """누진공제 0원인 첫 구간"""
        low_income = Decimal('5000000')  # 500만원 (1구간)
        
        result = calculate_tax(low_income)
        
        # 1구간 누진공제 = 0
        assert result['deduction'] == Decimal('0')
        
        # 세액 = 과세표준 × 6%
        expected_tax = (low_income * Decimal('0.06')).quantize(Decimal('0.01'))
        assert result['tax'] == expected_tax
    
    def test_rounding_consistency(self):
        """반올림 일관성"""
        # 0.5원 반올림 테스트
        test_values = [
            Decimal('10000000.005'),  # 올림
            Decimal('10000000.004'),  # 내림
        ]
        
        for value in test_values:
            result = calculate_tax(value)
            
            # 모든 결과는 ROUND_HALF_UP 규칙 준수
            for key in ['tax', 'local_tax', 'total']:
                val = result[key]
                # 소수점 2자리로 정확히 표현됨
                assert str(val).count('.') <= 1
                if '.' in str(val):
                    decimals = str(val).split('.')[1]
                    assert len(decimals) <= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])