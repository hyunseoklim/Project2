from django import forms
from .models import Profile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re

class ProfileForm(forms.ModelForm):
    full_name = forms.CharField(
        label="성함",
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': '실명을 입력하세요'})
    )
    business_registration_number = forms.CharField(
        label="사업자 등록번호",
        max_length=15,  # 하이픈이나 공백을 고려해 늘려줍니다.
        required=False, # 모델의 blank=True와 맞춤
        help_text="하이픈(-) 없이 숫자 10자리만 입력해주세요."
    )
    
    class Meta:
        model = Profile
        fields = ['full_name', 'business_registration_number', 'business_type', 'phone']
        
        # 1. 레이블(Label) 한글화: 화면에 표시될 이름을 지정합니다.
        # HTML 하드코딩 방지용, 한글로 변환``
        labels = {
            'business_registration_number': '사업자 등록 번호',
            'business_type': '사업 유형',
            'phone': '전화번호',
        }
        
        # 2. 위젯(Widget) 설정: placeholder 등 특수 속성만 남깁니다. (class는 아래에서 자동화)
        widgets = {
            'business_registration_number': forms.TextInput(attrs={
                'placeholder': '숫자 10자리만 입력 (예: 1234567890)',
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '010-0000-0000',
            }),
        }

    def __init__(self, *args, **kwargs):
        """3. 스타일 자동화: 모든 필드에 일괄적으로 부트스트랩 클래스 주입"""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            # User 모델의 first_name에 저장된 값을 full_name 필드의 초기값으로 설정
            self.fields['full_name'].initial = self.instance.user.first_name
            
        for field_name, field in self.fields.items():
            # 이미 설정된 클래스가 있다면 유지하고 form-control 추가
            existing_classes = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()


    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # full_name을 User 모델의 first_name에 저장
        if self.cleaned_data.get('full_name'):
            profile.user.first_name = self.cleaned_data['full_name']
            if commit:
                profile.user.save()
        
        if commit:
            profile.save()
        
        return profile

    
class CustomUserCreationForm(UserCreationForm):
    """
    커스텀 회원가입 폼
    - 이메일 필드 추가 (필수)
    - 이메일 중복 검증
    - 사용자 친화적인 에러 메시지
    """
    email = forms.EmailField(
        required=True,
        label='이메일',
        widget=forms.EmailInput(attrs={
            'class': 'form-input-field',
            'placeholder': 'example@email.com',
            'autocomplete': 'email'
        }),
        help_text='비밀번호 찾기에 사용됩니다.'
    )
    
    username = forms.CharField(
        label='아이디',
        widget=forms.TextInput(attrs={
            'class': 'form-input-field',
            'placeholder': '4-20자 영문, 숫자',
            'autocomplete': 'username'
        }),
        help_text='4-20자의 영문, 숫자만 사용 가능합니다.'
    )
    
    password1 = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-field',
            'placeholder': '8자 이상',
            'autocomplete': 'new-password'
        }),
        help_text='최소 8자 이상이어야 합니다.'
    )
    
    password2 = forms.CharField(
        label='비밀번호 확인',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-field',
            'placeholder': '비밀번호 재입력',
            'autocomplete': 'new-password'
        }),
        help_text='동일한 비밀번호를 다시 입력해주세요.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_username(self):
        """아이디 검증"""
        username = self.cleaned_data.get('username')
        
        # 길이 검증
        if len(username) < 4:
            raise ValidationError('아이디는 최소 4자 이상이어야 합니다.')
        if len(username) > 20:
            raise ValidationError('아이디는 최대 20자까지 가능합니다.')
        
        # 영문, 숫자만 허용
        if not re.match(r'^[a-zA-Z0-9]+$', username):
            raise ValidationError('아이디는 영문과 숫자만 사용 가능합니다.')
        
        # 중복 검증
        if User.objects.filter(username=username).exists():
            raise ValidationError('이미 사용 중인 아이디입니다.')
        
        return username

    def clean_email(self):
        """이메일 검증 및 중복 확인"""
        email = self.cleaned_data.get('email')
        
        # 이메일 중복 검증
        if User.objects.filter(email=email).exists():
            raise ValidationError('이미 가입된 이메일 주소입니다.')
        
        # 이메일 형식 추가 검증 (선택사항)
        if email and '@' not in email:
            raise ValidationError('올바른 이메일 주소를 입력해주세요.')
        
        return email

    def clean_password1(self):
        """비밀번호 강도 검증 (간소화 버전)"""
        password = self.cleaned_data.get('password1')
        
        # 최소 길이
        if len(password) < 8:
            raise ValidationError('비밀번호는 최소 8자 이상이어야 합니다.')
        
        # 숫자만으로 구성 방지
        if password.isdigit():
            raise ValidationError('비밀번호는 숫자만으로 구성할 수 없습니다.')
        
        # 너무 흔한 비밀번호 방지
        common_passwords = ['password', '12345678', 'qwerty123', 'abc12345']
        if password.lower() in common_passwords:
            raise ValidationError('너무 흔한 비밀번호입니다. 다른 비밀번호를 사용해주세요.')
        
        return password

    def clean_password2(self):
        """비밀번호 확인 일치 검증"""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError('두 비밀번호가 일치하지 않습니다.')
        
        return password2

    def save(self, commit=True):
        """이메일 포함하여 사용자 저장"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
        
        return user