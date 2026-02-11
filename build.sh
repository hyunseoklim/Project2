#!/usr/bin/env bash
# exit on error
set -o errexit

# 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt

# 정적 파일 수집
python manage.py collectstatic --no-input

# 데이터베이스 마이그레이션
python manage.py migrate