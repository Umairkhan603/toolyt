from django.db import models
from apps.videos.models import VideoSource


class Transcript(models.Model):
    video_source = models.OneToOneField(VideoSource, on_delete=models.CASCADE, related_name='transcript')
    raw_text = models.TextField(blank=True)
    segments = models.JSONField(default=list, blank=True, help_text="Timestamped segments [{start, end, text}]")
    language = models.CharField(max_length=10, default='en')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transcript for Video #{self.video_source_id}"

    def to_srt(self) -> str:
        """Export segments to SubRip (SRT) format."""
        lines = []
        for idx, seg in enumerate(self.segments, 1):
            start_s = seg.get('start', 0.0)
            end_s = seg.get('end', 0.0)
            text = seg.get('text', '').strip()

            def format_timestamp(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                ms = int((sec - int(sec)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            lines.append(f"{idx}")
            lines.append(f"{format_timestamp(start_s)} --> {format_timestamp(end_s)}")
            lines.append(text)
            lines.append("")
        return "\n".join(lines)
