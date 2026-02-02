# `프로젝트 개요`

프로젝트명: 1인 사업자를 위한 가계부 프로그램

- 목적: 1인 사업자 분들은 사업하기에도 바쁩니다. 기본 가계부를 정리하며, 
        더 나아가 세금 관련 문제, AI조언, 자동화를 고려하여 만들게 되었습니다.
- 기간: 01.29 ~ 02.13
- 팀장 : 최재용         팀원:  서호준, 임현석, 정서현

# 기술 스택

| 분류 | 기술 |
| --- | --- |
| Backend | Django 6.0 |
| Database | PostgreSQL |
| Frontend | Django Templates + Bootstrap |

# 간단한 로컬 실행방법 (OS / window)

```bash
# 가상환경 종료 및 홈 디렉토리 이동
deactivate
cd ~

# git clone을 통해서 폴더 생성과 확인 후 이동 및 vs코드 재실행
git clone https://github.com/checkCJY/TaxProject.git
ls -l
cd "프로젝트 폴더명"
code -r .

# 가상환경 설정
uv venv .venv

# 가상환경 실행
source .venv/bin/activate

# 패키지 설치
uv pip install -r requirements.txt

# .env 파일 생성후 내용작성
# 내용은 팀장에게 문의. 
touch .env

# PostgreSQL 접속해서 작성.
PostgreSQL 접속
WSL2 : sudo -u postgres psql
mac : psql postgres

1. 데이터베이스 생성
CREATE DATABASE django_project;

2. 사용자 생성 (공백조심)
CREATE USER project_user WITH PASSWORD 'project-password';

# 오타수정
필수 1: 스키마에서 테이블 생성 가능하게
GRANT USAGE, CREATE ON SCHEMA public TO project_user;

권장 2: public 스키마 소유자 변경(안전/깔끔)
ALTER SCHEMA public OWNER TO project_user;

권장 3: DB 소유자도 django_user로(권한 꼬임 방지)
ALTER DATABASE django_project OWNER TO project_user;

사용자 기본 설정 (각각 따로 실행)
ALTER ROLE project_user SET client_encoding TO 'utf8';
ALTER ROLE project_user SET timezone TO 'Asia/Seoul';

데이터베이스 권한 부여
GRANT ALL PRIVILEGES ON DATABASE django_project TO project_user;

# 서버 실행 확인
uv run python manage.py runserver

# 추가 더미데이터 생성 및 제거 (순서대로. SQL)
# SQLite3, PostgreSQL도 가능
python manage.py shell < ./docs/dummy_data.py
python manage.py shell < ./docs/dummy_data_delete.py
```

# 주요 기능
1. 사용자 인증 (`accounts` 앱)
2. 사업장 관리 (`businesses` 앱)
3. 계좌 관리 (`accounts` 앱 또는 `businesses` 앱)
4. 거래처 관리 (`transactions` 앱)
5. 거래 내역 관리 (`transactions` 앱)
6. 증빙 서류 관리 (`transactions` 앱)
7. 카테고리 관리 (`transactions` 앱)
8. 손익 대시보드 (`dashboard` 앱)
9. 세금 데이터 정리 (`tax` 앱)

### Python/Django
- PEP 8 준수
- 클래스명: `PascalCase` (UserProfile)
- 함수명: `snake_case` (get_user_posts)
- 상수: `UPPER_CASE` (MAX_LENGTH)

### Git 커밋 메시지
- `feat:` 새로운 기능 추가
- `fix:` 버그 수정
- `docs:` 문서 수정
- `style:` 코드 포맷팅
- `refactor:` 코드 리팩토링

예시: `feat: 회원가입 API 구현`

### 브랜치 전략
- `main`: 배포용
- `develop`: 개발용
- `feature/기능명`: 기능 개발
# 프로젝트 구조

```
예시 템플릿
myproject/
├── accounts/          # 사용자 인증
├── posts/             # 게시글 관련
├── static/            # CSS, JS
├── templates/         # HTML 템플릿
├── manage.py
└── requirements.txt

```

# URL 구조 ( 이런 식으로 작성 예정 )

| URL | 설명 | View |
| --- | --- | --- |
| `/` | 메인 페이지 | index |
| `/accounts/signup/` | 회원가입 | signup |
| `/accounts/login/` | 로그인 | login |


# 테스트 계정

- 각각 슈퍼계정, 일반계정을 만들고 메모해두세요

# 배포 URL

(배포 후 URL 작성)