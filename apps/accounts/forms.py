from django import forms
from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['business_registration_number', 'business_type', 'phone']
        widgets = {
            'business_registration_number': forms.TextInput(attrs={
                'placeholder': '숫자 10자리만 입력 (예: 1234567890)',
                'class': 'form-control'
            }),
            'business_type': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={
                'placeholder': '010-0000-0000',
                'class': 'form-control'
            }),
        }