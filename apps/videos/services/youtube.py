import os
import re
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import yt_dlp
from yt_dlp.utils import download_range_func

logger = logging.getLogger(__name__)


class YouTubeDownloadError(Exception):
    pass


class YouTubeDownloaderService:
    """Service to safely inspect and download YouTube videos using yt-dlp."""

    @classmethod
    def is_youtube_url(cls, url: str) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower().split(':')[0]
            valid_domains = ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be', 'youtube-nocookie.com')
            return netloc in valid_domains or any(netloc.endswith('.' + d) for d in ['youtube.com', 'youtu.be'])
        except Exception:
            return False

    @classmethod
    def _get_base_opts(cls) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
        }
        if os.path.exists('/usr/bin/node'):
            opts['js_runtimes'] = {'node': {'path': '/usr/bin/node'}}
        return opts

    @classmethod
    def extract_info(cls, url: str) -> Dict[str, Any]:
        """Extract video metadata without downloading the video payload."""
        ydl_opts = cls._get_base_opts()
        ydl_opts.update({
            'quiet': True,
            'skip_download': True,
        })
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'id': info.get('id', ''),
                    'title': info.get('title', 'YouTube Video'),
                    'duration': float(info.get('duration') or 0.0),
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', ''),
                    'width': info.get('width', 1280),
                    'height': info.get('height', 720),
                    'chapters': info.get('chapters') or [],
                    'heatmap': info.get('heatmap') or [],
                }
        except Exception as e:
            logger.error(f"Failed to extract YouTube info for {url}: {e}")
            raise YouTubeDownloadError(f"Could not retrieve YouTube video info: {str(e)[:150]}")

    @classmethod
    def download_video(
        cls,
        url: str,
        target_directory: str,
        max_duration: int = 86400,
        start_time: float = 0.0,
        clip_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """Download video to target_directory with fast MP4 format <= 720p."""
        os.makedirs(target_directory, exist_ok=True)
        out_template = os.path.join(target_directory, '%(id)s.%(ext)s')

        # Fast format: prefer direct pre-merged MP4 stream for ultra-fast download speed
        fast_format = 'best[ext=mp4][height<=720]/bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[height<=720]/best'

        # Try fast range download first if clip_duration is specified
        if clip_duration and clip_duration > 0:
            try:
                range_opts = cls._get_base_opts()
                range_opts.update({
                    'format': fast_format,
                    'outtmpl': out_template,
                    'merge_output_format': 'mp4',
                    'download_ranges': download_range_func(None, [(start_time, start_time + clip_duration + 5.0)]),
                    'force_keyframes_at_cuts': True,
                    'max_filesize': 500 * 1024 * 1024,
                })
                with yt_dlp.YoutubeDL(range_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_id = info.get('id')
                    filename = ydl.prepare_filename(info)
                    base, _ = os.path.splitext(filename)
                    final_path = f"{base}.mp4"
                    if not os.path.exists(final_path) and os.path.exists(filename):
                        final_path = filename

                    if os.path.exists(final_path):
                        return {
                            'id': video_id,
                            'title': info.get('title', 'YouTube Video'),
                            'duration': float(info.get('duration') or 0.0),
                            'file_path': final_path,
                            'thumbnail': info.get('thumbnail', ''),
                            'width': info.get('width', 1280),
                            'height': info.get('height', 720),
                            'is_range_downloaded': True,
                        }
            except Exception as re_err:
                logger.warning(f"Selective range download failed, falling back to full download: {re_err}")

        # Standard download fallback
        ydl_opts = cls._get_base_opts()
        ydl_opts.update({
            'format': fast_format,
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'max_filesize': 500 * 1024 * 1024,  # 500MB
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info.get('id')
                filename = ydl.prepare_filename(info)
                # Ensure .mp4 extension after merge
                base, _ = os.path.splitext(filename)
                final_path = f"{base}.mp4"
                if not os.path.exists(final_path) and os.path.exists(filename):
                    final_path = filename

                duration = float(info.get('duration') or 0.0)
                if duration > max_duration:
                    try:
                        os.remove(final_path)
                    except OSError:
                        pass
                    raise YouTubeDownloadError(f"Video is too long ({int(duration)}s). Maximum allowed length is {max_duration // 60} minutes.")

                return {
                    'id': video_id,
                    'title': info.get('title', 'YouTube Video'),
                    'duration': duration,
                    'file_path': final_path,
                    'thumbnail': info.get('thumbnail', ''),
                    'width': info.get('width', 1920),
                    'height': info.get('height', 1080),
                    'is_range_downloaded': False,
                }
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp download failed: {e}")
            raise YouTubeDownloadError("Failed to download YouTube video. Please check the URL or try another link.")
        except Exception as e:
            logger.exception(f"Unexpected error downloading {url}: {e}")
            raise YouTubeDownloadError(f"Download failed: {str(e)[:150]}")
