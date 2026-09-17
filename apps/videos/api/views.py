from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.videos.models import VideoSource
from .serializers import VideoSourceSerializer, VideoUploadSerializer, VideoUrlImportSerializer
from apps.videos.tasks import validate_source_task
from apps.audit.utils import record_audit_event


class VideoSourceListAPIView(generics.ListAPIView):
    serializer_class = VideoSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VideoSource.objects.filter(
            user=self.request.user
        ).exclude(status=VideoSource.STATUS_DELETED).order_by('-created_at')


class VideoUploadAPIView(generics.CreateAPIView):
    serializer_class = VideoUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = request.FILES.get('original_file')
        if not uploaded_file:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        # Quota check
        if not request.user.profile.can_upload(uploaded_file.size):
            return Response(
                {'error': f"Storage quota exceeded ({request.user.profile.get_quota_mb()} MB limit)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        video = serializer.save(
            user=request.user,
            source_type=VideoSource.SOURCE_UPLOAD,
            status=VideoSource.STATUS_PENDING,
            file_size=uploaded_file.size
        )
        if not video.title:
            video.title = uploaded_file.name
            video.save(update_fields=['title'])

        record_audit_event(
            user=request.user,
            event_type='api.video.upload',
            request=request,
            metadata={'video_id': video.id, 'filename': uploaded_file.name}
        )

        validate_source_task.delay(video.id)
        return Response(VideoSourceSerializer(video).data, status=status.HTTP_201_CREATED)


class VideoUrlImportAPIView(generics.CreateAPIView):
    serializer_class = VideoUrlImportSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = serializer.validated_data['source_url']
        video = serializer.save(
            user=request.user,
            source_type=VideoSource.SOURCE_URL,
            status=VideoSource.STATUS_PENDING
        )
        if not video.title:
            video.title = url.split('/')[-1].split('?')[0] or "Imported Video"
            video.save(update_fields=['title'])

        record_audit_event(
            user=request.user,
            event_type='api.video.import_url',
            request=request,
            metadata={'video_id': video.id, 'url': url}
        )

        validate_source_task.delay(video.id)
        return Response(VideoSourceSerializer(video).data, status=status.HTTP_201_CREATED)


class VideoSourceDetailAPIView(generics.RetrieveDestroyAPIView):
    serializer_class = VideoSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VideoSource.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        record_audit_event(
            user=self.request.user,
            event_type='api.video.deleted',
            request=self.request,
            metadata={'video_id': instance.id, 'title': instance.title}
        )
        instance.delete_file()
