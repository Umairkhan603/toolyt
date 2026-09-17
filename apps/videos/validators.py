import os
import re
from django.core.exceptions import ValidationError
from django.conf import settings


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
