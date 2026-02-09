import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from apps.transactions.models import Transaction, Category, Account, Merchant
from apps.accounts.models import Profile
from django.contrib.auth import authenticate
from django.db import IntegrityError

@pytest.fixture
def test_user(db):
    """테스트용 유저 생성"""
    return User.objects.create_user(username='testuser', password='password123')

@pytest.fixture
def auth_client(client, test_user):
    """로그인된 클라이언트 제공"""
    client.login(username='testuser', password='password123')
    return client

@pytest.fixture
def base_data(test_user):
    """기본적인 계좌, 상점, 카테고리, 시간을 제공하는 픽스처"""
    # 고정된 시간 설정
    fixed_now = timezone.now()
    
    # 필수 객체 생성
    account = Account.objects.create(user=test_user, name="테스트 계좌", balance=100000)
    merchant = Merchant.objects.create(user=test_user, name="테스트 상점")
    category = Category.objects.create(name="식비", type='expense')
    
    # 딕셔너리 형태로 반환하여 테스트에서 골라 쓰게 함
    return {
        'account': account,
        'merchant': merchant,
        'category': category,
        'now': fixed_now
    }


@pytest.mark.django_db
def test_login_view_redirects_authenticated_user(auth_client):
    """이미 로그인한 유저가 로그인 페이지에 접근하면 홈으로 리다이렉트 되는지"""
    url = reverse('accounts:login')
    response = auth_client.get(url)
    
    # redirect_authenticated_user = True 설정 확인
    assert response.status_code == 302
    assert response.url == reverse('accounts:home')

@pytest.mark.django_db
def test_logout_view_redirects_home(auth_client):
    """로그아웃 시 설정한 next_page(홈)로 이동하는지"""
    url = reverse('accounts:logout')
    # POST로 요청해야 하는 경우가 많으므로 post 권장 (장고 4.1 이상)
    response = auth_client.post(url)
    
    assert response.status_code == 302
    assert response.url == reverse('accounts:home')


@pytest.mark.django_db
class TestAccountsView:

    def test_home_view_authenticated(self, auth_client, test_user):
        """로그인한 사용자가 접속했을 때 (필수 필드인 account, merchant, tx_type 반영)"""

        
        # 1. 필수 외래키 객체들 생성
        temp_account = Account.objects.create(user=test_user, name="테스트 계좌",balance=100000)
        temp_merchant = Merchant.objects.create(user=test_user, name="테스트 상점")
        temp_category = Category.objects.create(name="식비", type='expense')

        # 2. 모든 필수 조건을 충족하는 트랜잭션 생성
        Transaction.objects.create(
            user=test_user,
            amount=1000,
            tx_type='OUT',           # 'EXPENSE' 대신 'OUT' 사용    # 모델의 타입과 맞아야한다.
            category=temp_category, # 이것도
            account=temp_account,    # 필수 필드 추가
            merchant=temp_merchant,    # 필수 필드 추가
            occurred_at='2026-02-07 12:00:00'
        )
        
        url = reverse('accounts:home')
        response = auth_client.get(url)
        
        assert response.status_code == 200
        assert 'accounts/home_loggedin.html' in [t.name for t in response.templates]
        
        # 현재 뷰 로직이 category__isnull=True만 세고 있다면,
        # 위에서 카테고리를 할당했으므로 이 값은 0이어야 합니다.
        assert response.context['uncategorized_count'] == 0


    # ----------------------------------------------------------------
    # 2. signup 뷰 테스트
    # ----------------------------------------------------------------

    def test_signup_get_request(self, client):
        """회원가입 페이지 접속 확인"""
        url = reverse('accounts:signup')
        response = client.get(url)
        assert response.status_code == 200
        assert 'form' in response.context

    def test_signup_post_success(self, client):
        """회원가입 성공 케이스"""
        url = reverse('accounts:signup')
        data = {
            'username': 'newuser123',
            'email': 'new@example.com',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
        }
        # 회원가입 폼 전송
        response = client.post(url, data)
        
        # 가입 성공 후 홈으로 리다이렉트 확인
        assert response.status_code == 302
        assert response.url == reverse('accounts:home')
        # 실제로 유저가 생성되었는지 DB 확인
        assert User.objects.filter(username='newuser123').exists()

    def test_signup_already_authenticated_redirect(self, auth_client):
        """이미 로그인된 유저가 회원가입 시도 시 홈으로 리다이렉트"""
        url = reverse('accounts:signup')
        response = auth_client.get(url)
        
        assert response.status_code == 302
        assert response.url == reverse('accounts:home')

    def test_signup_validation_error(self, client):
        """비밀번호 불일치 등 폼 검증 실패 시"""
        url = reverse('accounts:signup')
        data = {
            'username': 'failuser',
            'email': 'fail@example.com',
            'password1': 'pass123',
            'password2': 'different_pass', # 비밀번호 다름
        }
        response = client.post(url, data)
        
        # 유저가 생성되지 않아야 함
        assert not User.objects.filter(username='failuser').exists()
        # 다시 회원가입 페이지에 머물러야 함 (200 OK)
        assert response.status_code == 200

