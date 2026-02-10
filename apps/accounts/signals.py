"""
User-Profile 자동 연동 시그널

Django Signal을 사용하여 User와 Profile을 자동으로 연결:
    1. 회원가입 시 → User 생성 → Profile 자동 생성
    2. User 정보 수정 시 → Profile도 자동 저장

왜 필요한가?
    - User 모델은 Django 기본 제공 (수정 불가)
    - 추가 정보(사업자번호 등)는 Profile에 저장
    - Signal로 자동 연동하여 개발자가 신경 쓸 필요 없음
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    User 생성 시 Profile 자동 생성
    
    Args:
        sender: User 모델 (발신자)
        instance: 생성된 User 인스턴스
        created: 새로 생성되었는지 여부 (True/False)
        
    Example:
        user = User.objects.create_user(username='test')
        → Profile.objects.create(user=user) 자동 실행
    """
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    """
    User 저장 시 Profile도 함께 저장
    
    Note:
        - created=False일 때만 실행 (수정 시)
        - hasattr 체크: Profile이 없을 수도 있음
        
    Example:
        user.first_name = 'John'
        user.save()
        → user.profile.save() 자동 실행
    """
    # 수정 시에만 실행 (생성 시는 위에서 처리)
    if not created and hasattr(instance, 'profile'):
        instance.profile.save()