from django.db import models
from django.contrib.auth.models import User
from apps.videos.models import VideoSource


class ProcessingJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    CROP_CENTER = 'center'
    CROP_BLUR = 'blur'
    CROP_FIT = 'fit'
    CROP_CHOICES = (
        (CROP_CENTER, 'Center Crop (Fill 9:16)'),
        (CROP_BLUR, 'Blurred Background'),
        (CROP_FIT, 'Fit with Letterbox/Pillarbox'),
    )

    DURATION_CHOICES = (
        (15, '15 Seconds'),
        (30, '30 Seconds ★ (Recommended)'),
        (45, '45 Seconds'),
        (60, '60 Seconds'),
        (90, '90 Seconds'),
    )

    CAPTION_STYLES = (
        ('classic', 'Classic White Subtitles'),
        ('bold_yellow', 'Bold Viral Yellow'),
        ('box', 'Subtitles with Box Background'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processing_jobs')
    video_source = models.ForeignKey(VideoSource, on_delete=models.CASCADE, related_name='processing_jobs')
    
    # Clip settings
    clip_duration = models.IntegerField(default=30, choices=DURATION_CHOICES)
    clip_count = models.IntegerField(default=1)
    start_time = models.FloatField(default=0.0)
    end_time = models.FloatField(null=True, blank=True)
    aspect_ratio = models.CharField(max_length=10, default='9:16')
    crop_mode = models.CharField(max_length=20, choices=CROP_CHOICES, default=CROP_CENTER)

    # Editing Features
    caption_enabled = models.BooleanField(default=False)
    caption_style = models.CharField(max_length=50, choices=CAPTION_STYLES, default='classic')
    watermark_enabled = models.BooleanField(default=False)
    watermark_text = models.CharField(max_length=100, blank=True)
    audio_volume = models.FloatField(default=1.0, help_text="Audio volume multiplier")
    anti_copyright_enabled = models.BooleanField(default=True, help_text="Transformative filters to prevent automated Content ID matches")


    # Status and progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    status_message = models.CharField(max_length=255, default='In queue...', blank=True)
    progress = models.IntegerField(default=0, help_text="Progress from 0 to 100")
    error_message = models.TextField(blank=True)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def update_progress(self, progress: int, message: str = ""):
        self.progress = progress
        if message:
            self.status_message = message
        self.save(update_fields=['progress', 'status_message'])

    def __str__(self):
        return f"Job #{self.id} for Video #{self.video_source_id} ({self.get_status_display()})"

    @property
    def effective_duration(self) -> float:
        if self.end_time and self.end_time > self.start_time:
            return min(float(self.clip_duration), self.end_time - self.start_time)
        return float(self.clip_duration)
