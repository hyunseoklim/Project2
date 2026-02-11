from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from apps.businesses.models import Business, Account
from apps.businesses.admin import BusinessAdmin, AccountAdmin
from django.contrib.auth import get_user_model

User = get_user_model()

class BusinessAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.user = User.objects.create(username="testuser_admin1")
        self.business = Business.objects.create(
            name="테스트사업장",
            user=self.user,
            registration_number="123-45-67890",
            branch_type="main",
            business_type="type1",
            location="서울",
            is_active=True
        )
        self.admin = BusinessAdmin(Business, self.site)

    def test_masked_registration_number(self):
        masked = self.admin.get_masked_registration_number(self.business)
        self.assertEqual(masked, "123-45-*****")

    def test_account_count(self):
        Account.objects.create(
            name="계좌1",
            bank_name="은행",
            account_number="123456789012",
            business=self.business,
            user=self.user,
            balance=10000,
            is_active=True
        )
        count = self.admin.get_account_count(self.business)
        self.assertEqual(count, "1개")

class AccountAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.user = User.objects.create(username="testuser_admin2")
        self.business = Business.objects.create(
            name="사업장2",
            user=self.user,
            registration_number="987-65-43210",
            branch_type="main",
            business_type="type2",
            location="부산",
            is_active=True
        )
        self.account = Account.objects.create(
            name="계좌2",
            bank_name="은행2",
            account_number="987654321098",
            business=self.business,
            user=self.user,
            balance=-5000,
            is_active=True
        )
        self.admin = AccountAdmin(Account, self.site)

    def test_masked_account_number(self):
        masked = self.admin.get_masked_account_number(self.account)
        self.assertEqual(masked, "987****098")

    def test_balance_display(self):
        html = self.admin.get_balance_display(self.account)
        self.assertIn("color:red", html)
