import os
from django.db import models
from django.contrib.auth.models import User
from .validators import validate_video_file_extension, validate_video_file_size


def video_upload_path(instance, filename):
    from .validators import sanitize_filename
    clean = sanitize_filename(filename)
    user_id = instance.user_id or 'public'
    return f"videos/{user_id}/{clean}"


class VideoSource(models.Model):
    SOURCE_UPLOAD = 'upload'
    SOURCE_URL = 'authorized_url'
    SOURCE_TYPES = (
        (SOURCE_UPLOAD, 'Direct Upload'),
        (SOURCE_URL, 'Authorized URL'),
    )

    STATUS_PENDING = 'pending'
    STATUS_VALIDATING = 'validating'
    STATUS_READY = 'ready'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_DELETED = 'deleted'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_VALIDATING, 'Validating'),
        (STATUS_READY, 'Ready'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DELETED, 'Deleted'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='video_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default=SOURCE_UPLOAD)
    original_file = models.FileField(
        upload_to=video_upload_path,
        validators=[validate_video_file_extension, validate_video_file_size],
        blank=True,
        null=True
    )
    source_url = models.URLField(blank=True, null=True)
    title = models.CharField(max_length=255, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text="Duration in seconds")
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True, help_text="Size in bytes")
    rights_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Video {self.id} ({self.get_source_type_display()})"

    @property
    def file_path(self):
        if self.original_file and os.path.exists(self.original_file.path):
            return self.original_file.path
        return None

    @property
    def file_size_mb(self) -> float:
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0.0

    @property
    def formatted_duration(self) -> str:
        if self.duration is None:
            return "00:00"
        mins = int(self.duration // 60)
        secs = int(self.duration % 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def formatted_resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "Unknown"

    def delete_file(self):
        if self.original_file and os.path.exists(self.original_file.path):
            try:
                os.remove(self.original_file.path)
            except OSError:
                pass
        self.status = self.STATUS_DELETED
        self.save(update_fields=['status'])
