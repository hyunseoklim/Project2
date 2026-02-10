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


"""
소프트 삭제 모델 (Soft Delete Pattern)

일반 삭제 vs 소프트 삭제:
    - 일반 삭제: DB에서 완전히 제거 (복구 불가)
    - 소프트 삭제: is_active=False로 표시 (복구 가능)

사용 이유:
    1. 데이터 복구 가능 (실수로 삭제해도 안전)
    2. 감사/추적 목적 (누가 언제 삭제했는지 기록)
    3. 연관 데이터 보호 (외래키로 연결된 데이터 보호)

사용 방법:
    class MyModel(SoftDeleteModel):
        name = models.CharField(max_length=100)
    
    # 삭제
    obj.soft_delete()  # is_active=False
    
    # 조회 (활성만)
    MyModel.active.all()
    
    # 조회 (삭제 포함)
    MyModel.objects.all()
    
    # 복구
    obj.restore()  # is_active=True
"""

class SoftDeleteModel(TimeStampedModel):
    """
    소프트 삭제 지원 추상 모델
    
    Fields:
        is_active: 활성 상태 (True: 정상, False: 삭제됨)
        
    Managers:
        objects: 모든 레코드 (삭제 포함)
        active: 활성 레코드만 (is_active=True)
    """
    is_active = models.BooleanField(
        default=True, 
        db_index=True,
        verbose_name="활성 상태"
    )
    
    objects = models.Manager()  # 기본 매니저 (모든 레코드)
    active = SoftDeleteManager()    # 활성 레코드만
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """소프트 삭제 (is_active=False)"""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def restore(self):
        """복구 (is_active=True)"""
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