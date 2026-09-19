import time
from typing import Callable, Dict, List
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.core.cache import cache


class AuditLoggingMiddleware:
    """Middleware to enforce IP rate-limiting, security headers, and request auditing."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def get_client_ip(self, request: HttpRequest) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')

    def check_rate_limit(self, ip: str, limit: int = 15, window_seconds: int = 60) -> bool:
        """Rate limit conversion POST submissions (max 15 requests per minute per IP)."""
        cache_key = f"rate_limit_{ip}"
        now = time.time()
        requests: List[float] = cache.get(cache_key, [])
        # Filter timestamps within window
        valid_requests = [t for t in requests if now - t < window_seconds]
        if len(valid_requests) >= limit:
            return False

        valid_requests.append(now)
        cache.set(cache_key, valid_requests, window_seconds)
        return True

    def __call__(self, request: HttpRequest) -> HttpResponse:
        ip = self.get_client_ip(request)
        request.client_ip = ip

        # Rate limit POST conversion requests
        if request.method == 'POST' and request.path in ('/', '/api/jobs/'):
            if not self.check_rate_limit(ip):
                return HttpResponseForbidden("Rate limit exceeded. Please wait a minute before submitting more video conversion jobs.")

        response = self.get_response(request)

        # Enforce Security Headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "img-src 'self' data: blob: https:; "
            "video-src 'self' blob:; "
            "media-src 'self' blob:; "
            "connect-src 'self';"
        )

        return response