@pytest.mark.django_db
class TestHomeView:

    def test_home_view_authenticated_current_model(self, auth_client, test_user, base_data):
        """모델이 Category를 필수로 요구하므로, 모든 데이터는 분류된 상태여야 함"""

        acc = base_data['account']
        mer = base_data['merchant']
        cat = base_data['category']
        now = base_data['now']

        # 1. 모든 거래에 카테고리를 넣어서 생성 (모델의 제약 조건을 지킴)
        Transaction.objects.create(
            user=test_user, amount=1000, tx_type='OUT',
            category=cat, account=acc, merchant=mer, occurred_at=now
        )

        # 2. 홈 페이지 접속
        response = auth_client.get(reverse('accounts:home'))

        # 3. 검증: 카테고리가 없는 데이터는 생성 자체가 불가능하므로, 카운트는 0이어야 함
        assert response.status_code == 200
        assert response.context['uncategorized_count'] == 0

@pytest.mark.django_db
class TestPasswordChangeView:
    
    def test_password_change_get(self, auth_client):
        """비밀번호 변경 페이지가 정상적으로 표시되는지 테스트"""
        url = reverse('accounts:password_change')
        response = auth_client.get(url)
        
        assert response.status_code == 200
        assert 'accounts/password_change.html' in [t.name for t in response.templates]

    def test_password_change_success(self, client, test_user): # auth_client 대신 client 사용 시도
        # 1. 로그인 상태 확실히 만들기
        password = "test_password123"
        test_user.set_password(password)
        test_user.save()
        client.login(username=test_user.username, password=password)

        url = reverse('accounts:password_change')
        new_password = "new_password456!"
        
        data = {
            'old_password': password,       # 이제 확실히 알고 있는 비밀번호 사용
            'new_password1': new_password,
            'new_password2': new_password,
        }
        
        response = client.post(url, data)
        
        # 2. 검증
        # 만약 여기서 또 200이 나온다면, response.context['form'].errors를 출력해보면 범인을 잡을 수 있어요!
        if response.status_code == 200:
            print(response.context['form'].errors) 
            
        assert response.status_code == 302
        assert response.url == reverse('accounts:home')
        # 3. 세션 유지 확인: 홈으로 다시 접속했을 때 로그인 전용 페이지가 뜨는지 확인
        home_response = client.get(reverse('accounts:home'))
        assert 'accounts/home_loggedin.html' in [t.name for t in home_response.templates]

