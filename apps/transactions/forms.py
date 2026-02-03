from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Transaction, Merchant, Category
from apps.businesses.models import Account, Business


class TransactionForm(forms.ModelForm):
    """거래 입력/수정 폼"""
    
    class Meta:
        model = Transaction
        fields = [
            'business', 'account', 'merchant', 'merchant_name', 'category',
            'tx_type', 'tax_type', 'is_business', 'amount', 'vat_amount',
            'occurred_at', 'memo'
        ]
        widgets = {
            'occurred_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'memo': forms.Textarea(attrs={'rows': 3}),
            'amount': forms.NumberInput(attrs={'step': '0.01'}),
            'vat_amount': forms.NumberInput(attrs={'step': '0.01'}),
        }
        labels = {
            'business': '사업장',
            'account': '계좌',
            'merchant': '거래처',
            'merchant_name': '거래처명 (직접입력)',
            'category': '카테고리',
            'tx_type': '거래 유형',
            'tax_type': '부가세 유형',
            'is_business': '사업용 거래',
            'amount': '금액',
            'vat_amount': '부가세',
            'occurred_at': '거래일시',
            'memo': '메모',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 사용자별 필터링
        if self.user:
            self.fields['business'].queryset = Business.objects.filter(user=self.user, is_active=True)
            self.fields['account'].queryset = Account.objects.filter(user=self.user, is_active=True)
            self.fields['merchant'].queryset = Merchant.objects.filter(user=self.user, is_active=True)
        
        # 필드 선택사항 설정
        self.fields['merchant'].required = False
        self.fields['merchant_name'].required = False
        self.fields['business'].required = False
        self.fields['vat_amount'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        # 거래처 필수 검증
        merchant = cleaned_data.get('merchant')
        merchant_name = cleaned_data.get('merchant_name')
        if not merchant and not merchant_name:
            raise ValidationError('거래처를 선택하거나 직접 입력하세요.')
        
        # 부가세 자동 계산
        is_business = cleaned_data.get('is_business', True)
        tax_type = cleaned_data.get('tax_type', 'taxable')
        amount = cleaned_data.get('amount')
        vat_amount = cleaned_data.get('vat_amount')
        
        if is_business and tax_type == 'taxable' and amount and not vat_amount:
            cleaned_data['vat_amount'] = (amount * Decimal('0.1')).quantize(Decimal('0.01'))
        
        return cleaned_data


class MerchantForm(forms.ModelForm):
    """거래처 입력/수정 폼"""
    
    class Meta:
        model = Merchant
        fields = ['name', 'business_number', 'contact', 'category', 'memo']
        widgets = {
            'memo': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'name': '거래처명',
            'business_number': '사업자등록번호',
            'contact': '연락처',
            'category': '카테고리',
            'memo': '메모',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 필드 선택사항 설정
        self.fields['business_number'].required = False
        self.fields['contact'].required = False
        self.fields['category'].required = False
        self.fields['memo'].required = False
