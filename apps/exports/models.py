import os
from django.db import models
from apps.processing.models import ProcessingJob


def clip_upload_path(instance, filename):
    user_id = instance.job.user_id if instance.job and instance.job.user_id else 'public'
    return f"clips/{user_id}/{filename}"


def thumb_upload_path(instance, filename):
    user_id = instance.job.user_id if instance.job and instance.job.user_id else 'public'
    return f"thumbnails/{user_id}/{filename}"


class GeneratedClip(models.Model):
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_DELETED = 'deleted'
    STATUS_CHOICES = (
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DELETED, 'Deleted'),
    )

    job = models.ForeignKey(ProcessingJob, on_delete=models.CASCADE, related_name='clips')
    start_time = models.FloatField(default=0.0)
    end_time = models.FloatField(default=0.0)
    output_file = models.FileField(upload_to=clip_upload_path)
    thumbnail = models.ImageField(upload_to=thumb_upload_path, blank=True, null=True)
    duration = models.FloatField(null=True, blank=True)
    width = models.IntegerField(default=1080)
    height = models.IntegerField(default=1920)
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_READY)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Clip #{self.id} for Job #{self.job_id} ({self.get_status_display()})"

    @property
    def file_size_mb(self) -> float:
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0.0

    @property
    def formatted_duration(self) -> str:
        if self.duration:
            secs = int(self.duration)
            return f"{secs}s"
        return "0s"

    def delete_files(self):
        """Remove video and thumbnail from disk safely."""
        if self.output_file and os.path.exists(self.output_file.path):
            try:
                os.remove(self.output_file.path)
            except OSError:
                pass
        if self.thumbnail and os.path.exists(self.thumbnail.path):
            try:
                os.remove(self.thumbnail.path)
            except OSError:
                pass
        self.status = self.STATUS_DELETED
        self.save(update_fields=['status'])
