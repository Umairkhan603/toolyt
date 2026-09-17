from rest_framework import serializers, generics, permissions
from apps.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ('id', 'event_type', 'ip_address', 'metadata', 'created_at')


class AuditEventListAPIView(generics.ListAPIView):
    serializer_class = AuditEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AuditEvent.objects.filter(user=self.request.user).order_by('-created_at')[:100]
