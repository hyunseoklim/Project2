"""계좌 관리 폼"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Account, Business


class AccountForm(forms.ModelForm):
    """계좌 생성/수정 폼"""
    
    class Meta:
        model = Account
        fields = ['name', 'bank_name', 'account_number', 'account_type', 'business']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '계좌 별칭 (예: 국민은행 주거래)'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '은행명 (예: 국민은행)'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '1234-5678-9012 형식으로 입력'
            }),
            'account_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'business': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'name': '계좌 별칭',
            'bank_name': '은행명',
            'account_number': '계좌번호',
            'account_type': '계좌 구분',
            'business': '연결 사업장 (선택)',
        }
        help_texts = {
            'account_number': '하이픈(-)을 포함하여 입력하세요',
            'business': '사업용 계좌인 경우 사업장을 선택할 수 있습니다',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 사업장 선택지: 본인의 활성 사업장만
        if self.user:
            self.fields['business'].queryset = Business.active.filter(user=self.user)
        
        # 사업장 선택 필수 아님
        self.fields['business'].required = False
    
    def clean_account_number(self):
        """계좌번호 형식 및 중복 검증"""
        account_number = self.cleaned_data.get('account_number')
        
        if not account_number:
            return account_number
        
        # 하이픈 제거 후 검증
        cleaned = account_number.replace('-', '').replace(' ', '')
        
        # 숫자만 있는지 확인
        if not cleaned.isdigit():
            raise ValidationError('계좌번호는 숫자와 하이픈(-)만 입력 가능합니다.')
        
        # 최소 길이 검증
        if len(cleaned) < 10:
            raise ValidationError('유효하지 않은 계좌번호입니다. (최소 10자리)')
        
        # 중복 검증 (동일 사용자 내)
        if self.user:
            queryset = Account.active.filter(user=self.user, account_number=account_number)
            
            # 수정 시 자기 자신 제외
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError('이미 등록된 계좌번호입니다.')
        
        return account_number
    
    def clean(self):
        """폼 전체 검증"""
        cleaned_data = super().clean()
        account_type = cleaned_data.get('account_type')
        business = cleaned_data.get('business')
        
        # 개인용 계좌에 사업장이 선택된 경우
        if account_type == 'personal' and business:
            self.add_error('business', '개인용 계좌는 사업장을 선택할 수 없습니다.')
        
        return cleaned_data


class AccountSearchForm(forms.Form):
    """계좌 검색 폼"""
    
    ACCOUNT_TYPE_CHOICES = [
        ('', '전체'),
        ('business', '사업용'),
        ('personal', '개인용'),
    ]
    
    account_type = forms.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='계좌 구분'
    )
    
    business = forms.ModelChoiceField(
        queryset=Business.objects.none(),
        required=False,
        empty_label='전체 사업장',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='사업장'
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '계좌명 또는 은행명 검색'
        }),
        label='검색'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 사업장 선택지: 본인의 활성 사업장만
        if user:
            self.fields['business'].queryset = Business.active.filter(user=user)