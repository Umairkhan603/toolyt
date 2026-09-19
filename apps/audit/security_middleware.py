import time
import hashlib
from collections import defaultdict
from django.http import JsonResponse
from django.conf import settings


class RateLimitMiddleware:
    """
    Simple in-memory rate limiter for conversion POST requests.
    Limits requests per IP to prevent abuse.
    For production with multiple workers, replace with Redis-based rate limiting.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._request_log = defaultdict(list)
        self._max_requests = getattr(settings, 'RATE_LIMIT_CONVERSIONS_PER_MINUTE', 5)
        self._window_seconds = 60

    def __call__(self, request):
        # Only rate-limit POST requests to the home (conversion) endpoint
        if request.method == 'POST' and request.path == '/':
            ip = self._get_client_ip(request)
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]

            now = time.time()
            cutoff = now - self._window_seconds

            # Clean old entries
            self._request_log[ip_hash] = [
                t for t in self._request_log[ip_hash] if t > cutoff
            ]

            if len(self._request_log[ip_hash]) >= self._max_requests:
                from django.contrib import messages
                messages.error(request, f"Too many requests. Please wait a minute before converting another video.")
                from django.shortcuts import redirect
                return redirect('home')

            self._request_log[ip_hash].append(now)

        return self.get_response(request)

    def _get_client_ip(self, request):
        """Extract real client IP, handling reverse proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first (client) IP from the chain
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


class SecurityHeadersMiddleware:
    """
    Adds additional security headers not covered by Django's built-in middleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Permissions-Policy: restrict powerful browser features
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=(), '
            'accelerometer=()'
        )

        # Cross-Origin policies
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-origin'

        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'

        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        return response
