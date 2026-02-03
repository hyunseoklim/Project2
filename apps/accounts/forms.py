from django import forms
from .models import Profile

class ProfileForm(forms.ModelForm):
    business_registration_number = forms.CharField(
        label="사업자 등록번호",
        max_length=15,  # 하이픈이나 공백을 고려해 늘려줍니다.
        required=False, # 모델의 blank=True와 맞춤
        help_text="하이픈(-) 없이 숫자 10자리만 입력해주세요."
    )
    
    class Meta:
        model = Profile
        fields = ['business_registration_number', 'business_type', 'phone']
        
        # 1. 레이블(Label) 한글화: 화면에 표시될 이름을 지정합니다.
        # HTML 하드코딩 방지용, 한글로 변환
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
        for field_name, field in self.fields.items():
            # 이미 설정된 클래스가 있다면 유지하고 form-control 추가
            existing_classes = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()

    
    def clean_business_registration_number(self):
        # 1. 값 가져오기 및 전처리
        brn = self.cleaned_data.get('business_registration_number')
        
        # 값이 비어있으면(blank=True) 이후 검사 없이 통과
        if not brn:
            return brn

        # 사용자가 실수로 넣은 공백이나 하이픈(-) 제거
        brn = brn.replace(" ", "").replace("-", "")

        # 2. 형식 유효성 검사
        if not brn.isdigit():
            raise forms.ValidationError("사업자 번호는 숫자만 입력 가능합니다.")
        
        if len(brn) != 10:
            raise forms.ValidationError("사업자 번호는 정확히 10자리여야 합니다.")

        # 3. 중복 검사 (DB 조회)
        # 현재 수정 중인 내 프로필은 제외하고 검색
        exists = Profile.objects.exclude(user=self.instance.user).filter(
            business_registration_number=brn
        ).exists()
        
        if exists:
            raise forms.ValidationError("이미 등록된 사업자 등록번호입니다.")
            
        # 최종적으로 정제된 번호를 반환
        return brn