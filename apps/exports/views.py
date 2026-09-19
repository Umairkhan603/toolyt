import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, FileResponse, Http404
from django.contrib import messages
from .models import GeneratedClip
from apps.audit.utils import record_audit_event


def clip_list_view(request):
    if request.user.is_authenticated:
        clips = GeneratedClip.objects.filter(
            job__user=request.user,
            status=GeneratedClip.STATUS_READY
        ).select_related('job', 'job__video_source').order_by('-created_at')
    else:
        clips = GeneratedClip.objects.filter(
            status=GeneratedClip.STATUS_READY
        ).select_related('job', 'job__video_source').order_by('-created_at')[:20]

    return render(request, 'exports/clip_list.html', {'clips': clips})


def clip_detail_view(request, clip_id: int):
    clip = get_object_or_404(GeneratedClip.objects.select_related('job', 'job__video_source'), id=clip_id)
    return render(request, 'exports/clip_detail.html', {'clip': clip})


from django.conf import settings


def clip_download_view(request, clip_id: int):
    clip = get_object_or_404(GeneratedClip.objects.select_related('job'), id=clip_id)

    if not clip.output_file or not clip.output_file.name:
        raise Http404("Clip file does not exist on disk.")

    file_path = os.path.abspath(clip.output_file.path)
    media_root = os.path.abspath(settings.MEDIA_ROOT)

    if not file_path.startswith(media_root) or not os.path.exists(file_path):
        raise Http404("Clip file does not exist on disk.")

    record_audit_event(
        user=request.user if request.user.is_authenticated else None,
        event_type='clip.downloaded',
        request=request,
        metadata={
            'clip_id': clip.id,
            'job_id': clip.job_id,
            'file_name': os.path.basename(clip.output_file.name),
            'size': clip.file_size
        }
    )

    response = FileResponse(open(clip.output_file.path, 'rb'), content_type='video/mp4')
    filename = f"short_{clip.id}.mp4"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def clip_delete_view(request, clip_id: int):
    clip = get_object_or_404(GeneratedClip.objects.select_related('job'), id=clip_id)
    if clip.job.user and request.user.is_authenticated and clip.job.user != request.user:
        return HttpResponseForbidden("Access denied.")

    if request.method == 'POST':
        record_audit_event(
            user=request.user,
            event_type='clip.deleted',
            request=request,
            metadata={'clip_id': clip.id, 'job_id': clip.job_id}
        )
        clip.delete_files()
        messages.success(request, f"Shorts clip #{clip.id} was deleted.")
        return redirect('exports:list')

    return render(request, 'exports/clip_confirm_delete.html', {'clip': clip})
