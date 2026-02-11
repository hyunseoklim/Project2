# =============================================================================
# businesses/tests/test_views_business.py - pytest Views 테스트 (Part 2: Business Views)
# =============================================================================

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import Client
from django.contrib.messages import get_messages

from apps.businesses.models import Business, Account


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """테스트 클라이언트"""
    return Client()


@pytest.fixture
def user(db):
    """테스트용 사용자"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def other_user(db):
    """다른 사용자"""
    return User.objects.create_user(
        username='otheruser',
        email='other@example.com',
        password='testpass123'
    )


@pytest.fixture
def authenticated_client(client, user):
    """로그인된 클라이언트"""
    client.login(username='testuser', password='testpass123')
    return client


@pytest.fixture
def business(db, user):
    """테스트용 사업장"""
    return Business.objects.create(
        user=user,
        name='강남점',
        location='서울시 강남구',
        business_type='소매업',
        branch_type='main'
    )


@pytest.fixture
def branch_business(db, user):
    """지점 사업장"""
    return Business.objects.create(
        user=user,
        name='강남점 지점1',
        location='서울시 강남구 역삼동',
        business_type='소매업',
        branch_type='branch'
    )


@pytest.fixture
def multiple_businesses(db, user):
    """여러 사업장 생성 (페이지네이션 테스트용)"""
    businesses = []
    for i in range(25):
        business = Business.objects.create(
            user=user,
            name=f'사업장{i:02d}',
            location=f'위치{i}',
            business_type='소매업' if i % 2 == 0 else '제조업',
            branch_type='main' if i % 3 == 0 else 'branch'
        )
        businesses.append(business)
    return businesses


# =============================================================================
# business_list 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessListView:
    """사업장 목록 뷰 테스트"""
    
    def test_business_list_requires_login(self, client):
        """로그인 필요 테스트"""
        url = reverse('businesses:business_list')
        response = client.get(url)
        
        assert response.status_code == 302
        assert '/login/' in response.url
    
    def test_business_list_success(self, authenticated_client, business):
        """사업장 목록 조회 성공"""
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'page_obj' in response.context
        assert 'search_form' in response.context
        assert business in response.context['page_obj']
    
    def test_business_list_only_shows_own_businesses(self, authenticated_client, business, other_user):
        """본인 사업장만 표시"""
        other_business = Business.objects.create(
            user=other_user,
            name='남의 사업장'
        )
        
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url)
        
        businesses = list(response.context['page_obj'])
        assert business in businesses
        assert other_business not in businesses
    
    def test_business_list_filter_by_branch_type(self, authenticated_client, business, branch_business):
        """지점 구분으로 필터링"""
        url = reverse('businesses:business_list')
        
        # 본점만 필터링
        response = authenticated_client.get(url, {'branch_type': 'main'})
        businesses = list(response.context['page_obj'])
        assert business in businesses
        assert branch_business not in businesses
        
        # 지점만 필터링
        response = authenticated_client.get(url, {'branch_type': 'branch'})
        businesses = list(response.context['page_obj'])
        assert branch_business in businesses
        assert business not in businesses
    
    def test_business_list_filter_by_business_type(self, authenticated_client, user):
        """업종으로 필터링"""
        retail = Business.objects.create(
            user=user, name='소매점', business_type='소매업'
        )
        manufacturing = Business.objects.create(
            user=user, name='공장', business_type='제조업'
        )
        
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {'business_type': '소매업'})
        
        businesses = list(response.context['page_obj'])
        assert retail in businesses
        assert manufacturing not in businesses
    
    def test_business_list_search_by_name(self, authenticated_client, user):
        """사업장명으로 검색"""
        business1 = Business.objects.create(user=user, name='강남점')
        business2 = Business.objects.create(user=user, name='역삼점')
        
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {'search': '강남'})
        
        businesses = list(response.context['page_obj'])
        assert business1 in businesses
        assert business2 not in businesses
    
    def test_business_list_search_by_location(self, authenticated_client, user):
        """위치로 검색"""
        business1 = Business.objects.create(
            user=user, name='점포1', location='서울시 강남구'
        )
        business2 = Business.objects.create(
            user=user, name='점포2', location='서울시 서초구'
        )
        
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {'search': '강남'})
        
        businesses = list(response.context['page_obj'])
        assert business1 in businesses
        assert business2 not in businesses
    
    def test_business_list_ordering(self, authenticated_client, user):
        """사업장 정렬 테스트 (이름순)"""
        Business.objects.create(user=user, name='다점')
        Business.objects.create(user=user, name='가점')
        Business.objects.create(user=user, name='나점')
        
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url)
        
        businesses = list(response.context['page_obj'])
        names = [b.name for b in businesses]
        
        assert names == ['가점', '나점', '다점']
    
    def test_business_list_pagination(self, authenticated_client, multiple_businesses):
        """페이지네이션 테스트 (페이지당 20개)"""
        url = reverse('businesses:business_list')
        
        # 1페이지
        response = authenticated_client.get(url)
        assert len(response.context['page_obj']) == 20
        
        # 2페이지
        response = authenticated_client.get(url, {'page': 2})
        assert len(response.context['page_obj']) == 5
    
    def test_business_list_statistics(self, authenticated_client, user):
        """통계 정보 확인"""
        Business.objects.create(user=user, name='본점1', branch_type='main')
        Business.objects.create(user=user, name='본점2', branch_type='main')
        Business.objects.create(user=user, name='지점1', branch_type='branch')
        
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url)
        
        assert response.context['total_count'] == 3
        assert response.context['main_count'] == 2
        assert response.context['branch_count'] == 1
    
    def test_business_list_template_used(self, authenticated_client, business):
        """올바른 템플릿 사용 확인"""
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url)
        
        assert 'businesses/business_list.html' in [t.name for t in response.templates]


# =============================================================================
# business_detail 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessDetailView:
    """사업장 상세 뷰 테스트"""
    
    def test_business_detail_requires_login(self, client, business):
        """로그인 필요"""
        url = reverse('businesses:business_detail', kwargs={'pk': business.pk})
        response = client.get(url)
        
        assert response.status_code == 302
        assert '/login/' in response.url
    
    def test_business_detail_success(self, authenticated_client, business):
        """사업장 상세 조회 성공"""
        url = reverse('businesses:business_detail', kwargs={'pk': business.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.context['business'] == business
    
    def test_business_detail_other_user_business_404(self, authenticated_client, other_user):
        """다른 사용자의 사업장 조회 시 404"""
        other_business = Business.objects.create(
            user=other_user,
            name='남의 사업장'
        )
        
        url = reverse('businesses:business_detail', kwargs={'pk': other_business.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 404
    
    def test_business_detail_shows_accounts(self, authenticated_client, business, user):
        """연결된 계좌 목록 표시"""
        # 이 사업장의 계좌 2개
        account1 = Account.objects.create(
            user=user, business=business,
            name='계좌1', bank_name='은행', account_number='1111'
        )
        account2 = Account.objects.create(
            user=user, business=business,
            name='계좌2', bank_name='은행', account_number='2222'
        )
        
        # 다른 사업장의 계좌
        other_business = Business.objects.create(user=user, name='다른사업장')
        account3 = Account.objects.create(
            user=user, business=other_business,
            name='계좌3', bank_name='은행', account_number='3333'
        )
        
        url = reverse('businesses:business_detail', kwargs={'pk': business.pk})
        response = authenticated_client.get(url)
        
        accounts = list(response.context['accounts'])
        assert account1 in accounts
        assert account2 in accounts
        assert account3 not in accounts
    
    def test_business_detail_statistics(self, authenticated_client, business, user):
        """통계 정보 확인"""
        Account.objects.create(
            user=user, business=business,
            name='계좌1', bank_name='은행', account_number='1111',
            balance=Decimal('500000')
        )
        Account.objects.create(
            user=user, business=business,
            name='계좌2', bank_name='은행', account_number='2222',
            balance=Decimal('300000')
        )
        
        url = reverse('businesses:business_detail', kwargs={'pk': business.pk})
        response = authenticated_client.get(url)
        
        assert response.context['account_count'] == 2
        assert response.context['total_balance'] == Decimal('800000')


# =============================================================================
# business_create 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessCreateView:
    """사업장 생성 뷰 테스트"""
    
    def test_business_create_get_requires_login(self, client):
        """로그인 필요 (GET)"""
        url = reverse('businesses:business_create')
        response = client.get(url)
        
        assert response.status_code == 302
    
    def test_business_create_get_success(self, authenticated_client):
        """사업장 생성 폼 표시"""
        url = reverse('businesses:business_create')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'form' in response.context
    
    def test_business_create_post_success(self, authenticated_client):
        """사업장 생성 성공"""
        url = reverse('businesses:business_create')
        data = {
            'name': '새 사업장',
            'location': '서울시 강남구',
            'business_type': '소매업',
            'branch_type': 'main',
            'registration_number': '123-45-67890',
        }
        
        response = authenticated_client.post(url, data)
        
        assert response.status_code == 302
        assert Business.objects.filter(name='새 사업장').exists()
        
        messages = list(get_messages(response.wsgi_request))
        assert any('생성되었습니다' in str(m) for m in messages)
    
    def test_business_create_minimal_data(self, authenticated_client):
        """최소 필수 필드만으로 생성"""
        url = reverse('businesses:business_create')
        data = {
            'name': '최소사업장',
            'branch_type': 'main',
        }
        
        response = authenticated_client.post(url, data)
        
        assert response.status_code == 302
        assert Business.objects.filter(name='최소사업장').exists()
    
    def test_business_create_invalid_data(self, authenticated_client):
        """유효하지 않은 데이터로 생성 시도"""
        url = reverse('businesses:business_create')
        data = {
            'name': '',  # 필수 필드 누락
        }
        
        response = authenticated_client.post(url, data)
        
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['form'].errors
    
    def test_business_create_sets_user_automatically(self, authenticated_client, user):
        """사업장 생성 시 사용자 자동 설정"""
        url = reverse('businesses:business_create')
        data = {
            'name': '새 사업장',
            'branch_type': 'main',
        }
        
        authenticated_client.post(url, data)
        
        business = Business.objects.get(name='새 사업장')
        assert business.user == user
    
    def test_business_create_duplicate_name(self, authenticated_client, business):
        """중복 사업장명 생성 시도"""
        url = reverse('businesses:business_create')
        data = {
            'name': business.name,  # 중복
            'branch_type': 'branch',
        }
        
        response = authenticated_client.post(url, data)
        
        messages = list(get_messages(response.wsgi_request))
        assert any('이미 등록된' in str(m) or '실패' in str(m) for m in messages)
    
    def test_business_create_registration_number_normalization(self, authenticated_client):
        """사업자등록번호 자동 정규화"""
        url = reverse('businesses:business_create')
        data = {
            'name': '테스트',
            'branch_type': 'main',
            'registration_number': '1234567890',  # 하이픈 없음
        }
        
        authenticated_client.post(url, data)
        
        business = Business.objects.get(name='테스트')
        assert business.registration_number == '123-45-67890'


# =============================================================================
# business_update 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessUpdateView:
    """사업장 수정 뷰 테스트"""
    
    def test_business_update_get_success(self, authenticated_client, business):
        """사업장 수정 폼 표시"""
        url = reverse('businesses:business_update', kwargs={'pk': business.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['business'] == business
    
    def test_business_update_post_success(self, authenticated_client, business):
        """사업장 수정 성공"""
        url = reverse('businesses:business_update', kwargs={'pk': business.pk})
        data = {
            'name': '수정된 사업장명',
            'location': business.location,
            'business_type': business.business_type,
            'branch_type': business.branch_type,
        }
        
        response = authenticated_client.post(url, data)
        
        assert response.status_code == 302
        
        business.refresh_from_db()
        assert business.name == '수정된 사업장명'
        
        messages = list(get_messages(response.wsgi_request))
        assert any('수정되었습니다' in str(m) for m in messages)
    
    def test_business_update_other_user_business_404(self, authenticated_client, other_user):
        """다른 사용자의 사업장 수정 시도"""
        other_business = Business.objects.create(
            user=other_user,
            name='남의 사업장'
        )
        
        url = reverse('businesses:business_update', kwargs={'pk': other_business.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 404


# =============================================================================
# business_delete 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessDeleteView:
    """사업장 삭제 뷰 테스트"""
    
    def test_business_delete_get_confirmation_page(self, authenticated_client, business):
        """삭제 확인 페이지 표시"""
        url = reverse('businesses:business_delete', kwargs={'pk': business.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.context['business'] == business
        assert 'account_count' in response.context
    
    def test_business_delete_post_success(self, authenticated_client, business):
        """사업장 소프트 삭제 성공"""
        url = reverse('businesses:business_delete', kwargs={'pk': business.pk})
        response = authenticated_client.post(url)
        
        assert response.status_code == 302
        
        business.refresh_from_db()
        assert business.is_active is False
        
        messages = list(get_messages(response.wsgi_request))
        assert any('삭제되었습니다' in str(m) for m in messages)
    
    def test_business_delete_shows_account_count(self, authenticated_client, business, user):
        """연결된 계좌 수 표시"""
        # 계좌 3개 생성
        for i in range(3):
            Account.objects.create(
                user=user, business=business,
                name=f'계좌{i}', bank_name='은행',
                account_number=f'{i}111'
            )
        
        url = reverse('businesses:business_delete', kwargs={'pk': business.pk})
        response = authenticated_client.get(url)
        
        assert response.context['account_count'] == 3
    
    def test_business_delete_other_user_business_404(self, authenticated_client, other_user):
        """다른 사용자의 사업장 삭제 시도"""
        other_business = Business.objects.create(
            user=other_user,
            name='남의 사업장'
        )
        
        url = reverse('businesses:business_delete', kwargs={'pk': other_business.pk})
        response = authenticated_client.post(url)
        
        assert response.status_code == 404


# =============================================================================
# business_restore 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessRestoreView:
    """사업장 복구 뷰 테스트"""
    
    def test_business_restore_get_confirmation_page(self, authenticated_client, business):
        """복구 확인 페이지"""
        business.soft_delete()
        
        url = reverse('businesses:business_restore', kwargs={'pk': business.pk})
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.context['business'] == business
    
    def test_business_restore_post_success(self, authenticated_client, business):
        """사업장 복구 성공"""
        business.soft_delete()
        
        url = reverse('businesses:business_restore', kwargs={'pk': business.pk})
        response = authenticated_client.post(url)
        
        assert response.status_code == 302
        
        business.refresh_from_db()
        assert business.is_active is True
        
        messages = list(get_messages(response.wsgi_request))
        assert any('복구되었습니다' in str(m) for m in messages)
    
    def test_business_restore_already_active_warning(self, authenticated_client, business):
        """이미 활성 상태인 사업장 복구 시도"""
        url = reverse('businesses:business_restore', kwargs={'pk': business.pk})
        response = authenticated_client.post(url)
        
        messages = list(get_messages(response.wsgi_request))
        assert any('이미 활성' in str(m) for m in messages)


# =============================================================================
# business_deleted_list 뷰 테스트
# =============================================================================

@pytest.mark.django_db
class TestBusinessDeletedListView:
    """삭제된 사업장 목록 뷰 테스트"""
    
    def test_business_deleted_list_requires_login(self, client):
        """로그인 필요"""
        url = reverse('businesses:business_deleted_list')
        response = client.get(url)
        
        assert response.status_code == 302
    
    def test_business_deleted_list_shows_only_deleted(self, authenticated_client, user):
        """삭제된 사업장만 표시"""
        active = Business.objects.create(user=user, name='활성')
        deleted = Business.objects.create(user=user, name='삭제됨')
        deleted.soft_delete()
        
        url = reverse('businesses:business_deleted_list')
        response = authenticated_client.get(url)
        
        businesses = list(response.context['page_obj'])
        assert deleted in businesses
        assert active not in businesses
    
    def test_business_deleted_list_pagination(self, authenticated_client, user):
        """페이지네이션 테스트"""
        # 삭제된 사업장 25개 생성
        for i in range(25):
            business = Business.objects.create(user=user, name=f'사업장{i}')
            business.soft_delete()
        
        url = reverse('businesses:business_deleted_list')
        
        # 1페이지
        response = authenticated_client.get(url)
        assert len(response.context['page_obj']) == 20
        
        # 2페이지
        response = authenticated_client.get(url, {'page': 2})
        assert len(response.context['page_obj']) == 5


# =============================================================================
# 헬퍼 함수 테스트
# =============================================================================

@pytest.mark.django_db
class TestHelperFunctions:
    """_get_optimized_page 헬퍼 함수 테스트"""
    
    def test_pagination_first_page(self, authenticated_client, multiple_businesses):
        """첫 페이지 조회"""
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {'page': 1})
        
        assert response.status_code == 200
        assert len(response.context['page_obj']) == 20
    
    def test_pagination_invalid_page_number(self, authenticated_client, multiple_businesses):
        """잘못된 페이지 번호 (문자열)"""
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {'page': 'invalid'})
        
        # 1페이지로 폴백
        assert response.status_code == 200
        assert len(response.context['page_obj']) == 20
    
    def test_pagination_negative_page_number(self, authenticated_client, multiple_businesses):
        """음수 페이지 번호"""
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {'page': -1})
        
        # 1페이지로 폴백
        assert response.status_code == 200
    
    def test_pagination_too_large_page_number(self, authenticated_client, multiple_businesses):
        """존재하지 않는 큰 페이지 번호"""
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {'page': 9999})
        
        # 마지막 페이지로 폴백
        assert response.status_code == 200
        assert len(response.context['page_obj']) == 5  # 25개 중 마지막 5개