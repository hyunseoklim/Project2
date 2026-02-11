"""
사용자 프로필 관리

Django 기본 User 모델을 확장하여 사업자 정보를 저장합니다.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from apps.core.models import TimeStampedModel
from django.db.models.signals import post_save
from django.dispatch import receiver


# 공통 검증 패턴
PHONE_VALIDATOR = RegexValidator(
    regex=r'^[0-9\-\+\(\)\s]+$',
    message='올바른 전화번호를 입력하세요'
)

BUSINESS_NUMBER_VALIDATOR = RegexValidator(
    regex=r'^\d{10}$',
    message='사업자등록번호는 10자리 숫자여야 합니다'
)


class Profile(TimeStampedModel):
    """사업자 프로필 (Django User 확장)"""
    
    BUSINESS_TYPE_CHOICES = [
        ('individual', '개인사업자'),
        ('corporate', '법인사업자'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[PHONE_VALIDATOR])

    class Meta:
        db_table = 'profiles'

    def __str__(self):
        return f"{self.user.username} 프로필"
    
    def get_main_business(self):
        """사용자의 대표 사업장 반환"""
        return self.user.businesses.filter(
            is_active=True,
            branch_type='main'
        ).first()
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()