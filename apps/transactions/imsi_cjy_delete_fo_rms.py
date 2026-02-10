"""
amount = 공급가액
vat_amount = 부가세
total_amount = models.py 에 있는

@property
    def total_amount(self):
        # 총금액 = 공급가액 + 부가세
        return self.amount + (self.vat_amount or Decimal('0'))
이 코드를 사용하기 위해서라면, forms.py를 아래코드로 수정해야 하나
아직 확인을 제대로 못해봄. 

"""
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal, ROUND_HALF_UP
from .models import Transaction, Merchant, Category, Attachment
from apps.businesses.models import Account, Business


class TransactionForm(forms.ModelForm):
    """거래 입력/수정 폼"""
    merchant_name = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '거래처명 직접 입력',
            'list': 'merchant-list'
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
            'amount': '금액 (총액)',
            'vat_amount': '부가세 (자동계산)',
            'occurred_at': '거래일시',
            'memo': '메모',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['business'].queryset = Business.objects.filter(user=self.user, is_active=True)
            self.fields['account'].queryset = Account.objects.filter(user=self.user, is_active=True)
            self.fields['merchant'].queryset = Merchant.objects.filter(user=self.user, is_active=True)
            self.fields['category'].queryset = Category.objects.filter(
                Q(is_system=True) | Q(user=self.user)
            ).order_by('type', 'name')

        self.fields['merchant'].required = False
        self.fields['merchant_name'].required = False
        self.fields['business'].required = False
        self.fields['vat_amount'].required = False
        
        # 수정 모드: 총금액으로 표시
        if self.instance and self.instance.pk:
            self.initial['amount'] = self.instance.total_amount

    def clean(self):
        cleaned_data = super().clean()
        
        merchant = cleaned_data.get('merchant')
        merchant_name = cleaned_data.get('merchant_name')
        if not merchant and not merchant_name:
            raise ValidationError('거래처를 선택하거나 직접 입력하세요.')
        
        tx_type = cleaned_data.get('tx_type')
        is_business = cleaned_data.get('is_business', True)
        tax_type = cleaned_data.get('tax_type', 'taxable')
        amount = cleaned_data.get('amount')
        vat_amount = cleaned_data.get('vat_amount')
        
        if amount and not vat_amount:
            if tx_type == 'OUT' and is_business and tax_type == 'taxable':
                supply = (amount / Decimal('1.1')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                vat = (amount - supply).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                cleaned_data['amount'] = supply
                cleaned_data['vat_amount'] = vat
            else:
                cleaned_data['vat_amount'] = Decimal('0')
        
        return cleaned_data


class MerchantForm(forms.ModelForm):
    class Meta:
        model = Merchant
        fields = ['name', 'business_number', 'contact', 'category', 'memo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '거래처명 (예: 네이버)'}),
            'business_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123-45-67890', 'maxlength': '12'}),
            'contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '연락처 (예: 010-1234-5678)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '메모 (선택)'}),
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
        self.fields['business_number'].required = False
        self.fields['contact'].required = False
        self.fields['category'].required = False
        self.fields['memo'].required = False
        if self.is_bound and self.errors:
            for field_name in self.errors:
                field = self.fields.get(field_name)
                if not field:
                    continue
                existing = field.widget.attrs.get('class', '')
                if 'is-invalid' not in existing:
                    field.widget.attrs['class'] = f"{existing} is-invalid".strip()

    def clean_business_number(self):
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
        if self.instance and self.instance.type != 'expense':
            self.fields['expense_type'].required = False

    def clean(self):
        cleaned_data = super().clean()
        cat_type = cleaned_data.get('type')
        if cat_type != 'expense':
            cleaned_data['expense_type'] = None
        return cleaned_data


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="엑셀 파일 선택",
        help_text=".xlsx 형식의 파일만 업로드 가능합니다."
    )

    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file and not file.name.endswith('.xlsx'):
            raise ValidationError("에러: .xlsx 확장자 파일만 올릴 수 있습니다.")
        return file

    
class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ['attachment_type', 'file']
        widgets = {
            'attachment_type': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.jpg,.jpeg,.png,.pdf'}),
        }
        labels = {
            'attachment_type': '영수증 유형',
            'file': '파일 선택',
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('파일 크기는 5MB를 초과할 수 없습니다.')
        return file