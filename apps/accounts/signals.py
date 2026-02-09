from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """유저 생성 시 프로필 자동 생성"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """유저 저장 시 프로필도 같이 저장"""
    # hasattr로 확인하는 이유는 가끔 유저 생성 시점에 프로필이 없을 수도 있기 때문입니다.
    if hasattr(instance, 'profile'):
        instance.profile.save()