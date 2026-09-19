import os
from .base import *

DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-me-in-production-secret-key-12345')

allowed_hosts_str = os.getenv('DJANGO_ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()]

# PostgreSQL Database setup if provided
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    from urllib.parse import urlparse

    db_url = urlparse(DATABASE_URL)

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': db_url.path.lstrip('/'),
            'USER': db_url.username,
            'PASSWORD': db_url.password,
            'HOST': db_url.hostname,
            'PORT': db_url.port or '5432',
        }
    }
elif os.getenv('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'shorts_converter'),
            'USER': os.getenv('POSTGRES_USER', 'postgres'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }

# =====================================================
# Security Hardening
# =====================================================

# XSS & Content Type Protection
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Clickjacking Protection
X_FRAME_OPTIONS = 'DENY'

# Cookie Security
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = os.getenv('SECURE_COOKIES', 'False').lower() in ('true', '1')
SESSION_COOKIE_SECURE = os.getenv('SECURE_COOKIES', 'False').lower() in ('true', '1')
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Session Expiry - 2 hours of inactivity
SESSION_COOKIE_AGE = 7200
SESSION_SAVE_EVERY_REQUEST = True

# HTTPS / SSL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1')

# HSTS (HTTP Strict Transport Security) - Enable in production with HTTPS
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_SUBDOMAINS', 'False').lower() in ('true', '1')
SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', 'False').lower() in ('true', '1')

# Referrer Policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Permissions Policy - restrict browser features
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Admin URL (obscure default /admin/ path)
ADMIN_URL = os.getenv('ADMIN_URL', 'admin/')

# =====================================================
# Rate Limiting Configuration
# =====================================================

# Max conversion requests per IP per minute
RATE_LIMIT_CONVERSIONS_PER_MINUTE = int(os.getenv('RATE_LIMIT_CONVERSIONS', '5'))

# Celery
CELERY_TASK_ALWAYS_EAGER = False
