from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal

from .models import Transaction, Merchant, Category
from apps.businesses.models import Account, Business
import re

class TransactionForm(forms.ModelForm):
    """거래 입력/수정 폼"""
    merchant_name = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '거래처명 직접 입력',
            'list': 'merchant-list'  # datalist 활용
        })
    )    
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
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '거래처명 (예: 네이버)',
            }),
            'business_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123-45-67890',
                'maxlength': '12',
            }),
            'contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '연락처 (예: 010-1234-5678)',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'memo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '메모 (선택)',
            }),
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

        if self.user:
            self.fields['category'].queryset = Category.objects.filter(
                Q(is_system=True) | Q(user=self.user)
            ).order_by('type', 'name')
        self.fields['category'].empty_label = '미지정(기타)'

        # 필드 선택사항 설정
        self.fields['business_number'].required = False
        self.fields['contact'].required = False
        self.fields['category'].required = False
        self.fields['memo'].required = False

        # 유효성 검사 실패 시 필드 강조 표시
        if self.is_bound and self.errors:
            for field_name in self.errors:
                field = self.fields.get(field_name)
                if not field:
                    continue
                existing = field.widget.attrs.get('class', '')
                if 'is-invalid' not in existing:
                    field.widget.attrs['class'] = f"{existing} is-invalid".strip()

    def clean_business_number(self):
        """사업자등록번호 형식 검증 및 정규화"""
        reg_num = self.cleaned_data.get('business_number')

        if not reg_num:
            return reg_num

        cleaned = reg_num.replace('-', '').replace(' ', '')

        if not cleaned.isdigit():
            raise ValidationError('사업자등록번호는 숫자와 하이픈(-)만 입력 가능합니다.')

        if len(cleaned) != 10:
            raise ValidationError('사업자등록번호는 10자리여야 합니다.')

        return f"{cleaned[:3]}-{cleaned[3:5]}-{cleaned[5:]}"


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'expense_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '카테고리명'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'expense_type': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name': '카테고리명',
            'type': '유형',
            'expense_type': '지출 세부 유형 (지출만)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['type'].choices = [('', '수입 또는 지출 선택')] + list(self.fields['type'].choices)
        self.fields['expense_type'].choices = [('', '없음')] + list(self.fields['expense_type'].choices)
        self.fields['expense_type'].required = False
        # 지출이 아니면 expense_type 숨기기
        if self.instance and self.instance.type != 'expense':
            self.fields['expense_type'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        cat_type = cleaned_data.get('type')
        expense_type = cleaned_data.get('expense_type')
        
        # 지출 카테고리는 세부 유형 선택사항으로 (사용자 카테고리는 자유롭게)
        if cat_type == 'expense':
            # expense_type이 비어있어도 OK (사용자 카테고리)
            pass
        else:
            # 수입 카테고리는 expense_type 제거
            cleaned_data['expense_type'] = None
        
        return cleaned_data