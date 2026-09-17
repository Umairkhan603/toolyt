import os
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse, Http404
from apps.exports.models import GeneratedClip
from .serializers import GeneratedClipSerializer
from apps.audit.utils import record_audit_event


class GeneratedClipListAPIView(generics.ListAPIView):
    serializer_class = GeneratedClipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GeneratedClip.objects.filter(
            job__user=self.request.user,
            status=GeneratedClip.STATUS_READY
        ).select_related('job', 'job__video_source').order_by('-created_at')


class GeneratedClipDetailAPIView(generics.RetrieveDestroyAPIView):
    serializer_class = GeneratedClipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GeneratedClip.objects.filter(
            job__user=self.request.user
        ).select_related('job', 'job__video_source')

    def perform_destroy(self, instance):
        record_audit_event(
            user=self.request.user,
            event_type='api.clip.deleted',
            request=self.request,
            metadata={'clip_id': instance.id, 'job_id': instance.job_id}
        )
        instance.delete_files()


class GeneratedClipDownloadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        try:
            clip = GeneratedClip.objects.select_related('job').get(id=pk, job__user=request.user)
        except GeneratedClip.DoesNotExist:
            raise Http404("Clip not found.")

        if not clip.output_file or not os.path.exists(clip.output_file.path):
            raise Http404("Clip file not found on disk.")

        record_audit_event(
            user=request.user,
            event_type='api.clip.downloaded',
            request=request,
            metadata={'clip_id': clip.id, 'job_id': clip.job_id}
        )

        response = FileResponse(open(clip.output_file.path, 'rb'), content_type='video/mp4')
        filename = f"short_{clip.id}.mp4"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
