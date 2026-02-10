# =============================================================================
# businesses/tests/test_integration.py - 통합 테스트
# =============================================================================

import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User

from apps.businesses.models import Business, Account


# =============================================================================
# 사업장-계좌 통합 시나리오
# =============================================================================

@pytest.mark.django_db
@pytest.mark.integration
class TestBusinessAccountIntegration:
    """사업장과 계좌의 통합 시나리오 테스트"""
    
    def test_create_business_then_create_account(self, authenticated_client, user):
        """사업장 생성 후 계좌 생성 플로우"""
        # 1. 사업장 생성
        business_url = reverse('businesses:business_create')
        business_data = {
            'name': '새 사업장',
            'location': '서울시 강남구',
            'business_type': '소매업',
            'branch_type': 'main',
        }
        
        response = authenticated_client.post(business_url, business_data)
        assert response.status_code == 302
        
        business = Business.objects.get(name='새 사업장')
        
        # 2. 사업장에 연결된 계좌 생성
        account_url = reverse('businesses:account_create')
        account_data = {
            'name': '사업장 주거래',
            'bank_name': '국민은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'business',
            'business': business.pk,
        }
        
        response = authenticated_client.post(account_url, account_data)
        # 디버깅 추가 👇
        if response.status_code != 302:
            print("응답 코드:", response.status_code)
            print("폼 에러:", response.context.get('form').errors if response.context else "context 없음")
            print("제출 데이터:", business_data)
            
        assert response.status_code == 302
        
        # 3. 검증
        account = Account.objects.get(name='사업장 주거래')
        assert account.business == business
        assert account.user == user
        
        # 4. 사업장 상세 페이지에서 계좌 확인
        detail_url = reverse('businesses:business_detail', kwargs={'pk': business.pk})
        response = authenticated_client.get(detail_url)
        
        assert account in response.context['accounts']
    
    def test_delete_business_nullifies_accounts(self, authenticated_client, complete_business_setup):
        """사업장 삭제 시 계좌의 business 필드가 NULL로 변경"""
        setup = complete_business_setup
        business = setup['main_business']
        account = setup['main_account1']
        
        # 사업장 하드 삭제
        business.delete()  # 실제 삭제
        
        # 계좌의 business가 NULL로 변경되었는지 확인
        account.refresh_from_db()
        assert account.business is None
    
    def test_soft_delete_business_then_restore(self, authenticated_client, business, user):
        """사업장 소프트 삭제 후 복구"""
        # 계좌 생성
        account = Account.objects.create(
            user=user,
            business=business,
            name='계좌',
            bank_name='은행',
            account_number='1234-5678-9012'
        )
        
        # 사업장 소프트 삭제
        delete_url = reverse('businesses:business_delete', kwargs={'pk': business.pk})
        response = authenticated_client.post(delete_url)
        assert response.status_code == 302
        
        business.refresh_from_db()
        assert business.is_active is False
        
        # 사업장 복구
        restore_url = reverse('businesses:business_restore', kwargs={'pk': business.pk})
        response = authenticated_client.post(restore_url)
        assert response.status_code == 302
        
        business.refresh_from_db()
        assert business.is_active is True
        
        # 계좌도 여전히 연결되어 있는지 확인
        account.refresh_from_db()
        assert account.business == business


# =============================================================================
# 계좌 생명주기 통합 테스트
# =============================================================================

@pytest.mark.django_db
@pytest.mark.integration
class TestAccountLifecycle:
    """계좌의 전체 생명주기 테스트"""
    
    def test_account_full_lifecycle(self, authenticated_client, user, business):
        """계좌 생성 → 수정 → 삭제 → 복구 → 영구삭제"""
        
        # 1. 계좌 생성
        create_url = reverse('businesses:account_create')
        create_data = {
            'name': '테스트 계좌',
            'bank_name': '국민은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'business',
            'business': business.pk,
        }
        
        response = authenticated_client.post(create_url, create_data)
        assert response.status_code == 302
        
        account = Account.objects.get(name='테스트 계좌')
        account_pk = account.pk
        
        # 2. 계좌 수정
        update_url = reverse('businesses:account_update', kwargs={'pk': account_pk})
        update_data = {
            'name': '수정된 계좌',
            'bank_name': '국민은행',
            'account_number': '1234-5678-9012-3456',
            'account_type': 'business',
        }
        
        response = authenticated_client.post(update_url, update_data)
        assert response.status_code == 302
        
        account.refresh_from_db()
        assert account.name == '수정된 계좌'
        
        # 3. 계좌 소프트 삭제
        delete_url = reverse('businesses:account_delete', kwargs={'pk': account_pk})
        response = authenticated_client.post(delete_url)
        assert response.status_code == 302
        
        account.refresh_from_db()
        assert account.is_active is False
        
        # 4. 계좌 복구
        restore_url = reverse('businesses:account_restore', kwargs={'pk': account_pk})
        response = authenticated_client.post(restore_url)
        assert response.status_code == 302
        
        account.refresh_from_db()
        assert account.is_active is True
        
        # 5. 영구 삭제
        hard_delete_url = reverse('businesses:account_hard_delete', kwargs={'pk': account_pk})
        response = authenticated_client.post(hard_delete_url)
        assert response.status_code == 302
        
        # DB에서 완전히 삭제되었는지 확인
        assert not Account.objects.filter(pk=account_pk).exists()


