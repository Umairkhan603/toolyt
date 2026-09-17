from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'user', 'ip_address')
    list_filter = ('event_type', 'created_at')
    search_fields = ('user__username', 'event_type', 'ip_address')
    readonly_fields = ('created_at', 'user', 'event_type', 'ip_address', 'metadata')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
