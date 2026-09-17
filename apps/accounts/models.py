from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    storage_quota = models.BigIntegerField(default=2 * 1024 * 1024 * 1024, help_text="Quota in bytes (default 2GB)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} Profile"

    def get_used_storage(self) -> int:
        """Calculate total storage currently used by user's videos and generated clips."""
        from apps.videos.models import VideoSource
        from apps.exports.models import GeneratedClip

        video_storage = VideoSource.objects.filter(
            user=self.user,
            status__in=['ready', 'processing', 'completed']
        ).aggregate(total=Sum('file_size'))['total'] or 0

        clip_storage = GeneratedClip.objects.filter(
            job__user=self.user,
            status='ready'
        ).aggregate(total=Sum('file_size'))['total'] or 0

        return video_storage + clip_storage

    def get_used_storage_mb(self) -> float:
        return round(self.get_used_storage() / (1024 * 1024), 2)

    def get_quota_mb(self) -> float:
        return round(self.storage_quota / (1024 * 1024), 2)

    def get_usage_percentage(self) -> float:
        if not self.storage_quota:
            return 0.0
        pct = (self.get_used_storage() / self.storage_quota) * 100
        return min(round(pct, 1), 100.0)

    def can_upload(self, additional_bytes: int) -> bool:
        return (self.get_used_storage() + additional_bytes) <= self.storage_quota
