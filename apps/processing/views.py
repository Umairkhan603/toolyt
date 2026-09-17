from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.utils import timezone
from apps.videos.models import VideoSource
from .models import ProcessingJob
from .forms import ProcessingJobForm
from .tasks import process_video_job_task
from apps.audit.utils import record_audit_event


@login_required
def create_job_view(request, video_id: int):
    video = get_object_or_404(VideoSource, id=video_id)
    if video.user != request.user:
        return HttpResponseForbidden("You do not have permission to access this video.")

    if video.status != VideoSource.STATUS_READY:
        messages.warning(request, f"Video is currently in status '{video.get_status_display()}'. Please wait until it is ready.")
        return redirect('videos:detail', video_id=video.id)

    if request.method == 'POST':
        form = ProcessingJobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.user = request.user
            job.video_source = video
            job.status = ProcessingJob.STATUS_PENDING
            job.progress = 0
            job.save()

            record_audit_event(
                user=request.user,
                event_type='job.created',
                request=request,
                metadata={
                    'job_id': job.id,
                    'video_id': video.id,
                    'clip_duration': job.clip_duration,
                    'crop_mode': job.crop_mode,
                    'caption_enabled': job.caption_enabled
                }
            )

            # Trigger Celery background task
            process_video_job_task.delay(job.id)
            messages.success(request, f"Shorts generation job #{job.id} queued successfully!")
            return redirect('processing:job_detail', job_id=job.id)
    else:
        # Default start and end based on video duration
        initial_duration = 30
        initial_end = min(video.duration or 30.0, float(initial_duration))
        form = ProcessingJobForm(initial={
            'clip_duration': initial_duration,
            'start_time': 0.0,
            'end_time': initial_end,
            'crop_mode': ProcessingJob.CROP_CENTER
        })

    return render(request, 'processing/create_job.html', {
        'form': form,
        'video': video
    })


def job_detail_view(request, job_id: int):
    job = get_object_or_404(ProcessingJob.objects.select_related('video_source'), id=job_id)
    clips = job.clips.filter(status=job.clips.model.STATUS_READY)

    return render(request, 'processing/job_detail.html', {
        'job': job,
        'video': job.video_source,
        'clips': clips
    })


def job_status_api(request, job_id: int):
    job = get_object_or_404(ProcessingJob, id=job_id)
    clips_data = [
        {
            'id': c.id,
            'url': c.output_file.url if c.output_file else '',
            'thumb': c.thumbnail.url if c.thumbnail else '',
            'duration': c.formatted_duration,
            'size_mb': c.file_size_mb,
        }
        for c in job.clips.filter(status='ready')
    ]

    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'status_display': job.get_status_display(),
        'status_message': job.status_message or job.get_status_display(),
        'progress': job.progress,
        'error_message': job.error_message,
        'completed': job.status in [ProcessingJob.STATUS_COMPLETED, ProcessingJob.STATUS_FAILED, ProcessingJob.STATUS_CANCELLED],
        'clips': clips_data
    })


def cancel_job_view(request, job_id: int):
    job = get_object_or_404(ProcessingJob, id=job_id)
    if job.status in [ProcessingJob.STATUS_PENDING, ProcessingJob.STATUS_PROCESSING]:
        job.status = ProcessingJob.STATUS_CANCELLED
        job.save(update_fields=['status'])
        messages.info(request, f"Job #{job.id} cancelled.")
        record_audit_event(
            user=request.user if request.user.is_authenticated else None,
            event_type='job.cancelled',
            request=request,
            metadata={'job_id': job.id}
        )

    return redirect('processing:job_detail', job_id=job.id)


def retry_job_view(request, job_id: int):
    job = get_object_or_404(ProcessingJob, id=job_id)
    job.status = ProcessingJob.STATUS_PENDING
    job.progress = 0
    job.error_message = ""
    job.started_at = None
    job.completed_at = None
    job.save()

    process_video_job_task.delay(job.id)
    messages.success(request, f"Job #{job.id} re-queued for processing.")
    return redirect('processing:job_detail', job_id=job.id)
