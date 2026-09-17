from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Public & dashboard views
from apps.accounts import public_views

# REST API views
from apps.accounts.api.views import RegisterApiView, LoginApiView, LogoutApiView, ProfileApiView
from apps.videos.api.views import (
    VideoSourceListAPIView,
    VideoUploadAPIView,
    VideoUrlImportAPIView,
    VideoSourceDetailAPIView
)
from apps.processing.api.views import (
    ProcessingJobListCreateAPIView,
    ProcessingJobDetailAPIView,
    ProcessingJobCancelAPIView,
    ProcessingJobRetryAPIView
)
from apps.exports.api.views import (
    GeneratedClipListAPIView,
    GeneratedClipDetailAPIView,
    GeneratedClipDownloadAPIView
)
from apps.audit.api import AuditEventListAPIView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public Pages
    path('', public_views.home_view, name='home'),
    path('features/', public_views.features_view, name='features'),
    path('terms/', public_views.terms_view, name='terms'),
    path('privacy/', public_views.privacy_view, name='privacy'),
    path('copyright/', public_views.copyright_policy_view, name='copyright'),

    # Authenticated UI Pages
    path('dashboard/', public_views.dashboard_view, name='dashboard'),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('videos/', include('apps.videos.urls', namespace='videos')),
    path('processing/', include('apps.processing.urls', namespace='processing')),
    path('clips/', include('apps.exports.urls', namespace='exports')),

    # REST API Endpoints (Section 9 of Specification)
    # Auth
    path('api/auth/register/', RegisterApiView.as_view(), name='api_register'),
    path('api/auth/login/', LoginApiView.as_view(), name='api_login'),
    path('api/auth/logout/', LogoutApiView.as_view(), name='api_logout'),
    path('api/auth/profile/', ProfileApiView.as_view(), name='api_profile'),

    # Video Sources
    path('api/videos/', VideoSourceListAPIView.as_view(), name='api_video_list'),
    path('api/videos/upload/', VideoUploadAPIView.as_view(), name='api_video_upload'),
    path('api/videos/import-url/', VideoUrlImportAPIView.as_view(), name='api_video_import_url'),
    path('api/videos/<int:pk>/', VideoSourceDetailAPIView.as_view(), name='api_video_detail'),

    # Processing Jobs
    path('api/jobs/', ProcessingJobListCreateAPIView.as_view(), name='api_job_list_create'),
    path('api/jobs/<int:pk>/', ProcessingJobDetailAPIView.as_view(), name='api_job_detail'),
    path('api/jobs/<int:pk>/cancel/', ProcessingJobCancelAPIView.as_view(), name='api_job_cancel'),
    path('api/jobs/<int:pk>/retry/', ProcessingJobRetryAPIView.as_view(), name='api_job_retry'),

    # Generated Clips
    path('api/clips/', GeneratedClipListAPIView.as_view(), name='api_clip_list'),
    path('api/clips/<int:pk>/', GeneratedClipDetailAPIView.as_view(), name='api_clip_detail'),
    path('api/clips/<int:pk>/download/', GeneratedClipDownloadAPIView.as_view(), name='api_clip_download'),

    # Audit Events
    path('api/audit/', AuditEventListAPIView.as_view(), name='api_audit_list'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
