from django.contrib import admin
from .models import VideoSource


@admin.register(VideoSource)
class VideoSourceAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'source_type', 'status', 'duration', 'width', 'height', 'created_at')
    list_filter = ('source_type', 'status', 'rights_confirmed', 'created_at')
    search_fields = ('title', 'user__username', 'source_url')
    readonly_fields = ('created_at', 'updated_at', 'duration', 'width', 'height', 'file_size')
