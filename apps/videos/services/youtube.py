import os
import re
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode
import yt_dlp
from yt_dlp.utils import download_range_func

logger = logging.getLogger(__name__)


class YouTubeDownloadError(Exception):
    pass


class YouTubeDownloaderService:
    """
    Service to safely inspect and download video URLs using yt-dlp.

    Features:
    - URL normalization: extracts video ID and strips playlists, mixes, and tracking params.
    - Clean error handling with user-friendly messages for bot-protection failures.
    - Support for any video platform (TikTok, Instagram, Facebook, Twitter/X, Vimeo, direct MP4).
    """

    # User-friendly error message shown when YouTube blocks the download
    BOT_PROTECTION_MESSAGE = (
        "This server cannot download YouTube videos automatically due to bot protection. "
        "Please use the 'Upload File' tab on the home page to upload your video directly."
    )

    @classmethod
    def clean_youtube_url(cls, url: str) -> str:
        """
        Normalize and clean a YouTube URL so that playlist, radio mix, or index
        parameters NEVER cause yt-dlp to download the wrong video.
        """
        if not url:
            return ""
        url = url.strip()
        if not cls.is_youtube_url(url):
            return url

        # Match YouTube 11-character video ID
        # Matches: watch?v=ID, shorts/ID, youtu.be/ID, embed/ID, live/ID, v/ID
        id_match = re.search(r'(?:v=|\/shorts\/|\/embed\/|\/live\/|\/v\/|youtu\.be\/)([0-9A-Za-z_-]{11})', url)
        if id_match:
            video_id = id_match.group(1)
            # If original was a Shorts URL, keep /shorts/ID, otherwise use /watch?v=ID
            if '/shorts/' in url:
                return f"https://www.youtube.com/shorts/{video_id}"
            return f"https://www.youtube.com/watch?v={video_id}"

        # If no 11-char ID found, strip 'list' and 'index' params if present to avoid playlist hijacking
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            query.pop('list', None)
            query.pop('index', None)
            query.pop('start_radio', None)
            cleaned_query = urlencode(query, doseq=True)
            return parsed._replace(query=cleaned_query).geturl()
        except Exception:
            return url

    @classmethod
    def is_youtube_url(cls, url: str) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower().split(':')[0]
            valid_domains = (
                'youtube.com', 'www.youtube.com', 'm.youtube.com',
                'youtu.be', 'www.youtu.be', 'youtube-nocookie.com'
            )
            return netloc in valid_domains or any(netloc.endswith('.' + d) for d in ['youtube.com', 'youtu.be'])
        except Exception:
            return False

    @classmethod
    def is_supported_url(cls, url: str) -> bool:
        """Check if URL is a valid web video link that can be processed."""
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urlparse(url.strip())
            return parsed.scheme.lower() in ('http', 'https') and bool(parsed.netloc)
        except Exception:
            return False

    @classmethod
    def _is_bot_protection_error(cls, error_message: str) -> bool:
        """Check if an error message indicates YouTube bot protection."""
        if not error_message:
            return False
        msg_lower = error_message.lower()
        bot_indicators = [
            'bot', 'sign in', 'confirm you', 'captcha',
            'automated', 'not a robot', 'verify',
            'auth', 'login required',
        ]
        return any(indicator in msg_lower for indicator in bot_indicators)

    @classmethod
    def _get_base_opts(cls) -> Dict[str, Any]:
        """Construct standard yt-dlp options."""
        opts: Dict[str, Any] = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }
        return opts

    @classmethod
    def extract_info(cls, url: str) -> Dict[str, Any]:
        """Extract video metadata without downloading the video payload."""
        url = cls.clean_youtube_url(url)

        ydl_opts = cls._get_base_opts()
        ydl_opts['skip_download'] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                # Handle playlist wrapper if returned
                if info.get('_type') == 'playlist' and info.get('entries'):
                    entries = [e for e in info['entries'] if e]
                    if entries:
                        info = entries[0]

                return {
                    'id': info.get('id', ''),
                    'title': info.get('title', 'Imported Video'),
                    'duration': float(info.get('duration') or 0.0),
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', ''),
                    'width': info.get('width', 1280) or 1280,
                    'height': info.get('height', 720) or 720,
                    'chapters': info.get('chapters') or [],
                    'heatmap': info.get('heatmap') or [],
                }
        except Exception as e:
            logger.error(f"Failed to extract info for {url}: {e}")
            err_msg = str(e)
            if cls._is_bot_protection_error(err_msg):
                raise YouTubeDownloadError(cls.BOT_PROTECTION_MESSAGE)
            raise YouTubeDownloadError(f"Could not retrieve video info: {err_msg[:150]}")

    @classmethod
    def download_video(
        cls,
        url: str,
        target_directory: str,
        max_duration: int = 86400,
        start_time: float = 0.0,
        clip_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Download video to target_directory with fast MP4 format <= 720p.
        Works seamlessly for YouTube and any other platform supported by yt-dlp.
        """
        url = cls.clean_youtube_url(url)
        is_yt = cls.is_youtube_url(url)
        os.makedirs(target_directory, exist_ok=True)
        out_template = os.path.join(target_directory, '%(id)s.%(ext)s')

        # Fast format preference
        fast_format = (
            'best[ext=mp4][height<=720]/bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/'
            'best[height<=720]/best[ext=mp4]/best'
        )

        # 1. Try fast range download first if clip_duration is specified (YouTube only)
        if is_yt and clip_duration and clip_duration > 0:
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
                    if info.get('_type') == 'playlist' and info.get('entries'):
                        entries = [e for e in info['entries'] if e]
                        if entries:
                            info = entries[0]

                    video_id = info.get('id', 'video')
                    filename = ydl.prepare_filename(info)
                    base, _ = os.path.splitext(filename)
                    final_path = f"{base}.mp4"
                    if not os.path.exists(final_path) and os.path.exists(filename):
                        final_path = filename

                    if os.path.exists(final_path):
                        return {
                            'id': video_id,
                            'title': info.get('title', 'Video'),
                            'duration': float(info.get('duration') or 0.0),
                            'file_path': final_path,
                            'thumbnail': info.get('thumbnail', ''),
                            'width': info.get('width', 1280) or 1280,
                            'height': info.get('height', 720) or 720,
                            'is_range_downloaded': True,
                        }
            except Exception as re_err:
                logger.warning(f"Selective range download failed: {re_err}")
                # If it's a bot-protection error, raise immediately instead of retrying
                if cls._is_bot_protection_error(str(re_err)):
                    raise YouTubeDownloadError(cls.BOT_PROTECTION_MESSAGE)

        # 2. Standard full download
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
                if info.get('_type') == 'playlist' and info.get('entries'):
                    entries = [e for e in info['entries'] if e]
                    if entries:
                        info = entries[0]

                video_id = info.get('id', 'video')
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                final_path = f"{base}.mp4"
                if not os.path.exists(final_path) and os.path.exists(filename):
                    final_path = filename

                if not os.path.exists(final_path):
                    # Search directory for downloaded file with matching id
                    candidates = [
                        os.path.join(target_directory, f) for f in os.listdir(target_directory)
                        if f.startswith(str(video_id)) and not f.endswith('.part')
                    ]
                    if candidates:
                        final_path = candidates[0]

                duration = float(info.get('duration') or 0.0)
                if duration > max_duration:
                    try:
                        if os.path.exists(final_path):
                            os.remove(final_path)
                    except OSError:
                        pass
                    raise YouTubeDownloadError(
                        f"Video is too long ({int(duration)}s). Maximum allowed length is {max_duration // 60} minutes."
                    )

                return {
                    'id': video_id,
                    'title': info.get('title', 'Video'),
                    'duration': duration,
                    'file_path': final_path,
                    'thumbnail': info.get('thumbnail', ''),
                    'width': info.get('width', 1920) or 1920,
                    'height': info.get('height', 1080) or 1080,
                    'is_range_downloaded': False,
                }
        except YouTubeDownloadError:
            raise
        except Exception as e:
            logger.error(f"yt-dlp download failed for {url}: {e}")
            err_str = str(e)
            if cls._is_bot_protection_error(err_str):
                raise YouTubeDownloadError(cls.BOT_PROTECTION_MESSAGE)
            raise YouTubeDownloadError(f"Failed to download video: {err_str[:150]}")


# Universal alias for clarity across the codebase
VideoDownloaderService = YouTubeDownloaderService
