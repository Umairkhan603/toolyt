import os
import tempfile
import shutil
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from rest_framework.test import APIClient
from apps.videos.models import VideoSource
from apps.processing.models import ProcessingJob
from apps.exports.models import GeneratedClip


class ExportsTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='exportuser1', password='Password123!')
        self.user2 = User.objects.create_user(username='exportuser2', password='Password123!')

        self.video = VideoSource.objects.create(
            user=self.user1,
            title="Export Video",
            rights_confirmed=True,
            status=VideoSource.STATUS_READY
        )
        self.job = ProcessingJob.objects.create(
            user=self.user1,
            video_source=self.video,
            clip_duration=30,
            status=ProcessingJob.STATUS_COMPLETED
        )
        self.clip = GeneratedClip.objects.create(
            job=self.job,
            duration=30.0,
            width=1080,
            height=1920,
            file_size=1024,
            status=GeneratedClip.STATUS_READY
        )
        self.clip.output_file.save("test_clip.mp4", ContentFile(b"fake video mp4 stream"), save=True)

        self.client1 = Client()
        self.client1.force_login(self.user1)

        self.client2 = Client()
        self.client2.force_login(self.user2)

        self.api_client1 = APIClient()
        self.api_client1.force_authenticate(user=self.user1)

        self.api_client2 = APIClient()
        self.api_client2.force_authenticate(user=self.user2)

    def tearDown(self):
        if self.clip.output_file and os.path.exists(self.clip.output_file.path):
            try:
                os.remove(self.clip.output_file.path)
            except OSError:
                pass

    def test_clip_views(self):
        list_res = self.client1.get('/clips/')
        self.assertEqual(list_res.status_code, 200)

        detail_res = self.client1.get(f'/clips/{self.clip.id}/')
        self.assertEqual(detail_res.status_code, 200)

    def test_download_authorization(self):
        # Download succeeds for owner
        res1 = self.client1.get(f'/clips/{self.clip.id}/download/')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1['Content-Type'], 'video/mp4')

        # Download is also publicly accessible without login
        res2 = self.client2.get(f'/clips/{self.clip.id}/download/')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2['Content-Type'], 'video/mp4')

    def test_api_clip_endpoints_isolation(self):
        # Owner gets clip list
        res1 = self.api_client1.get('/api/clips/')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(res1.data), 1)

        # Other user has empty clip list
        res2 = self.api_client2.get('/api/clips/')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(len(res2.data), 0)

        # Other user cannot access clip detail
        res3 = self.api_client2.get(f'/api/clips/{self.clip.id}/')
        self.assertEqual(res3.status_code, 404)

    def test_clip_physical_deletion(self):
        clip_path = self.clip.output_file.path
        self.assertTrue(os.path.exists(clip_path))

        del_res = self.api_client1.delete(f'/api/clips/{self.clip.id}/')
        self.assertEqual(del_res.status_code, 204)
        self.assertFalse(os.path.exists(clip_path))
