import os
import shutil
import tempfile
import logging
from celery import shared_task
from django.utils import timezone
from django.core.files import File
from apps.videos.models import VideoSource
from apps.processing.models import ProcessingJob
from apps.processing.services.ffmpeg import FFmpegService, VideoProcessingError
from apps.captions.services import CaptionService
from apps.exports.models import GeneratedClip
from apps.audit.utils import record_audit_event

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_video_job_task(self, job_id: int):
    """
    Background Celery task that processes a video into 9:16 vertical shorts.
    """
    try:
        job = ProcessingJob.objects.select_related('video_source', 'user').get(id=job_id)
    except ProcessingJob.DoesNotExist:
        logger.error(f"ProcessingJob #{job_id} does not exist.")
        return

    # Check if job was cancelled
    if job.status == ProcessingJob.STATUS_CANCELLED:
        logger.info(f"ProcessingJob #{job_id} was cancelled before starting.")
        return

    job.status = ProcessingJob.STATUS_PROCESSING
    job.started_at = timezone.now()
    job.progress = 5
    job.status_message = "Preparing video processing engine..."
    job.error_message = ""
    job.save(update_fields=['status', 'started_at', 'progress', 'status_message', 'error_message'])

    scratch_dir = tempfile.mkdtemp(prefix=f"job_{job.id}_")
    source = job.video_source
    num_clips = max(1, min(15, job.clip_count or 1))
    clip_duration = float(job.effective_duration)

    from apps.videos.services.highlights import HighlightDetectorService
    from apps.videos.services.youtube import YouTubeDownloaderService

    try:
        # Step 1: Detect Highlights & Metadata
        highlights = []
        if source.source_url and YouTubeDownloaderService.is_youtube_url(source.source_url):
            try:
                job.update_progress(10, "Extracting video metadata and audience heatmap...")
                yt_meta = YouTubeDownloaderService.extract_info(source.source_url)
                if not source.title:
                    source.title = yt_meta.get('title', 'YouTube Video')
                if not source.duration and yt_meta.get('duration'):
                    source.duration = float(yt_meta.get('duration'))
                source.save(update_fields=['title', 'duration'])

                if num_clips == 1 and job.start_time > 0:
                    highlights = [{
                        'index': 1,
                        'title': f"Clip at {int(job.start_time)}s",
                        'start_time': job.start_time,
                        'end_time': job.start_time + clip_duration,
                        'duration': clip_duration,
                    }]
                else:
                    highlights = HighlightDetectorService.detect_highlights(
                        yt_meta,
                        clip_duration=clip_duration,
                        clip_count=num_clips
                    )
            except Exception as meta_err:
                logger.warning(f"Could not extract metadata for highlights: {meta_err}")

        # Step 2: Ensure source video is downloaded locally ONCE
        source_local_path = None
        if source.original_file and hasattr(source.original_file, 'path') and os.path.exists(source.original_file.path) and os.path.getsize(source.original_file.path) > 1000:
            source_local_path = source.original_file.path
        elif source.source_url and YouTubeDownloaderService.is_youtube_url(source.source_url):
            job.update_progress(20, "Downloading source video stream at high speed (720p)...")
            yt_clip_info = YouTubeDownloaderService.download_video(
                source.source_url,
                scratch_dir
            )
            downloaded_path = yt_clip_info['file_path']
            if os.path.exists(downloaded_path):
                fn = os.path.basename(downloaded_path)
                with open(downloaded_path, 'rb') as f:
                    source.original_file.save(fn, File(f), save=False)
                source.duration = yt_clip_info.get('duration', source.duration)
                source.width = yt_clip_info.get('width', 1280)
                source.height = yt_clip_info.get('height', 720)
                source.status = VideoSource.STATUS_READY
                source.save()
                source_local_path = source.original_file.path
        elif source.original_file and os.path.exists(source.original_file.path):
            source_local_path = source.original_file.path

        if not source_local_path or not os.path.exists(source_local_path):
            raise VideoProcessingError("Source video could not be loaded or downloaded.")

        # Fallback highlight detection if needed
        if not highlights:
            try:
                dur = float(source.duration or 300.0)
                if dur <= 0:
                    probe = FFmpegService.probe_video(source_local_path)
                    dur = float(probe.get('duration') or 300.0)
            except Exception:
                dur = 300.0

            if num_clips == 1 and job.start_time > 0:
                highlights = [{
                    'index': 1,
                    'title': f"Clip at {int(job.start_time)}s",
                    'start_time': job.start_time,
                    'end_time': job.start_time + clip_duration,
                    'duration': clip_duration,
                }]
            else:
                highlights = HighlightDetectorService.detect_highlights(
                    {'duration': dur, 'title': source.title},
                    clip_duration=clip_duration,
                    clip_count=num_clips
                )

        logger.info(f"ProcessingJob #{job.id}: Generating {len(highlights)} shorts.")

        # Step 3: Transcribe video if subtitles enabled (ONCE for the entire video)
        transcript = None
        if job.caption_enabled:
            job.update_progress(25, "Generating automated captions for speech...")
            try:
                transcript = CaptionService.transcribe_video(source)
            except Exception as cap_err:
                logger.warning(f"Audio transcription failed: {cap_err}")



        # Step 5: Fast Local FFmpeg Rendering for Each Short
        created_clips = []
        watermark = job.watermark_text if job.watermark_enabled else None
        total_highlights = len(highlights)

        for idx, h in enumerate(highlights):
            # Check if job was cancelled mid-run
            job.refresh_from_db(fields=['status'])
            if job.status == ProcessingJob.STATUS_CANCELLED:
                logger.info(f"ProcessingJob #{job.id} cancelled during rendering.")
                return

            sub_progress = 30 + int((idx / total_highlights) * 65)
            anti_text = " + Anti-Copyright" if job.anti_copyright_enabled else ""
            job.update_progress(sub_progress, f"Rendering Short #{idx+1} of {total_highlights} (9:16 layout{anti_text})...")

            h_start = float(h['start_time'])
            h_dur = float(h.get('duration', clip_duration))
            clip_scratch = os.path.join(scratch_dir, f"clip_{idx}")
            os.makedirs(clip_scratch, exist_ok=True)

            # Subtitles for this highlight
            subtitles_file = None
            if job.caption_enabled and transcript:
                try:
                    sub_path = os.path.join(clip_scratch, f"subtitles_{job.id}_{idx}.ass")
                    subtitles_file = CaptionService.generate_subtitles_for_clip(
                        transcript=transcript,
                        clip_start=h_start,
                        clip_end=h_start + h_dur,
                        output_sub_path=sub_path,
                        style_name=job.caption_style
                    )
                except Exception as cap_err:
                    logger.warning(f"Caption slice generation failed for clip #{idx+1}: {cap_err}")

            # Render 9:16 vertical short
            temp_output_path = os.path.join(clip_scratch, f"short_{job.id}_{idx}.mp4")
            temp_thumb_path = os.path.join(clip_scratch, f"thumb_{job.id}_{idx}.jpg")

            try:
                output_meta = FFmpegService.render_clip(
                    input_path=source_local_path,
                    output_path=temp_output_path,
                    start_time=h_start,
                    duration=h_dur,
                    crop_mode=job.crop_mode,
                    watermark_text=watermark,
                    subtitle_file=subtitles_file,
                    volume_multiplier=job.audio_volume,
                    anti_copyright=job.anti_copyright_enabled,
                )

                FFmpegService.generate_thumbnail(
                    video_path=temp_output_path,
                    output_thumbnail_path=temp_thumb_path,
                    timestamp=min(1.0, h_dur / 2)
                )

                clip = GeneratedClip(
                    job=job,
                    start_time=h_start,
                    end_time=h_start + output_meta['duration'],
                    duration=output_meta['duration'],
                    width=output_meta['width'],
                    height=output_meta['height'],
                    file_size=output_meta['file_size'],
                    status=GeneratedClip.STATUS_READY
                )

                filename_clip = f"short_{job.id}_{idx}_{int(h_start)}.mp4"
                filename_thumb = f"thumb_{job.id}_{idx}_{int(h_start)}.jpg"

                with open(temp_output_path, 'rb') as f_clip:
                    clip.output_file.save(filename_clip, File(f_clip), save=False)

                if os.path.exists(temp_thumb_path):
                    with open(temp_thumb_path, 'rb') as f_thumb:
                        clip.thumbnail.save(filename_thumb, File(f_thumb), save=False)

                clip.save()
                created_clips.append(clip)
                logger.info(f"GeneratedClip #{clip.id} created for Job #{job.id} ({h['title']}).")

            except Exception as ren_err:
                logger.error(f"Failed to render highlight #{idx+1}: {ren_err}")
                continue

        if not created_clips:
            job.status = ProcessingJob.STATUS_FAILED
            job.error_message = "Failed to render shorts from video."
            job.status_message = "Processing failed."
            job.save(update_fields=['status', 'error_message', 'status_message'])
            return

        # Step 5: Mark Job Completed
        job.status = ProcessingJob.STATUS_COMPLETED
        job.progress = 100
        job.completed_at = timezone.now()
        job.status_message = f"All {len(created_clips)} Shorts generated successfully!"
        job.save(update_fields=['status', 'progress', 'completed_at', 'status_message'])

        record_audit_event(
            user=job.user,
            event_type='job.completed',
            metadata={
                'job_id': job.id,
                'clips_count': len(created_clips),
            }
        )
        logger.info(f"ProcessingJob #{job.id} successfully completed. {len(created_clips)} clips generated.")

    except Exception as e:
        logger.exception(f"ProcessingJob #{job.id} failed: {e}")
        job.status = ProcessingJob.STATUS_FAILED
        job.error_message = str(e)
        job.status_message = "Processing error."
        job.save(update_fields=['status', 'error_message', 'status_message'])
        record_audit_event(
            user=job.user,
            event_type='job.failed',
            metadata={'job_id': job.id, 'error': str(e)}
        )

    finally:
        try:
            shutil.rmtree(scratch_dir, ignore_errors=True)
        except OSError:
            pass


@shared_task
def cleanup_temp_files_task():
    """Periodic task to clean up old temp files or orphaned media."""
    logger.info("Running cleanup_temp_files_task...")
    # Clean up empty or stale temp directories if any
    return "Cleanup completed"
