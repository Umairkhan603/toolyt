from rest_framework import serializers
from apps.processing.models import ProcessingJob
from apps.videos.models import VideoSource


class ProcessingJobSerializer(serializers.ModelSerializer):
    video_title = serializers.ReadOnlyField(source='video_source.title')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    crop_mode_display = serializers.ReadOnlyField(source='get_crop_mode_display')
    clips_count = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingJob
        fields = (
            'id',
            'video_source',
            'video_title',
            'clip_duration',
            'clip_count',
            'start_time',
            'end_time',
            'aspect_ratio',
            'crop_mode',
            'crop_mode_display',
            'caption_enabled',
            'caption_style',
            'watermark_enabled',
            'watermark_text',
            'audio_volume',
            'status',
            'status_display',
            'progress',
            'error_message',
            'started_at',
            'completed_at',
            'created_at',
            'clips_count',
        )
        read_only_fields = ('id', 'status', 'progress', 'error_message', 'started_at', 'completed_at', 'created_at')

    def get_clips_count(self, obj):
        return obj.clips.filter(status='ready').count()


class ProcessingJobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingJob
        fields = (
            'id',
            'video_source',
            'clip_duration',
            'clip_count',
            'start_time',
            'end_time',
            'crop_mode',
            'caption_enabled',
            'caption_style',
            'watermark_enabled',
            'watermark_text',
            'audio_volume'
        )
        read_only_fields = ('id',)

    def validate_video_source(self, value):
        user = self.context['request'].user
        if value.user != user:
            raise serializers.ValidationError("You do not own this video source.")
        if value.status != VideoSource.STATUS_READY:
            raise serializers.ValidationError(f"Video is not ready yet (current status: {value.status}).")
        return value

    def validate(self, data):
        start = data.get('start_time', 0.0)
        end = data.get('end_time')
        if end is not None and end <= start:
            raise serializers.ValidationError({"end_time": "End time must be greater than start time."})
        return data
