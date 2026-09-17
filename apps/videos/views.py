from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import VideoSource
from .forms import VideoUploadForm, VideoUrlImportForm
from .tasks import validate_source_task
from apps.audit.utils import record_audit_event


@login_required
def video_list_view(request):
    videos = VideoSource.objects.filter(
        user=request.user
    ).exclude(status=VideoSource.STATUS_DELETED).order_by('-created_at')

    return render(request, 'videos/video_list.html', {'videos': videos})


@login_required
def upload_view(request):
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['original_file']

            # Check user storage quota
            profile = request.user.profile
            if not profile.can_upload(uploaded_file.size):
                messages.error(request, f"Upload rejected: you have exceeded your storage quota of {profile.get_quota_mb()} MB.")
                return render(request, 'videos/upload.html', {'form': form})

            source = form.save(commit=False)
            source.user = request.user
            source.source_type = VideoSource.SOURCE_UPLOAD
            source.status = VideoSource.STATUS_PENDING
            source.file_size = uploaded_file.size
            if not source.title:
                source.title = uploaded_file.name
            source.save()

            record_audit_event(
                user=request.user,
                event_type='video.upload',
                request=request,
                metadata={
                    'video_id': source.id,
                    'filename': uploaded_file.name,
                    'size': uploaded_file.size,
                    'rights_confirmed': source.rights_confirmed
                }
            )

            # Trigger background validation
            validate_source_task.delay(source.id)
            messages.success(request, "Video uploaded successfully! Validation and metadata extraction in progress.")
            return redirect('videos:detail', video_id=source.id)
    else:
        form = VideoUploadForm()

    return render(request, 'videos/upload.html', {'form': form})


@login_required
def import_url_view(request):
    if request.method == 'POST':
        form = VideoUrlImportForm(request.POST)
        if form.is_valid():
            source = form.save(commit=False)
            source.user = request.user
            source.source_type = VideoSource.SOURCE_URL
            source.status = VideoSource.STATUS_PENDING
            if not source.title:
                source.title = source.source_url.split('/')[-1].split('?')[0] or "Imported Video"
            source.save()

            record_audit_event(
                user=request.user,
                event_type='video.import_url',
                request=request,
                metadata={
                    'video_id': source.id,
                    'source_url': source.source_url,
                    'rights_confirmed': source.rights_confirmed
                }
            )

            validate_source_task.delay(source.id)
            messages.success(request, "Video import initiated! Downloading and extracting metadata.")
            return redirect('videos:detail', video_id=source.id)
    else:
        form = VideoUrlImportForm()

    return render(request, 'videos/import_url.html', {'form': form})


@login_required
def video_detail_view(request, video_id: int):
    video = get_object_or_404(VideoSource, id=video_id)
    if video.user != request.user:
        return HttpResponseForbidden("Access denied.")

    return render(request, 'videos/video_detail.html', {'video': video})


@login_required
def video_delete_view(request, video_id: int):
    video = get_object_or_404(VideoSource, id=video_id)
    if video.user != request.user:
        return HttpResponseForbidden("Access denied.")

    if request.method == 'POST':
        record_audit_event(
            user=request.user,
            event_type='video.deleted',
            request=request,
            metadata={'video_id': video.id, 'title': video.title}
        )
        video.delete_file()
        messages.success(request, f"Video '{video.title}' was successfully deleted.")
        return redirect('videos:list')

    return render(request, 'videos/video_confirm_delete.html', {'video': video})
