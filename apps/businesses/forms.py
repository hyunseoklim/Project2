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
        self.fields['business'].empty_label = '개인용이면 선택 안 함'
        
        # 사업장 선택 필수 아님
        self.fields['business'].required = False

        # 유효성 검사 실패 시 필드 강조 표시
        if self.is_bound and self.errors:
            for field_name in self.errors:
                field = self.fields.get(field_name)
                if not field:
                    continue
                existing = field.widget.attrs.get('class', '')
                if 'is-invalid' not in existing:
                    field.widget.attrs['class'] = f"{existing} is-invalid".strip()
    
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


class BusinessForm(forms.ModelForm):
    """사업장 생성/수정 폼"""
    
    class Meta:
        model = Business
        fields = ['name', 'location', 'business_type', 'branch_type', 'registration_number', 'memo']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '사업장명 (예: 강남점)'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '주소 (예: 서울시 강남구)'
            }),
            'business_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '업종 (예: 소매업)'
            }),
            'branch_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123-45-67890 형식으로 입력'
            }),

            'memo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '사업장 관련 메모를 입력하세요.'
            }),
        }
        labels = {
            'name': '사업장명',
            'location': '위치/주소',
            'business_type': '업종',
            'branch_type': '구분',
            'registration_number': '사업자등록번호',
        }
        help_texts = {
            'name': '사업장을 구분할 수 있는 이름을 입력하세요',
            'registration_number': '하이픈(-)을 포함하여 입력하세요',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
         # 새로 생성 시 자동 branch_code 제안
        if not self.instance.pk and self.user:
            registration_number = self.data.get('registration_number', '')
            if registration_number:
                existing_count = Business.objects.filter(
                    user=self.user,
                    registration_number=registration_number
                ).count()
                self.fields['branch_code'].initial = str(existing_count + 1).zfill(4)

        # 선택 필드들
        self.fields['location'].required = False
        self.fields['business_type'].required = False
        self.fields['registration_number'].required = False

        # 유효성 검사 실패 시 필드 강조 표시
        if self.is_bound and self.errors:
            for field_name in self.errors:
                field = self.fields.get(field_name)
                if not field:
                    continue
                existing = field.widget.attrs.get('class', '')
                if 'is-invalid' not in existing:
                    field.widget.attrs['class'] = f"{existing} is-invalid".strip()
    
    def clean_name(self):
        """사업장명 중복 검증"""
        name = self.cleaned_data.get('name')
        
        if not name:
            raise ValidationError('사업장명은 필수입니다.')
        
        # 중복 검증 (동일 사용자 내)
        if self.user:
            queryset = Business.active.filter(user=self.user, name=name)
            
            # 수정 시 자기 자신 제외
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError('이미 등록된 사업장명입니다.')
        
        return name
    
    def clean_registration_number(self):
        """사업자번호 형식 검증"""
        reg_num = self.cleaned_data.get('registration_number', '').strip()
        
        if not reg_num:
            return ''
        
        # 하이픈 제거
        clean_num = reg_num.replace('-', '').replace(' ', '')
        
        # 숫자 검증
        if not clean_num.isdigit():
            raise forms.ValidationError('사업자등록번호는 숫자만 입력 가능합니다.')
        
        # 길이 검증
        if len(clean_num) != 10:
            raise forms.ValidationError('사업자등록번호는 10자리여야 합니다.')
        
        # 하이픈 포맷
        formatted = f"{clean_num[:3]}-{clean_num[3:5]}-{clean_num[5:]}"
        return formatted
    
    def clean_branch_code(self):
        """분류코드 검증"""
        branch_code = self.cleaned_data.get('branch_code', '').strip()
        
        if not branch_code:
            return '0001'
        
        # 숫자만
        if not branch_code.isdigit():
            raise forms.ValidationError('분류코드는 숫자만 입력 가능합니다.')
        
        # 4자리
        if len(branch_code) != 4:
            raise forms.ValidationError('분류코드는 4자리여야 합니다.')
        
        return branch_code
    
    def clean(self):
        cleaned_data = super().clean()
        registration_number = cleaned_data.get('registration_number')
        branch_code = cleaned_data.get('branch_code')
        
        if registration_number and branch_code and self.user:
            # 중복 체크 (같은 사업자번호 + 같은 분류코드)
            duplicate = Business.objects.filter(
                user=self.user,
                registration_number=registration_number,
                branch_code=branch_code,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            if duplicate.exists():
                raise forms.ValidationError(
                    f"사업자번호 {registration_number}의 분류코드 {branch_code}는 "
                    f"이미 사용 중입니다. 다른 분류코드를 입력하세요."
                )
        
        return cleaned_data


class BusinessSearchForm(forms.Form):
    """사업장 검색 폼"""
    
    BRANCH_TYPE_CHOICES = [
        ('', '전체'),
        ('main', '본점'),
        ('branch', '지점'),
    ]
    
    branch_type = forms.ChoiceField(
        choices=BRANCH_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='구분'
    )
    
    business_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '업종 검색'
        }),
        label='업종'
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '사업장명 또는 위치 검색'
        }),
        label='검색'
    )