@pytest.mark.django_db
class TestProfileDetailView:

    def test_profile_detail_access_denied_anonymous(self, client):
        """로그인하지 않은 사용자는 프로필 페이지에 접근할 수 없음 (로그인 페이지로 리다이렉트)"""
        url = reverse('accounts:profile_detail')
        response = client.get(url)
        
        # 302 리다이렉트 발생 (로그인 페이지로)
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_profile_detail_auto_create(self, auth_client, test_user):
        """프로필이 없는 유저가 접속했을 때, 프로필이 자동으로 생성되는지 테스트"""
        
        # 1. 수정 후: 이미 시그널로 생성되었으므로 count는 1이 정상입니다.  
        assert Profile.objects.filter(user=test_user).count() == 1        
        # 2. 프로필 상세 페이지 접속
        url = reverse('accounts:profile_detail')
        response = auth_client.get(url)
        
        # 3. 결과 확인
        assert response.status_code == 200
        assert 'accounts/profile_detail.html' in [t.name for t in response.templates]
        
        # 4. DB 확인: 프로필이 정말 생성되었는가?
        assert Profile.objects.filter(user=test_user).count() == 1
        assert response.context['profile'].user == test_user

    def test_profile_detail_existing(self, auth_client, test_user):
        """이미 프로필이 있는 유저가 접속했을 때, 기존 프로필을 잘 보여주는지 테스트"""
        
        # 1. 시그널로 이미 생성된 프로필 가져와서 정보 업데이트
        profile = test_user.profile
        profile.business_registration_number = "1234567890"
        profile.business_type = 'individual'
        profile.phone = "010-1234-5678"
        profile.save()
        
        # 2. 페이지 접속
        url = reverse('accounts:profile_detail')
        response = auth_client.get(url)
        
        # 3. 결과 확인
        assert response.status_code == 200
        # 컨텍스트에 담긴 프로필이 우리가 수정한 그 프로필인지 확인
        assert response.context['profile'].user == test_user
        assert response.context['profile'].business_registration_number == "1234567890"
        assert response.context['profile'].business_type == 'individual'

@pytest.mark.django_db
class TestProfileEditView:

    def test_profile_edit_get(self, auth_client, test_user):
        """프로필 수정 페이지 로드 테스트"""
        url = reverse('accounts:profile_edit')
        response = auth_client.get(url)
        
        assert response.status_code == 200
        assert 'form' in response.context
        assert 'accounts/profile_edit.html' in [t.name for t in response.templates]

    def test_profile_edit_success(self, auth_client, test_user):
        """프로필 정보 수정 성공 테스트"""
        url = reverse('accounts:profile_edit')
        
        # 1. 수정할 데이터 준비 (ProfileForm 필드에 맞게)
        new_data = {
            'full_name': '홍길동',  # 필수로 설정되어 있다면 반드시 추가해야 함!
            'business_registration_number': '9876543210', # 기존과 다른 번호
            'business_type': 'corporate',
            'phone': '010-9999-8888'
        }
        
        # 2. POST 요청으로 데이터 전송
        response = auth_client.post(url, new_data)
        
        # 3. 리다이렉트 확인 (accounts:home으로 가기로 설정됨)
        assert response.status_code == 302
        assert response.url == reverse('accounts:home')
        
        # 4. DB에 실제로 반영되었는지 확인
        test_user.profile.refresh_from_db()
        assert test_user.profile.business_registration_number == '9876543210'
        assert test_user.profile.business_type == 'corporate'

    def test_profile_edit_integrity_error(self, auth_client, test_user, django_user_model):
        # 1. 다른 유저 선점
        other_user = django_user_model.objects.create_user(username='other', password='pass')
        # 수정 후: 이미 있는 프로필의 번호만 업데이트합니다.
        other_profile = other_user.profile
        other_profile.business_registration_number = '1112223333'
        other_profile.save()
        
        url = reverse('accounts:profile_edit')
        duplicate_data = {
            'business_registration_number': '1112223333',
            'business_type': 'individual',
            'phone': '010-0000-0000'
        }
        
        response = auth_client.post(url, duplicate_data)
        
        # 2. 어떤 메시지가 담겼는지 리스트로 변환
        messages = [str(m) for m in list(response.context['messages'])]
        
        # 3. 검증 (폼 에러로 인한 "입력 정보를 확인해주세요"가 포함되어 있을 것임)
        assert response.status_code == 200
        assert any("확인" in m or "이미" in m for m in messages)
        
        # 4. 추가 팁: 폼 자체의 에러 메시지도 확인해볼 수 있습니다
        assert 'business_registration_number' in response.context['form'].errors