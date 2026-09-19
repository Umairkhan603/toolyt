from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from apps.videos.models import VideoSource
from apps.videos.validators import sanitize_filename, validate_video_file_extension, validate_video_file_size


class VideosTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='creator1', password='Password123!')
        self.user2 = User.objects.create_user(username='creator2', password='Password123!')
        self.client1 = Client()
        self.client1.force_login(self.user1)

        self.api_client1 = APIClient()
        self.api_client1.force_authenticate(user=self.user1)

        self.api_client2 = APIClient()
        self.api_client2.force_authenticate(user=self.user2)

    def test_filename_sanitization_and_security(self):
        # Path traversal attempt
        clean1 = sanitize_filename('../../etc/passwd.mp4')
        self.assertNotIn('..', clean1)
        self.assertNotIn('/', clean1)
        self.assertTrue(clean1.endswith('.mp4'))

        # Command injection attempt in filename
        clean2 = sanitize_filename('video;rm -rf /;$(calc).mp4')
        self.assertNotIn(';', clean2)
        self.assertNotIn('$', clean2)
        self.assertNotIn('(', clean2)

    def test_extension_validator(self):
        valid_file = SimpleUploadedFile("sample.mp4", b"data", content_type="video/mp4")
        validate_video_file_extension(valid_file)  # Should not raise

        invalid_file = SimpleUploadedFile("script.sh", b"data", content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_video_file_extension(invalid_file)

    def test_upload_missing_rights_rejected(self):
        test_file = SimpleUploadedFile("test.mp4", b"dummy video bytes", content_type="video/mp4")
        # Attempt upload without rights confirmation
        response = self.client1.post('/videos/upload/', {
            'original_file': test_file,
            'title': 'Test Video',
            # rights_confirmed is omitted
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(VideoSource.objects.filter(user=self.user1).exists())

    def test_quota_exhaustion_rejected(self):
        # Set user quota very small
        self.user1.profile.storage_quota = 100
        self.user1.profile.save()

        test_file = SimpleUploadedFile("big.mp4", b"A" * 500, content_type="video/mp4")
        response = self.client1.post('/videos/upload/', {
            'original_file': test_file,
            'title': 'Big Video',
            'rights_confirmed': True,
        })
        self.assertFalse(VideoSource.objects.filter(user=self.user1).exists())

    def test_api_video_source_isolation(self):
        # Create video for user1
        v1 = VideoSource.objects.create(
            user=self.user1,
            title="User 1 Video",
            rights_confirmed=True,
            status=VideoSource.STATUS_READY
        )

        # User 1 can view
        res1 = self.api_client1.get(f'/api/videos/{v1.id}/')
        self.assertEqual(res1.status_code, 200)

        # User 2 cannot view user 1's video
        res2 = self.api_client2.get(f'/api/videos/{v1.id}/')
        self.assertEqual(res2.status_code, 404)

        # User 2 cannot delete user 1's video
        del_res = self.api_client2.delete(f'/api/videos/{v1.id}/')
        self.assertEqual(del_res.status_code, 404)
        self.assertTrue(VideoSource.objects.filter(id=v1.id).exists())

    def test_youtube_url_detection(self):
        from apps.videos.services.youtube import YouTubeDownloaderService
        self.assertTrue(YouTubeDownloaderService.is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(YouTubeDownloaderService.is_youtube_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertTrue(YouTubeDownloaderService.is_youtube_url("https://youtube.com/shorts/dQw4w9WgXcQ"))
        self.assertFalse(YouTubeDownloaderService.is_youtube_url("https://example.com/not-youtube"))

    def test_home_public_youtube_convert_submission(self):
        from unittest.mock import patch
        guest_client = Client()

        with patch('apps.processing.tasks.process_video_job_task.delay') as mock_delay:
            res = guest_client.post('/', {
                'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'clip_count': '5',
                'clip_duration': '30',
                'crop_mode': 'blur',
                'caption_enabled': 'on',
                'anti_copyright_enabled': 'on'
            })
            self.assertEqual(res.status_code, 302)
            self.assertTrue(res.url.startswith('/processing/jobs/'))
            mock_delay.assert_called_once()

    def test_highlight_detector_service(self):
        from apps.videos.services.highlights import HighlightDetectorService

        # 1. Heatmap detection test
        heatmap_data = [{'start_time': i * 60.0, 'value': 0.1 * (i % 5)} for i in range(20)]
        hl_heat = HighlightDetectorService.detect_highlights(
            {'duration': 1200, 'heatmap': heatmap_data},
            clip_duration=30,
            clip_count=5
        )
        self.assertEqual(len(hl_heat), 5)
        for h in hl_heat:
            self.assertIn('start_time', h)
            self.assertEqual(h['duration'], 30)

        # 2. Chapters detection test
        chapters_data = [
            {'start_time': 0, 'end_time': 100, 'title': 'Intro'},
            {'start_time': 100, 'end_time': 400, 'title': 'Core Science Analysis'},
            {'start_time': 400, 'end_time': 800, 'title': 'Deep Insights Discussion'},
            {'start_time': 800, 'end_time': 1200, 'title': 'Actionable Habits'},
            {'start_time': 1200, 'end_time': 1600, 'title': 'Summary and Q&A'},
            {'start_time': 1600, 'end_time': 1800, 'title': 'Outro'}
        ]
        hl_chap = HighlightDetectorService.detect_highlights(
            {'duration': 1800, 'chapters': chapters_data},
            clip_duration=30,
            clip_count=4
        )
        self.assertEqual(len(hl_chap), 4)

        # 3. Fallback distribution test
        hl_dist = HighlightDetectorService.detect_highlights(
            {'duration': 600},
            clip_duration=30,
            clip_count=5
        )
        self.assertEqual(len(hl_dist), 5)

    def test_ffmpeg_anti_copyright_filters(self):
        from apps.processing.services.ffmpeg import FFmpegService
        vf = FFmpegService.build_video_filter(crop_mode='blur', anti_copyright=True)
        self.assertIn('eq=contrast=', vf)
        self.assertIn('unsharp=', vf)
        self.assertIn('setpts=PTS/1.03', vf)

        vf_off = FFmpegService.build_video_filter(crop_mode='center', anti_copyright=False)
        self.assertNotIn('setpts=PTS/1.03', vf_off)

    def test_requested_duration_preserved_and_reduced_if_video_shorter(self):
        from apps.videos.services.highlights import HighlightDetectorService

        # Case 1: 375s video with 90s requested and 5 clips -> each clip MUST be 90s
        highlights = HighlightDetectorService.detect_highlights(
            {'duration': 375.0},
            clip_duration=90.0,
            clip_count=5
        )
        self.assertEqual(len(highlights), 5)
        for h in highlights:
            self.assertEqual(h['duration'], 90.0)
            self.assertLessEqual(h['end_time'], 375.0)

        # Case 2: 60s video with 90s requested -> duration is reduced to 60s
        hl_short = HighlightDetectorService.detect_highlights(
            {'duration': 60.0},
            clip_duration=90.0,
            clip_count=3
        )
        self.assertEqual(len(hl_short), 1)
        self.assertEqual(hl_short[0]['duration'], 60.0)
        self.assertEqual(hl_short[0]['start_time'], 0.0)
        self.assertEqual(hl_short[0]['end_time'], 60.0)