# =============================================================================
# 필터링 및 검색 통합 테스트
# =============================================================================

@pytest.mark.django_db
@pytest.mark.integration
class TestSearchAndFilter:
    """검색 및 필터링 통합 테스트"""
    
    def test_account_search_filter_combination(self, authenticated_client, user):
        """계좌 검색과 필터 조합"""
        # 다양한 계좌 생성
        business1 = Business.objects.create(user=user, name='사업장1')
        business2 = Business.objects.create(user=user, name='사업장2')
        
        Account.objects.create(
            user=user, business=business1,
            name='국민은행 주거래', bank_name='국민은행',
            account_number='1111', account_type='business'
        )
        Account.objects.create(
            user=user, business=business1,
            name='신한은행 적금', bank_name='신한은행',
            account_number='2222', account_type='business'
        )
        Account.objects.create(
            user=user, business=business2,
            name='국민은행 개인', bank_name='국민은행',
            account_number='3333', account_type='personal'
        )
        
        # 사업용 + 사업장1 + "국민은행" 검색
        url = reverse('businesses:account_list')
        response = authenticated_client.get(url, {
            'account_type': 'business',
            'business': business1.pk,
            'search': '국민은행'
        })
        
        accounts = list(response.context['page_obj'])
        assert len(accounts) == 1
        assert accounts[0].name == '국민은행 주거래'
    
    def test_business_search_filter_combination(self, authenticated_client, user):
        """사업장 검색과 필터 조합"""
        Business.objects.create(
            user=user, name='강남 본점',
            location='서울시 강남구',
            business_type='소매업',
            branch_type='main'
        )
        Business.objects.create(
            user=user, name='강남 지점1',
            location='서울시 강남구',
            business_type='소매업',
            branch_type='branch'
        )
        Business.objects.create(
            user=user, name='서초 본점',
            location='서울시 서초구',
            business_type='제조업',
            branch_type='main'
        )
        
        # 지점 + 소매업 + "강남" 검색
        url = reverse('businesses:business_list')
        response = authenticated_client.get(url, {
            'branch_type': 'branch',
            'business_type': '소매업',
            'search': '강남'
        })
        
        businesses = list(response.context['page_obj'])
        assert len(businesses) == 1
        assert businesses[0].name == '강남 지점1'


# =============================================================================
# 대시보드 및 통계 통합 테스트
# =============================================================================

@pytest.mark.django_db
@pytest.mark.integration
class TestDashboardIntegration:
    """대시보드 통계 통합 테스트"""
    
    def test_account_summary_with_real_data(self, authenticated_client, complete_business_setup):
        """실제 데이터를 사용한 계좌 요약"""
        url = reverse('businesses:account_summary')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        
        # 총 계좌 수 (4개)
        assert response.context['total_count'] == 4
        
        # 사업용 (3개)
        assert response.context['business_count'] == 3
        
        # 개인용 (1개)
        assert response.context['personal_count'] == 1
        
        # 총 잔액 (11,000,000원)
        expected_total = Decimal('5000000') + Decimal('2000000') + \
                        Decimal('1000000') + Decimal('3000000')
        assert response.context['total_balance'] == expected_total
    
    def test_business_account_statistics(self, authenticated_client, complete_business_setup):
        """사업장별 계좌 통계"""
        setup = complete_business_setup
        main_business = setup['main_business']
        
        url = reverse('businesses:business_detail', kwargs={'pk': main_business.pk})
        response = authenticated_client.get(url)
        
        # 본점 계좌 2개
        assert response.context['account_count'] == 2
        
        # 본점 총 잔액 (7,000,000원)
        expected_balance = Decimal('5000000') + Decimal('2000000')
        assert response.context['total_balance'] == expected_balance


# =============================================================================
# 권한 및 보안 통합 테스트
# =============================================================================

