"""
프로젝트 공통 추상 모델

- TimeStampedModel: 생성/수정 시간 자동 추적
- SoftDeleteModel: 소프트 삭제 (is_active) + Active Manager
- UserOwnedModel: 사용자 소유 + 타임스탬프
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class TimeStampedModel(models.Model):
    """생성/수정 시간 자동 추적"""
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """활성 데이터만 조회하는 Manager"""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteModel(TimeStampedModel):
    """
    소프트 삭제 (데이터 보존)
    
    objects: 전체 데이터 (Admin용)
    active: 활성 데이터만 (일반용)
    """
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    objects = models.Manager()  # 전체 조회
    active = SoftDeleteManager()  # 활성만 조회

    class Meta:
        abstract = True
    
    def soft_delete(self):
        """삭제 표시 (DB에서는 유지)"""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def restore(self):
        """삭제 취소"""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])


class UserOwnedModel(TimeStampedModel):
    """사용자 소유 리소스 (타임스탬프 포함)"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        db_index=True
    )

    class Meta:
        abstract = True

    def is_owner(self, user):
        """소유자 확인"""
        return self.user == user