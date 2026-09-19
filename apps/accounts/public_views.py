from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from apps.videos.models import VideoSource
from apps.processing.models import ProcessingJob
from apps.exports.models import GeneratedClip


from django.contrib import messages
from apps.videos.services.youtube import YouTubeDownloaderService
from apps.processing.tasks import process_video_job_task
from apps.audit.utils import record_audit_event


from apps.videos.validators import is_safe_url


def home_view(request):
    if request.method == 'POST':
        video_file = request.FILES.get('video_file')
        raw_url = (request.POST.get('video_url') or request.POST.get('youtube_url') or '').strip()

        if not video_file and not raw_url:
            messages.error(request, "Please enter a video link or upload a video file.")
            return redirect('home')

        source = None

        if video_file:
            from apps.videos.validators import validate_video_file_extension, validate_video_file_size
            from django.core.exceptions import ValidationError
            try:
                validate_video_file_extension(video_file)
                validate_video_file_size(video_file)
            except ValidationError as ve:
                messages.error(request, str(ve.message if hasattr(ve, 'message') else ve))
                return redirect('home')

            source = VideoSource.objects.create(
                user=request.user if request.user.is_authenticated else None,
                source_type=VideoSource.SOURCE_UPLOAD,
                original_file=video_file,
                title=video_file.name,
                file_size=video_file.size,
                rights_confirmed=True,
                status=VideoSource.STATUS_PENDING
            )
        else:
            # Clean and normalize YouTube URL to remove playlist/mix contamination
            clean_url = YouTubeDownloaderService.clean_youtube_url(raw_url)
            if not is_safe_url(clean_url):
                messages.error(request, "Please provide a valid public video link (YouTube, TikTok, Instagram, Facebook, or direct video URL).")
                return redirect('home')

            source = VideoSource.objects.create(
                user=request.user if request.user.is_authenticated else None,
                source_type=VideoSource.SOURCE_URL,
                source_url=clean_url,
                title="Imported Video",
                rights_confirmed=True,
                status=VideoSource.STATUS_PENDING
            )

        try:
            clip_duration = int(request.POST.get('clip_duration', 30))
            if clip_duration not in (15, 30, 45, 60, 90):
                clip_duration = 30
        except (ValueError, TypeError):
            clip_duration = 30

        try:
            start_time = float(request.POST.get('start_time', 0.0) or 0.0)
            if start_time < 0:
                start_time = 0.0
        except (ValueError, TypeError):
            start_time = 0.0

        try:
            clip_count = int(request.POST.get('clip_count', 5))
            clip_count = max(1, min(15, clip_count))
        except (ValueError, TypeError):
            clip_count = 5

        crop_mode = request.POST.get('crop_mode', ProcessingJob.CROP_BLUR)
        if crop_mode not in [ProcessingJob.CROP_CENTER, ProcessingJob.CROP_BLUR, ProcessingJob.CROP_FIT]:
            crop_mode = ProcessingJob.CROP_BLUR

        caption_enabled = request.POST.get('caption_enabled') in ('on', 'true', '1', True)
        caption_style = request.POST.get('caption_style', 'bold_yellow')
        watermark_text = request.POST.get('watermark_text', '').strip()
        anti_copyright_enabled = request.POST.get('anti_copyright_enabled', 'on') in ('on', 'true', '1', True)

        job = ProcessingJob.objects.create(
            user=request.user if request.user.is_authenticated else None,
            video_source=source,
            clip_count=clip_count,
            start_time=start_time,
            clip_duration=clip_duration,
            crop_mode=crop_mode,
            caption_enabled=caption_enabled,
            caption_style=caption_style,
            watermark_enabled=bool(watermark_text),
            watermark_text=watermark_text,
            anti_copyright_enabled=anti_copyright_enabled,
            status=ProcessingJob.STATUS_PENDING,
            progress=0
        )

        record_audit_event(
            user=request.user if request.user.is_authenticated else None,
            event_type='video.convert_requested',
            request=request,
            metadata={
                'job_id': job.id,
                'source_type': source.source_type,
                'video_url': source.source_url or '',
                'start_time': start_time
            }
        )

        # Trigger conversion task in background thread so the HTTP view redirects immediately
        import threading
        task_thread = threading.Thread(target=process_video_job_task.delay, args=(job.id,), daemon=True)
        task_thread.start()
        task_thread.join(timeout=0.05)

        messages.success(request, "Conversion started! Converting your video to 9:16 Shorts...")
        return redirect('processing:job_detail', job_id=job.id)

    # GET request
    recent_shorts = GeneratedClip.objects.filter(
        status=GeneratedClip.STATUS_READY
    ).select_related('job', 'job__video_source').order_by('-created_at')[:8]

    return render(request, 'public/home.html', {
        'recent_shorts': recent_shorts
    })


def features_view(request):
    return render(request, 'public/features.html')


def terms_view(request):
    return render(request, 'public/terms.html')


def privacy_view(request):
    return render(request, 'public/privacy.html')


def copyright_policy_view(request):
    return render(request, 'public/copyright.html')


@login_required
def dashboard_view(request):
    user = request.user
    profile = user.profile

    recent_videos = VideoSource.objects.filter(
        user=user
    ).exclude(status=VideoSource.STATUS_DELETED).order_by('-created_at')[:5]

    recent_jobs = ProcessingJob.objects.filter(
        user=user
    ).select_related('video_source').order_by('-created_at')[:5]

    recent_clips = GeneratedClip.objects.filter(
        job__user=user,
        status=GeneratedClip.STATUS_READY
    ).select_related('job', 'job__video_source').order_by('-created_at')[:6]

    context = {
        'profile': profile,
        'used_storage_mb': profile.get_used_storage_mb(),
        'quota_mb': profile.get_quota_mb(),
        'usage_pct': profile.get_usage_percentage(),
        'recent_videos': recent_videos,
        'recent_jobs': recent_jobs,
        'recent_clips': recent_clips,
        'total_videos': VideoSource.objects.filter(user=user).exclude(status='deleted').count(),
        'total_clips': GeneratedClip.objects.filter(job__user=user, status='ready').count(),
        'active_jobs': ProcessingJob.objects.filter(user=user, status__in=['pending', 'processing']).count(),
    }
    return render(request, 'dashboard.html', context)


def robots_txt_view(request):
    """Serve robots.txt dynamically with proper content type."""
    ctx = {
        'scheme': request.scheme,
        'host': request.get_host(),
    }
    content = render_to_string('robots.txt', ctx, request=request)
    return HttpResponse(content, content_type='text/plain')


def sitemap_xml_view(request):
    """Serve sitemap.xml dynamically with proper content type."""
    ctx = {
        'scheme': request.scheme,
        'host': request.get_host(),
    }
    content = render_to_string('sitemap.xml', ctx, request=request)
    return HttpResponse(content, content_type='application/xml')
