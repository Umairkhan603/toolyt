from rest_framework import serializers
from apps.exports.models import GeneratedClip


class GeneratedClipSerializer(serializers.ModelSerializer):
    duration_formatted = serializers.ReadOnlyField(source='formatted_duration')
    file_size_mb = serializers.ReadOnlyField()
    job_id = serializers.ReadOnlyField(source='job.id')
    video_title = serializers.ReadOnlyField(source='job.video_source.title')

    class Meta:
        model = GeneratedClip
        fields = (
            'id',
            'job_id',
            'video_title',
            'start_time',
            'end_time',
            'output_file',
            'thumbnail',
            'duration',
            'duration_formatted',
            'width',
            'height',
            'file_size',
            'file_size_mb',
            'status',
            'created_at'
        )
