from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal

from .models import Transaction, Merchant, Category, Attachment, MerchantCategory
from apps.businesses.models import Account, Business


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
            # 카테고리 필터링: 시스템 카테고리 + 사용자가 만든 카테고리
            self.fields['category'].queryset = Category.objects.filter(
                Q(is_system=True) | Q(user=self.user)
            ).order_by('type', 'name')


        # 필드 필수 여부 및 기타 설정
        self.fields['merchant'].required = False
        self.fields['merchant_name'].required = False
        self.fields['business'].required = False
        self.fields['vat_amount'].required = False

    def clean(self):
        """폼 전체 검증 및 부가세 자동 계산"""
        cleaned_data = super().clean()
        
        # 1. 거래처 검증: 선택 또는 직접 입력 중 하나는 필수
        merchant = cleaned_data.get('merchant')
        merchant_name = cleaned_data.get('merchant_name')
        if not merchant and not merchant_name:
            raise ValidationError('거래처를 선택하거나 직접 입력하세요.')
        
        # 2. 부가세 계산 관련 필드 가져오기
        tx_type = cleaned_data.get('tx_type')  # 수입(IN) / 지출(OUT)
        is_business = cleaned_data.get('is_business', True)  # 사업용 거래 여부
        tax_type = cleaned_data.get('tax_type', 'taxable')  # 과세(taxable) / 면세(tax_free)
        amount = cleaned_data.get('amount')  # 사용자가 입력한 총금액
        vat_amount = cleaned_data.get('vat_amount')  # 사용자가 입력한 부가세 (선택)
        
        # 3. 부가세 자동 계산 조건:
        #    - 금액이 입력되었고
        #    - 부가세가 비어있고
        #    - 지출(OUT)이고
        #    - 사업용 거래이고
        #    - 과세 거래인 경우
        if amount and not vat_amount:
            if tx_type == 'OUT' and is_business and tax_type == 'taxable':
                # 총금액 11,000원 입력 시:
                # - 공급가액 = 11,000 ÷ 1.1 = 10,000원
                # - 부가세 = 11,000 - 10,000 = 1,000원
                supply = (amount / Decimal('1.1')).quantize(
                    Decimal('0.01'), 
                    rounding=ROUND_HALF_UP
                )
                vat = (amount - supply).quantize(
                    Decimal('0.01'), 
                    rounding=ROUND_HALF_UP
                )
                
                # cleaned_data 업데이트
                cleaned_data['amount'] = supply  # amount는 공급가액으로 저장
                cleaned_data['vat_amount'] = vat  # vat_amount는 부가세로 저장
            else:
                # 수입, 개인용, 면세 거래는 부가세 0원
                cleaned_data['vat_amount'] = Decimal('0')
        
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
            # [수정 완료] MerchantCategory에는 is_system이 없으므로 user__isnull=True를 사용합니다.
            self.fields['category'].queryset = MerchantCategory.objects.filter(
                Q(user__isnull=True) | Q(user=self.user)
            ).order_by('name')
        else:
            # user 정보가 없는 경우 공용 카테고리만 노출
            self.fields['category'].queryset = MerchantCategory.objects.filter(user__isnull=True).order_by('name')
            
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
            pass
        else:
            cleaned_data['expense_type'] = None

        return cleaned_data
        # 수입 카테고리인 경우
        if tx_type == 'income':
            # 선택과 직접입력 둘 다 없으면 에러
            if not income_type and not custom_income_type:
                raise forms.ValidationError('수입 카테고리는 세부 유형을 선택하거나 직접 입력해야 합니다.')
            
            # 직접 입력한 경우
            if custom_income_type:
                cleaned_data['income_type'] = 'other'
            
            # 지출 타입 제거
            cleaned_data['expense_type'] = None
    
        # 지출 카테고리인 경우
        elif tx_type == 'expense':
            # 선택과 직접입력 둘 다 없으면 에러
            if not expense_type and not custom_expense_type:
                raise forms.ValidationError('지출 카테고리는 세부 유형을 선택하거나 직접 입력해야 합니다.')
            
            # 직접 입력한 경우
            if custom_expense_type:
                cleaned_data['expense_type'] = 'other'
            
            # 수입 타입 제거
            cleaned_data['income_type'] = None
        
        return cleaned_data

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="엑셀 파일 선택",
        help_text=".xlsx 형식의 파일만 업로드 가능합니다."
    )

    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file:
            # 확장자 검사
            if not file.name.endswith('.xlsx'):
                raise ValidationError("에러: .xlsx 확장자 파일만 올릴 수 있습니다.")
        return file
    
class AttachmentForm(forms.ModelForm):
    """영수증 첨부 파일 업로드 폼"""
    
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
        """파일 크기 검증"""
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 5 * 1024 * 1024:  # 5MB
                raise forms.ValidationError('파일 크기는 5MB를 초과할 수 없습니다.')
        return file