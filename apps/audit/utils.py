import logging
from typing import Optional, Dict, Any
from .models import AuditEvent

logger = logging.getLogger('audit')


def get_client_ip(request) -> Optional[str]:
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    sensitive_keys = {'password', 'token', 'secret', 'key', 'auth'}
    cleaned = {}
    for k, v in metadata.items():
        if any(s in k.lower() for s in sensitive_keys):
            cleaned[k] = '***REDACTED***'
        else:
            cleaned[k] = v
    return cleaned


def record_audit_event(
    event_type: str,
    user=None,
    request=None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditEvent:
    if request and not user and request.user.is_authenticated:
        user = request.user
    if request and not ip_address:
        ip_address = get_client_ip(request)

    meta = sanitize_metadata(metadata or {})
    event = AuditEvent.objects.create(
        user=user if (user and getattr(user, 'is_authenticated', True)) else None,
        event_type=event_type,
        ip_address=ip_address,
        metadata=meta
    )
    logger.info(f"AUDIT: {event}")
    return event
