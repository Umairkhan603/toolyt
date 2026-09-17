from django.contrib import admin
from .models import GeneratedClip


@admin.register(GeneratedClip)
class GeneratedClipAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'duration', 'width', 'height', 'file_size', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__user__username', 'job__video_source__title')
    readonly_fields = ('created_at', 'duration', 'width', 'height', 'file_size')
