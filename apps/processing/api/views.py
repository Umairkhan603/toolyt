from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.processing.models import ProcessingJob
from .serializers import ProcessingJobSerializer, ProcessingJobCreateSerializer
from apps.processing.tasks import process_video_job_task
from apps.audit.utils import record_audit_event


class ProcessingJobListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProcessingJobCreateSerializer
        return ProcessingJobSerializer

    def get_queryset(self):
        return ProcessingJob.objects.filter(
            user=self.request.user
        ).select_related('video_source').order_by('-created_at')

    def perform_create(self, serializer):
        job = serializer.save(user=self.request.user, status=ProcessingJob.STATUS_PENDING, progress=0)
        record_audit_event(
            user=self.request.user,
            event_type='api.job.created',
            request=self.request,
            metadata={'job_id': job.id, 'video_id': job.video_source_id}
        )
        process_video_job_task.delay(job.id)


class ProcessingJobDetailAPIView(generics.RetrieveAPIView):
    serializer_class = ProcessingJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProcessingJob.objects.filter(
            user=self.request.user
        ).select_related('video_source').prefetch_related('clips')


class ProcessingJobCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        try:
            job = ProcessingJob.objects.get(id=pk, user=request.user)
        except ProcessingJob.DoesNotExist:
            return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

        if job.status in [ProcessingJob.STATUS_PENDING, ProcessingJob.STATUS_PROCESSING]:
            job.status = ProcessingJob.STATUS_CANCELLED
            job.save(update_fields=['status'])
            record_audit_event(
                user=request.user,
                event_type='api.job.cancelled',
                request=request,
                metadata={'job_id': job.id}
            )
            return Response({'status': 'cancelled', 'job_id': job.id}, status=status.HTTP_200_OK)

        return Response({'error': f"Cannot cancel job in status '{job.status}'."}, status=status.HTTP_400_BAD_REQUEST)


class ProcessingJobRetryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        try:
            job = ProcessingJob.objects.get(id=pk, user=request.user)
        except ProcessingJob.DoesNotExist:
            return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

        job.status = ProcessingJob.STATUS_PENDING
        job.progress = 0
        job.error_message = ""
        job.started_at = None
        job.completed_at = None
        job.save()

        record_audit_event(
            user=request.user,
            event_type='api.job.retried',
            request=request,
            metadata={'job_id': job.id}
        )
        process_video_job_task.delay(job.id)
        return Response({'status': 'queued', 'job_id': job.id}, status=status.HTTP_200_OK)
