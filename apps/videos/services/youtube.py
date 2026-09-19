import os
import re
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, parse_qs, urlencode
import yt_dlp
from yt_dlp.utils import download_range_func
from django.conf import settings

logger = logging.getLogger(__name__)


class YouTubeDownloadError(Exception):
    pass


class YouTubeDownloaderService:
    """
    Robust, production-hardened service to safely inspect and download
    YouTube and universal web video URLs using yt-dlp.
    
    Features:
    - URL normalization: extracts video ID and strips playlists, mixes, and tracking params.
    - VPS Bot-Bypass: Uses YouTube Android & iOS mobile clients in extractor_args.
    - Automatic cookies.txt discovery and support.
    - Proxy support via settings / env.
    - Automatic fallback client rotation.
    - Support for any video platform (TikTok, Instagram, Facebook, Twitter/X, Vimeo, direct MP4).
    """

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
    def get_cookies_path(cls) -> Optional[str]:
        """
        Locate YouTube cookies.txt file or materialize it from environment variable.
        Supported locations:
        1. settings.YOUTUBE_COOKIES_PATH / env YOUTUBE_COOKIES_PATH
        2. BASE_DIR / 'cookies.txt'
        3. /app/cookies.txt (Docker container)
        4. MEDIA_ROOT / 'cookies.txt'
        5. Raw content in YOUTUBE_COOKIES_CONTENT env var (written to /tmp)
        """
        # 1. Direct path setting
        custom_path = getattr(settings, 'YOUTUBE_COOKIES_PATH', '') or os.getenv('YOUTUBE_COOKIES_PATH', '')
        if custom_path and os.path.isfile(custom_path):
            return custom_path

        # 2. Project root cookies.txt
        base_dir = getattr(settings, 'BASE_DIR', None)
        if base_dir:
            root_cookie = os.path.join(str(base_dir), 'cookies.txt')
            if os.path.isfile(root_cookie):
                return root_cookie

        # 3. Docker / standard Linux path
        if os.path.isfile('/app/cookies.txt'):
            return '/app/cookies.txt'

        # 4. MEDIA_ROOT cookies.txt
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if media_root:
            media_cookie = os.path.join(str(media_root), 'cookies.txt')
            if os.path.isfile(media_cookie):
                return media_cookie

        # 5. Content env var
        raw_content = getattr(settings, 'YOUTUBE_COOKIES_CONTENT', '') or os.getenv('YOUTUBE_COOKIES_CONTENT', '')
        if raw_content and raw_content.strip():
            temp_cookie = '/tmp/toolyt_youtube_cookies.txt'
            try:
                with open(temp_cookie, 'w', encoding='utf-8') as f:
                    f.write(raw_content.strip() + '\n')
                return temp_cookie
            except Exception as e:
                logger.warning(f"Failed to write YOUTUBE_COOKIES_CONTENT to {temp_cookie}: {e}")

        return None

    @classmethod
    def get_proxy(cls) -> Optional[str]:
        """Get configured proxy for video downloads if set."""
        proxy = (
            getattr(settings, 'YOUTUBE_PROXY', '') or
            os.getenv('YOUTUBE_PROXY', '') or
            os.getenv('HTTP_PROXY', '') or
            os.getenv('HTTPS_PROXY', '')
        )
        return proxy.strip() if proxy else None

    @classmethod
    def _get_base_opts(cls, player_clients: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Construct production-hardened yt-dlp options.
        Uses mobile clients (Android, iOS) to bypass VPS datacenter bot blocking.
        """
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

        # Mobile client extractor bypass for YouTube
        clients = player_clients or ['android', 'ios']
        opts['extractor_args'] = {
            'youtube': {
                'player_client': clients,
                'player_skip': ['webpage', 'configs'],
            }
        }

        # Cookies configuration
        cookie_path = cls.get_cookies_path()
        if cookie_path:
            logger.info(f"Using YouTube cookie file: {cookie_path}")
            opts['cookiefile'] = cookie_path

        # Proxy configuration
        proxy = cls.get_proxy()
        if proxy:
            logger.info(f"Using proxy for download: {proxy[:15]}...")
            opts['proxy'] = proxy

        # JS Runtime for signature deciphering if present
        if os.path.exists('/usr/bin/node'):
            opts['js_runtimes'] = {'node': {'path': '/usr/bin/node'}}

        return opts

    @classmethod
    def extract_info(cls, url: str) -> Dict[str, Any]:
        """Extract video metadata without downloading the video payload."""
        url = cls.clean_youtube_url(url)
        is_yt = cls.is_youtube_url(url)

        client_attempts = [
            ['android', 'ios'],
            ['ios', 'android'],
            ['tv_embedded', 'mweb', 'web'],
        ] if is_yt else [None]

        last_err = None
        for clients in client_attempts:
            ydl_opts = cls._get_base_opts(player_clients=clients)
            ydl_opts.update({
                'quiet': True,
                'skip_download': True,
            })
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
                last_err = e
                logger.warning(f"Extract info attempt with clients {clients} failed: {e}")

        logger.error(f"Failed to extract info for {url}: {last_err}")
        err_msg = str(last_err) if last_err else "Unknown error"
        if "bot" in err_msg.lower() or "sign in" in err_msg.lower():
            raise YouTubeDownloadError(
                "YouTube bot protection blocked access from this server IP. "
                "Please upload the video file directly, or configure cookies.txt on the server."
            )
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

        client_attempts = [
            ['android', 'ios'],
            ['ios', 'android'],
            ['tv_embedded', 'mweb', 'web'],
        ] if is_yt else [None]

        # 1. Try fast range download first if clip_duration is specified (YouTube only)
        if is_yt and clip_duration and clip_duration > 0:
            for clients in client_attempts:
                try:
                    range_opts = cls._get_base_opts(player_clients=clients)
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
                    logger.warning(f"Selective range download failed with clients {clients}: {re_err}")
                    # If it's a bot check error, try next client; otherwise break to full download
                    if "bot" not in str(re_err).lower() and "sign in" not in str(re_err).lower():
                        break

        # 2. Standard full download with client rotation
        last_err = None
        for clients in client_attempts:
            ydl_opts = cls._get_base_opts(player_clients=clients)
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
                last_err = e
                logger.warning(f"Download attempt with clients {clients} failed: {e}")

        logger.error(f"yt-dlp download failed completely for {url}: {last_err}")
        err_str = str(last_err) if last_err else "Download failed."
        if "bot" in err_str.lower() or "sign in" in err_str.lower():
            raise YouTubeDownloadError(
                "YouTube bot protection blocked downloads from this server IP. "
                "Tip: You can upload your video file directly on the home page, or add cookies.txt to your server."
            )
        raise YouTubeDownloadError(f"Failed to download video: {err_str[:150]}")


# Universal alias for clarity across the codebase
VideoDownloaderService = YouTubeDownloaderService

