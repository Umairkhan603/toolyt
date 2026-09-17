from rest_framework import serializers
from apps.videos.models import VideoSource


class VideoSourceSerializer(serializers.ModelSerializer):
    duration_formatted = serializers.ReadOnlyField(source='formatted_duration')
    resolution_formatted = serializers.ReadOnlyField(source='formatted_resolution')
    file_size_mb = serializers.ReadOnlyField()

    class Meta:
        model = VideoSource
        fields = (
            'id',
            'title',
            'source_type',
            'original_file',
            'source_url',
            'duration',
            'duration_formatted',
            'width',
            'height',
            'resolution_formatted',
            'file_size',
            'file_size_mb',
            'rights_confirmed',
            'status',
            'error_message',
            'created_at'
        )
        read_only_fields = ('id', 'duration', 'width', 'height', 'file_size', 'status', 'error_message', 'created_at')


class VideoUploadSerializer(serializers.ModelSerializer):
    rights_confirmed = serializers.BooleanField(required=True)

    class Meta:
        model = VideoSource
        fields = ('original_file', 'title', 'rights_confirmed')

    def validate_rights_confirmed(self, value):
        if not value:
            raise serializers.ValidationError("You must confirm rights and ownership before uploading.")
        return value


class VideoUrlImportSerializer(serializers.ModelSerializer):
    rights_confirmed = serializers.BooleanField(required=True)
    source_url = serializers.URLField(required=True)

    class Meta:
        model = VideoSource
        fields = ('source_url', 'title', 'rights_confirmed')

    def validate_rights_confirmed(self, value):
        if not value:
            raise serializers.ValidationError("You must confirm rights before importing URL.")
        return value
