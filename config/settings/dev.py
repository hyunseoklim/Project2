from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# 개발용 추가 앱들 (필요시)
INSTALLED_APPS += [
    # 'debug_toolbar',  # Django Debug Toolbar 사용하려면 주석 해제
]

MIDDLEWARE += [
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',  # Debug Toolbar 사용시
]

# Debug Toolbar 설정 (사용시)
INTERNAL_IPS = [
    '127.0.0.1',
]

# 개발 환경에서 이메일을 콘솔에 출력
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# 개발 환경 로깅 (상세하게)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',  # SQL 쿼리 보고 싶으면 DEBUG, 아니면 INFO
        },
    },
}