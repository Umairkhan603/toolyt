from django.contrib import admin
from .models import ProcessingJob


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'video_source', 'clip_duration', 'crop_mode', 'caption_enabled', 'status', 'progress', 'created_at')
    list_filter = ('status', 'crop_mode', 'caption_enabled', 'created_at')
    search_fields = ('user__username', 'video_source__title')
    readonly_fields = ('created_at', 'started_at', 'completed_at')
