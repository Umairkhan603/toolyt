from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import UserProfile


class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.api_client = APIClient()
        self.user = User.objects.create_user(username='testcreator', email='creator@example.com', password='Password123!')

    def test_user_profile_creation(self):
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.storage_quota, 2 * 1024 * 1024 * 1024)
        self.assertEqual(self.user.profile.get_used_storage(), 0)
        self.assertTrue(self.user.profile.can_upload(100 * 1024 * 1024))

    def test_registration_view(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'SecretPass123!',
            'password2': 'SecretPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_login_and_logout_views(self):
        login_res = self.client.post(reverse('accounts:login'), {
            'username': 'testcreator',
            'password': 'Password123!'
        })
        self.assertEqual(login_res.status_code, 302)

        logout_res = self.client.get(reverse('accounts:logout'))
        self.assertEqual(logout_res.status_code, 302)

    def test_auth_api_endpoints(self):
        # API Register
        reg_res = self.api_client.post('/api/auth/register/', {
            'username': 'apiuser',
            'email': 'apiuser@example.com',
            'password': 'SecurePassword123!'
        })
        self.assertEqual(reg_res.status_code, 201)

        # API Login
        login_res = self.api_client.post('/api/auth/login/', {
            'username': 'apiuser',
            'password': 'SecurePassword123!'
        })
        self.assertEqual(login_res.status_code, 200)

        # API Profile
        prof_res = self.api_client.get('/api/auth/profile/')
        self.assertEqual(prof_res.status_code, 200)
        self.assertEqual(prof_res.data['username'], 'apiuser')

        # API Logout
        logout_res = self.api_client.post('/api/auth/logout/')
        self.assertEqual(logout_res.status_code, 200)
