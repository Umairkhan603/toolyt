import logging
import os
import requests
from celery import shared_task
from django.utils import timezone
from apps.videos.models import VideoSource
from apps.processing.services.ffmpeg import FFmpegService, VideoProcessingError
from apps.audit.utils import record_audit_event

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def validate_source_task(self, video_source_id: int):
    """
    Background task to validate video source via FFprobe.
    Handles both direct uploads and authorized URL downloads.
    """
    try:
        source = VideoSource.objects.get(id=video_source_id)
    except VideoSource.DoesNotExist:
        logger.error(f"VideoSource #{video_source_id} does not exist.")
        return

    source.status = VideoSource.STATUS_VALIDATING
    source.save(update_fields=['status', 'updated_at'])

    try:
        # Handle authorized URL download if needed
        if source.source_type == VideoSource.SOURCE_URL and not source.original_file:
            if not source.source_url:
                raise VideoProcessingError("No source URL provided.")

            # Download video stream safely
            import tempfile
            from apps.videos.validators import sanitize_filename
            from apps.videos.services.youtube import YouTubeDownloaderService
            from django.core.files import File

            temp_dir = tempfile.mkdtemp()

            if YouTubeDownloaderService.is_youtube_url(source.source_url):
                yt_info = YouTubeDownloaderService.download_video(source.source_url, temp_dir)
                local_path = yt_info['file_path']
                target_filename = os.path.basename(local_path)
                if not source.title or source.title == "Imported Video":
                    source.title = yt_info.get('title', '')
                with open(local_path, 'rb') as f:
                    source.original_file.save(target_filename, File(f), save=False)
            else:
                target_filename = sanitize_filename(os.path.basename(source.source_url.split('?')[0]) or "imported_video.mp4")
                if not any(target_filename.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']):
                    target_filename += ".mp4"
                local_path = os.path.join(temp_dir, target_filename)

                # Stream download with size limit enforcement
                max_size = 500 * 1024 * 1024
                downloaded = 0
                with requests.get(source.source_url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(local_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            downloaded += len(chunk)
                            if downloaded > max_size:
                                raise VideoProcessingError("Imported video exceeds maximum file size limit (500MB).")
                            f.write(chunk)

                with open(local_path, 'rb') as f:
                    source.original_file.save(target_filename, File(f), save=False)

            # Cleanup temp file
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
                os.rmdir(temp_dir)
            except OSError:
                pass
            try:
                os.remove(local_path)
                os.rmdir(temp_dir)
            except OSError:
                pass

        if not source.original_file or not os.path.exists(source.original_file.path):
            raise VideoProcessingError("Original video file is missing or unreadable.")

        # Probe video using FFprobe
        meta = FFmpegService.probe_video(source.original_file.path)
        source.width = meta['width']
        source.height = meta['height']
        source.duration = meta['duration']
        source.file_size = meta['file_size']
        source.status = VideoSource.STATUS_READY
        source.error_message = ""
        if not source.title:
            source.title = os.path.splitext(os.path.basename(source.original_file.name))[0]
        source.save()

        record_audit_event(
            user=source.user,
            event_type='video.validated',
            metadata={
                'video_id': source.id,
                'resolution': f"{source.width}x{source.height}",
                'duration': source.duration,
                'size': source.file_size
            }
        )
        logger.info(f"VideoSource #{source.id} successfully validated.")

    except Exception as e:
        logger.exception(f"Validation failed for VideoSource #{source.id}: {e}")
        source.status = VideoSource.STATUS_FAILED
        source.error_message = str(e)
        source.save(update_fields=['status', 'error_message', 'updated_at'])
        record_audit_event(
            user=source.user,
            event_type='video.validation_failed',
            metadata={'video_id': source.id, 'error': str(e)}
        )
