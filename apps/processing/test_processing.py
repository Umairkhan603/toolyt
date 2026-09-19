import os
import shutil
import tempfile
import subprocess
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files import File
from rest_framework.test import APIClient
from apps.videos.models import VideoSource
from apps.processing.models import ProcessingJob
from apps.processing.services.ffmpeg import FFmpegService, VideoProcessingError
from apps.processing.tasks import process_video_job_task
from apps.exports.models import GeneratedClip


class ProcessingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_dir = tempfile.mkdtemp()
        cls.sample_video_path = os.path.join(cls.test_dir, "test_input.mp4")

        # Generate a real 2-second 1280x720 test video with audio using FFmpeg
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=2:size=1280x720:rate=25',
            '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=2',
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-c:a', 'aac', '-b:a', '64k',
            '-pix_fmt', 'yuv420p',
            cls.sample_video_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.user1 = User.objects.create_user(username='director1', password='Password123!')
        self.user2 = User.objects.create_user(username='director2', password='Password123!')

        self.video = VideoSource.objects.create(
            user=self.user1,
            title="Sample 720p Video",
            duration=2.0,
            width=1280,
            height=720,
            file_size=os.path.getsize(self.sample_video_path),
            rights_confirmed=True,
            status=VideoSource.STATUS_READY
        )
        with open(self.sample_video_path, 'rb') as f:
            self.video.original_file.save("test_input.mp4", File(f), save=True)

        self.client1 = Client()
        self.client1.force_login(self.user1)

        self.api_client1 = APIClient()
        self.api_client1.force_authenticate(user=self.user1)

    def test_ffmpeg_probe(self):
        meta = FFmpegService.probe_video(self.video.original_file.path)
        self.assertEqual(meta['width'], 1280)
        self.assertEqual(meta['height'], 720)
        self.assertGreater(meta['duration'], 1.5)
        self.assertEqual(meta['video_codec'], 'h264')
        self.assertTrue(meta['has_audio'])

    def test_ffmpeg_probe_invalid_file(self):
        invalid_path = os.path.join(self.test_dir, "corrupt.mp4")
        with open(invalid_path, 'w') as f:
            f.write("not a valid video content")

        with self.assertRaises(VideoProcessingError):
            FFmpegService.probe_video(invalid_path)

    def test_video_filter_construction(self):
        # Center crop filter
        f_center = FFmpegService.build_video_filter(crop_mode='center')
        self.assertIn("crop=1080:1920", f_center)

        # Blur background filter
        f_blur = FFmpegService.build_video_filter(crop_mode='blur')
        self.assertIn("boxblur", f_blur)
        self.assertIn("overlay", f_blur)

        # Fit background filter
        f_fit = FFmpegService.build_video_filter(crop_mode='fit')
        self.assertIn("pad=1080:1920", f_fit)

        # Watermark inclusion
        f_watermark = FFmpegService.build_video_filter(crop_mode='center', watermark_text='@Brand')
        self.assertIn("drawtext", f_watermark)
        self.assertIn("@Brand", f_watermark)

    def test_render_vertical_clip_center_crop(self):
        out_clip_path = os.path.join(self.test_dir, "out_vertical.mp4")
        meta = FFmpegService.render_clip(
            input_path=self.video.original_file.path,
            output_path=out_clip_path,
            start_time=0.0,
            duration=1.0,
            crop_mode='center'
        )
        self.assertEqual(meta['width'], 1080)
        self.assertEqual(meta['height'], 1920)
        self.assertTrue(os.path.exists(out_clip_path))

    def test_render_vertical_clip_blurred_background(self):
        out_blur_path = os.path.join(self.test_dir, "out_blur.mp4")
        meta = FFmpegService.render_clip(
            input_path=self.video.original_file.path,
            output_path=out_blur_path,
            start_time=0.0,
            duration=1.0,
            crop_mode='blur'
        )
        self.assertEqual(meta['width'], 1080)
        self.assertEqual(meta['height'], 1920)
        self.assertTrue(os.path.exists(out_blur_path))

    def test_thumbnail_generation(self):
        thumb_path = os.path.join(self.test_dir, "test_thumb.jpg")
        FFmpegService.generate_thumbnail(self.video.original_file.path, thumb_path, timestamp=0.5)
        self.assertTrue(os.path.exists(thumb_path))
        self.assertGreater(os.path.getsize(thumb_path), 0)

    def test_end_to_end_job_processing_task(self):
        job = ProcessingJob.objects.create(
            user=self.user1,
            video_source=self.video,
            clip_duration=15,
            start_time=0.0,
            end_time=1.0,
            crop_mode=ProcessingJob.CROP_CENTER,
            caption_enabled=False,
            watermark_enabled=True,
            watermark_text="@ShortsTest",
            status=ProcessingJob.STATUS_PENDING
        )

        # Run task directly
        process_video_job_task(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, ProcessingJob.STATUS_COMPLETED)
        self.assertEqual(job.progress, 100)

        # Check GeneratedClip
        clip = job.clips.first()
        self.assertIsNotNone(clip)
        self.assertEqual(clip.width, 1080)
        self.assertEqual(clip.height, 1920)
        self.assertTrue(os.path.exists(clip.output_file.path))
        self.assertTrue(os.path.exists(clip.thumbnail.path))

    def test_api_jobs_endpoints_and_isolation(self):
        from unittest.mock import patch

        # Create job via API with delay mocked so job stays pending
        with patch('apps.processing.tasks.process_video_job_task.delay') as mock_delay:
            res = self.api_client1.post('/api/jobs/', {
                'video_source': self.video.id,
                'clip_duration': 30,
                'start_time': 0.0,
                'crop_mode': 'center'
            })
            self.assertEqual(res.status_code, 201)
            job_id = res.data['id']
            mock_delay.assert_called_once_with(job_id)

            # Cancel job via API while pending
            cancel_res = self.api_client1.post(f'/api/jobs/{job_id}/cancel/')
            self.assertEqual(cancel_res.status_code, 200)

            # Retry job via API
            retry_res = self.api_client1.post(f'/api/jobs/{job_id}/retry/')
            self.assertEqual(retry_res.status_code, 200)

    def test_job_status_api_includes_status_message(self):
        job = ProcessingJob.objects.create(
            user=self.user1,
            video_source=self.video,
            clip_duration=15,
            progress=45,
            status_message="Rendering Short #1 of 3...",
            status=ProcessingJob.STATUS_PROCESSING
        )
        res = self.client1.get(f'/processing/jobs/{job.id}/status/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status_message'], "Rendering Short #1 of 3...")
        self.assertEqual(data['progress'], 45)

    def test_multi_clip_processing_with_status_updates(self):
        job = ProcessingJob.objects.create(
            user=self.user1,
            video_source=self.video,
            clip_count=2,
            clip_duration=1,
            start_time=0.0,
            end_time=2.0,
            crop_mode=ProcessingJob.CROP_CENTER,
            caption_enabled=False,
            anti_copyright_enabled=True,
            status=ProcessingJob.STATUS_PENDING
        )
        process_video_job_task(job.id)
        job.refresh_from_db()
        self.assertEqual(job.status, ProcessingJob.STATUS_COMPLETED)
        self.assertEqual(job.progress, 100)
        self.assertIn("Shorts generated successfully", job.status_message)
        self.assertEqual(job.clips.count(), 2)


