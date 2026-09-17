from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.audit.models import AuditEvent
from apps.audit.utils import record_audit_event, sanitize_metadata


class AuditTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='audituser', password='Password123!')
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_sanitize_metadata(self):
        data = {
            'username': 'john',
            'password': 'supersecretpassword',
            'api_token': 'xyz123',
            'action': 'login'
        }
        cleaned = sanitize_metadata(data)
        self.assertEqual(cleaned['username'], 'john')
        self.assertEqual(cleaned['action'], 'login')
        self.assertEqual(cleaned['password'], '***REDACTED***')
        self.assertEqual(cleaned['api_token'], '***REDACTED***')

    def test_record_audit_event(self):
        event = record_audit_event(
            user=self.user,
            event_type='test.action',
            metadata={'ip': '127.0.0.1', 'secret_key': 'abc'}
        )
        self.assertEqual(event.event_type, 'test.action')
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.metadata['secret_key'], '***REDACTED***')

    def test_audit_api_list(self):
        record_audit_event(user=self.user, event_type='test.event.1')
        record_audit_event(user=self.user, event_type='test.event.2')

        res = self.api_client.get('/api/audit/')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data), 2)
