import json
import logging
import os
import subprocess
from typing import Dict, Any, Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class VideoProcessingError(Exception):
    """Base exception for video processing pipeline errors."""
    pass


class FFmpegService:
    """Service encapsulating all FFprobe and FFmpeg operations safely using argument arrays."""

    @staticmethod
    def get_ffmpeg_bin() -> str:
        return getattr(settings, 'FFMPEG_PATH', 'ffmpeg')

    @staticmethod
    def get_ffprobe_bin() -> str:
        return getattr(settings, 'FFPROBE_PATH', 'ffprobe')

    @classmethod
    def probe_video(cls, file_path: str) -> Dict[str, Any]:
        """
        Inspect video metadata safely using ffprobe.
        Returns a dictionary with duration, width, height, codecs, bit_rate, etc.
        """
        if not os.path.exists(file_path):
            raise VideoProcessingError(f"Video file not found: {file_path}")

        args = [
            cls.get_ffprobe_bin(),
            '-v', 'error',
            '-show_format',
            '-show_streams',
            '-of', 'json',
            file_path
        ]

        try:
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=30
            )
            data = json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            raise VideoProcessingError("FFprobe timed out analyzing media file.")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe failed: {e.stderr}")
            raise VideoProcessingError(f"Media validation failed: {e.stderr.strip() or 'Corrupt file'}")
        except json.JSONDecodeError:
            raise VideoProcessingError("Failed to parse FFprobe output.")

        streams = data.get('streams', [])
        format_info = data.get('format', {})

        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)

        if not video_stream:
            raise VideoProcessingError("File contains no valid video stream.")

        # Extract dimensions
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        if width <= 0 or height <= 0:
            raise VideoProcessingError("Invalid video resolution detected.")

        # Extract duration
        duration = 0.0
        if 'duration' in format_info:
            try:
                duration = float(format_info['duration'])
            except (ValueError, TypeError):
                duration = 0.0
        if duration <= 0 and 'duration' in video_stream:
            try:
                duration = float(video_stream['duration'])
            except (ValueError, TypeError):
                duration = 0.0

        file_size = int(format_info.get('size', os.path.getsize(file_path)))

        return {
            'width': width,
            'height': height,
            'duration': duration,
            'file_size': file_size,
            'video_codec': video_stream.get('codec_name', 'unknown'),
            'audio_codec': audio_stream.get('codec_name', 'none') if audio_stream else None,
            'has_audio': audio_stream is not None,
            'bit_rate': int(format_info.get('bit_rate', 0)),
            'format_name': format_info.get('format_name', ''),
        }

    @classmethod
    def generate_thumbnail(cls, video_path: str, output_thumbnail_path: str, timestamp: float = 1.0) -> str:
        """Capture a high-quality preview frame as thumbnail."""
        os.makedirs(os.path.dirname(output_thumbnail_path), exist_ok=True)
        args = [
            cls.get_ffmpeg_bin(),
            '-y',
            '-ss', str(max(0.0, timestamp)),
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',
            output_thumbnail_path
        ]
        try:
            subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=20
            )
            return output_thumbnail_path
        except Exception as e:
            logger.warning(f"Thumbnail generation failed at {timestamp}s, trying 0s: {e}")
            fallback_args = [
                cls.get_ffmpeg_bin(),
                '-y',
                '-ss', '0',
                '-i', video_path,
                '-vframes', '1',
                '-q:v', '2',
                output_thumbnail_path
            ]
            subprocess.run(fallback_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=20)
            return output_thumbnail_path

    @classmethod
    def build_video_filter(
        cls,
        crop_mode: str,
        watermark_text: Optional[str] = None,
        subtitle_file: Optional[str] = None,
        anti_copyright: bool = True
    ) -> str:
        """
        Build the vertical 9:16 filter graph safely.
        Target: 1080x1920
        """
        filter_parts = []

        if crop_mode == 'blur':
            # Blur background with center-fitted foreground
            filter_str = (
                "split=2[bg][fg];"
                "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bgblur];"
                "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fgscaled];"
                "[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2"
            )
        elif crop_mode == 'fit':
            # Fit with black background
            filter_str = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black"
        else:
            # Default: center crop
            filter_str = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

        filter_parts.append(filter_str)

        # Optional subtitle burn-in
        if subtitle_file and os.path.exists(subtitle_file):
            # Escape path for ffmpeg subtitles filter
            escaped_sub_path = subtitle_file.replace('\\', '/').replace(':', '\\:')
            filter_parts.append(f"subtitles='{escaped_sub_path}'")

        # Anti-copyright transformative video adjustments
        if anti_copyright:
            # Subtle color grading: enriched contrast and vibrancy
            filter_parts.append("eq=contrast=1.05:brightness=0.01:saturation=1.08")
            # Subtle edge unsharp mask for enhanced clarity and unique pixel signature
            filter_parts.append("unsharp=3:3:0.5:3:3:0.0")
            # Sync video speed to 1.03x to match audio tempo shift
            filter_parts.append("setpts=PTS/1.03")

        # Optional watermark text overlay
        if watermark_text:
            # Clean watermark text
            clean_text = "".join(c for c in watermark_text if c.isalnum() or c in " -_@.").strip()
            if clean_text:
                filter_parts.append(
                    f"drawtext=text='{clean_text}':x=(w-tw)/2:y=h-th-80:fontsize=36:fontcolor=white@0.85:shadowcolor=black@0.7:shadowx=2:shadowy=2"
                )

        return ",".join(filter_parts)

    @classmethod
    def render_clip(
        cls,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        crop_mode: str = 'center',
        watermark_text: Optional[str] = None,
        subtitle_file: Optional[str] = None,
        volume_multiplier: float = 1.0,
        anti_copyright: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract and convert a clip to 9:16 vertical MP4 (1080x1920) H.264/AAC.
        """
        if not os.path.exists(input_path):
            raise VideoProcessingError(f"Source file not found: {input_path}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        vf = cls.build_video_filter(
            crop_mode=crop_mode,
            watermark_text=watermark_text,
            subtitle_file=subtitle_file,
            anti_copyright=anti_copyright
        )

        args = [
            cls.get_ffmpeg_bin(),
            '-y',
            '-i', input_path,
            '-ss', str(max(0.0, start_time)),
            '-t', str(max(1.0, duration)),
        ]

        args.extend([
            '-vf', vf,
            '-c:v', 'libx264',
            '-preset', 'superfast',
            '-tune', 'fastdecode',
            '-crf', '22',
            '-threads', '0',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
        ])

        # Audio filters: volume and anti-copyright frequency/tempo shifting
        main_a_filters = []
        if anti_copyright:
            # 1.03x tempo shift: changes audio frequency spectrum without changing voice quality
            main_a_filters.append("atempo=1.03")
            # Voice equalization tweaks to disrupt acoustic fingerprinting
            main_a_filters.append("equalizer=f=1000:t=q:w=1:g=-1.5")
            main_a_filters.append("equalizer=f=3000:t=q:w=1:g=1.5")

        if volume_multiplier != 1.0:
            main_a_filters.append(f"volume={volume_multiplier}")

        if main_a_filters:
            args.extend(['-filter:a', ",".join(main_a_filters)])

        args.append(output_path)

        try:
            process = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=300
            )
        except subprocess.TimeoutExpired:
            raise VideoProcessingError("FFmpeg encoding exceeded timeout limit.")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg encoding failed: {e.stderr}")
            raise VideoProcessingError(f"Video encoding failed: {e.stderr.strip()[:200]}")

        # Validate output
        output_meta = cls.probe_video(output_path)
        return output_meta