@pytest.mark.django_db
@pytest.mark.integration
class TestSecurityIntegration:
    """보안 및 권한 통합 테스트"""
    
    def test_user_cannot_access_other_users_data(
        self, client, user, other_user, business, account
    ):
        """다른 사용자의 데이터 접근 불가"""
        # 다른 사용자로 로그인
        client.login(username='otheruser', password='testpass123')
        
        # 사업장 상세 접근 시도
        business_url = reverse('businesses:business_detail', kwargs={'pk': business.pk})
        response = client.get(business_url)
        assert response.status_code == 404
        
        # 계좌 상세 접근 시도
        account_url = reverse('businesses:account_detail', kwargs={'pk': account.pk})
        response = client.get(account_url)
        assert response.status_code == 404
        
        # 사업장 수정 시도
        update_url = reverse('businesses:business_update', kwargs={'pk': business.pk})
        response = client.get(update_url)
        assert response.status_code == 404
        
        # 계좌 삭제 시도
        delete_url = reverse('businesses:account_delete', kwargs={'pk': account.pk})
        response = client.post(delete_url)
        assert response.status_code == 404
    
    def test_deleted_data_not_visible_in_list(self, authenticated_client, user):
        """삭제된 데이터는 일반 목록에 표시 안 됨"""
        # 활성 사업장
        active_business = Business.objects.create(user=user, name='활성')
        
        # 삭제된 사업장
        deleted_business = Business.objects.create(user=user, name='삭제됨')
        deleted_business.soft_delete()
        
        # 일반 목록
        list_url = reverse('businesses:business_list')
        response = authenticated_client.get(list_url)
        
        businesses = list(response.context['page_obj'])
        assert active_business in businesses
        assert deleted_business not in businesses
        
        # 삭제된 목록
        deleted_url = reverse('businesses:business_deleted_list')
        response = authenticated_client.get(deleted_url)
        
        businesses = list(response.context['page_obj'])
        assert deleted_business in businesses
        assert active_business not in businesses


# =============================================================================
# 페이지네이션 통합 테스트
# =============================================================================

@pytest.mark.django_db
@pytest.mark.integration
class TestPaginationIntegration:
    """페이지네이션 통합 테스트"""
    
    def test_pagination_across_filters(self, authenticated_client, user):
        """필터 적용 시 페이지네이션"""
        business = Business.objects.create(user=user, name='사업장')
        
        # 사업용 계좌 25개 생성
        for i in range(25):
            Account.objects.create(
                user=user, business=business,
                name=f'사업용{i}', bank_name='은행',
                account_number=f'{i:04d}', account_type='business'
            )
        
        # 개인용 계좌 5개 생성
        for i in range(5):
            Account.objects.create(
                user=user, name=f'개인용{i}',
                bank_name='은행', account_number=f'9{i:03d}',
                account_type='personal'
            )
        
        # 사업용 필터 + 페이지네이션
        url = reverse('businesses:account_list')
        
        # 1페이지 (20개)
        response = authenticated_client.get(url, {
            'account_type': 'business',
            'page': 1
        })
        assert len(response.context['page_obj']) == 20
        
        # 2페이지 (5개)
        response = authenticated_client.get(url, {
            'account_type': 'business',
            'page': 2
        })
        assert len(response.context['page_obj']) == 5
        
        # 개인용 필터 (1페이지에 모두 표시)
        response = authenticated_client.get(url, {
            'account_type': 'personal'
        })
        assert len(response.context['page_obj']) == 5


# =============================================================================
# 에러 처리 통합 테스트
# =============================================================================

@pytest.mark.django_db
@pytest.mark.integration
class TestErrorHandling:
    """에러 처리 통합 테스트"""
    
    def test_404_on_nonexistent_resource(self, authenticated_client):
        """존재하지 않는 리소스 접근"""
        # 존재하지 않는 사업장
        url = reverse('businesses:business_detail', kwargs={'pk': 99999})
        response = authenticated_client.get(url)
        assert response.status_code == 404
        
        # 존재하지 않는 계좌
        url = reverse('businesses:account_detail', kwargs={'pk': 99999})
        response = authenticated_client.get(url)
        assert response.status_code == 404
    
    def test_invalid_form_resubmission(self, authenticated_client):
        """잘못된 폼 재제출"""
        url = reverse('businesses:business_create')
        
        # 잘못된 데이터 제출
        invalid_data = {
            'name': '',  # 필수 필드 누락
            'registration_number': '123',  # 잘못된 형식
        }
        
        response = authenticated_client.post(url, invalid_data)
        
        # 폼 에러와 함께 같은 페이지 표시
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['form'].errors
        
        # 에러 메시지 존재
        from django.contrib.messages import get_messages
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) > 0