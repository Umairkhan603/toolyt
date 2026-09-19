import os
import re
import socket
import ipaddress
from urllib.parse import urlparse
from django.core.exceptions import ValidationError
from django.conf import settings


def is_safe_url(url: str) -> bool:
    """
    Validate that a URL is a safe public HTTP/HTTPS URL.
    Prevents SSRF attacks by resolving hostname and blocking private, loopback, and link-local IP addresses.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname = hostname.lower()

        # Reject explicit local hostnames
        if hostname in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            return False

        if hostname.endswith('.local') or hostname.endswith('.internal'):
            return False

        # Resolve hostname to IP addresses
        ip_list = []
        try:
            # Check if direct IP literal
            ip_obj = ipaddress.ip_address(hostname)
            ip_list.append(ip_obj)
        except ValueError:
            # Resolve DNS
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                ip_list.append(ipaddress.ip_address(ip_str))

        for ip in ip_list:
            if (
                ip.is_loopback or
                ip.is_private or
                ip.is_link_local or
                ip.is_multicast or
                ip.is_reserved or
                ip.is_unspecified
            ):
                return False

        return True
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and shell issues."""
    name, ext = os.path.splitext(filename)
    # Remove any non-alphanumeric characters except - and _
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    clean_ext = ext.lower()
    return f"{clean_name[:60]}{clean_ext}"


def validate_video_file_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file extension '{ext}'. Allowed extensions are: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}"
        )


def validate_video_file_size(value):
    if value.size > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise ValidationError(
            f"File size exceeds maximum allowed limit of {max_mb} MB."
        )
