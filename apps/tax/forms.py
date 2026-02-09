"""
종합소득세 계산 폼
"""
from django import forms
from decimal import Decimal
from datetime import datetime

from .utils import SIMPLE_EXPENSE_RATES


class IncomeTaxCalculationForm(forms.Form):
    """종합소득세 계산 폼 - 간단 버전"""
    
    year = forms.IntegerField(
        label='계산 연도',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='종합소득세를 계산할 연도'
    )
    
    business_type = forms.ChoiceField(
        label='업종 (단순경비율 적용)',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='업종을 선택하면 단순경비율 방식도 비교합니다'
    )
    
    deduction_amount = forms.DecimalField(
        label='소득공제액',
        initial=Decimal('1500000'),
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '100000',
            'placeholder': '1,500,000'
        }),
        help_text='기본공제 150만원 + 추가 공제 (부양가족, 연금보험료 등)'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 연도 선택지 (최근 5년)
        current_year = datetime.now().year
        year_choices = [
            (year, f'{year}년')
            for year in range(current_year, current_year - 5, -1)
        ]
        self.fields['year'].widget.choices = year_choices
        self.fields['year'].initial = current_year - 1  # 작년 기본
        
        # 업종 선택지
        business_choices = [('', '선택 안 함 (실제 지출만 사용)')]
        business_choices.extend([
            (code, f"{info['name']} (경비율 {info['rate']*100:.0f}%)")
            for code, info in SIMPLE_EXPENSE_RATES.items()
        ])
        self.fields['business_type'].choices = business_choices
    
    def clean_year(self):
        """연도 검증"""
        year = self.cleaned_data.get('year')
        current_year = datetime.now().year
        
        if year < 2020 or year > current_year:
            raise forms.ValidationError(f'2020년부터 {current_year}년까지만 선택 가능합니다.')
        
        return year
    
    def clean_deduction_amount(self):
        """소득공제액 검증"""
        amount = self.cleaned_data.get('deduction_amount')
        
        if amount < 0:
            raise forms.ValidationError('소득공제액은 0원 이상이어야 합니다.')
        
        if amount > Decimal('100000000'):  # 1억 초과 방지
            raise forms.ValidationError('소득공제액이 너무 큽니다.')
        
        return amount