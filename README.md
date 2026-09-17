# Toolyt - YouTube Long Video to Shorts Converter

A rights-respecting video repurposing platform built with **Python, Django 5, Celery, and FFmpeg** for creators who want to transform their long-form videos into high-converting **9:16 vertical shorts**.

---

## 🎯 Compliance & Ethics

> **Important compliance notice:** Transformative editing does not automatically grant permission to use copyrighted material. Verify ownership, licensing, and platform rules before publishing.
>
> This platform does not claim that editing makes copyrighted material safe to reuse and does **not** include mechanisms designed to evade YouTube Content ID or platform copyright detection systems. Every submission requires mandatory rights confirmation.

---

## 🚀 Key Features

- **Vertical 9:16 Framing (1080x1920)**:
  - **Center Crop**: Scales and crops video to fill the vertical canvas.
  - **Blurred Background**: Fits the source video in the center while dynamically blurring the margins.
  - **Fit (Letterbox/Pillarbox)**: Maintains original aspect ratio padded with neutral backgrounds.
- **Configurable Shorts Durations**: Presets for 15s, 30s, 45s, 60s, and 90s, with sub-second start/end clipping controls.
- **Automated Subtitles & Captions**: Timestamped speech-to-text generation with Advanced SubStation Alpha (`.ass`) rendering (Classic, Bold Viral Yellow, Subtitle Box).
- **Branding & Watermarks**: Dynamic channel handle or watermark burn-in.
- **Asynchronous Task Queue**: Celery & Redis pipeline with real-time browser progress polling and status updates.
- **Security & Integrity**:
  - Subprocess argument arrays prevent shell injection.
  - FFprobe media inspection detects corrupt files and validates codecs.
  - Per-user storage quotas and complete file purging upon deletion.
  - Comprehensive immutable audit logging.
- **Full REST API**: Token and session-authenticated endpoints matching Section 9 of the specification.

---

## 🛠 Tech Stack

- **Backend**: Python 3.11+, Django 5.1+, Django REST Framework, Celery 5.6+, Redis
- **Media Engine**: FFmpeg, FFprobe (safe subprocess execution)
- **Frontend**: Django Templates, Tailwind CSS, Lucide Icons, Vanilla JS Polling
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **Containerization**: Docker & Docker Compose

---

## 📦 Quickstart Guide

### 1. Local Development Setup

```bash
# 1. Clone or navigate to the workspace
cd /home/umair/Downloads/Toolyt

# 2. Activate virtual environment
source venv/bin/activate

# 3. Apply database migrations
python manage.py migrate

# 4. Create an admin superuser
python manage.py createsuperuser

# 5. Run development server
python manage.py runserver 8000
```

Visit `http://localhost:8000/` in your browser.

### 2. Running with Docker Compose (Production)

```bash
docker compose up --build
```

---

## 🧪 Running Tests

Execute the full automated test suite with pytest:

```bash
pytest -v
```

All 24 unit, integration, and security tests verify:
- File extension, size, and MIME validation
- Path traversal and shell injection sanitization
- Mandatory rights confirmation enforcement
- FFmpeg 9:16 vertical encoding and filter generation
- Video probe metadata extraction and corrupt input rejection
- Asynchronous Celery task execution end-to-end
- REST API authentication and multi-user isolation

---

## 📡 REST API Reference

### Authentication
- `POST /api/auth/register/` - Register account
- `POST /api/auth/login/` - Authenticate user
- `POST /api/auth/logout/` - End session
- `GET /api/auth/profile/` - Current user profile & quota

### Video Sources
- `GET /api/videos/` - List user's videos
- `POST /api/videos/upload/` - Upload video file (multipart)
- `POST /api/videos/import-url/` - Import video from authorized URL
- `GET /api/videos/<id>/` - Retrieve video details & metadata
- `DELETE /api/videos/<id>/` - Delete video and clean disk storage

### Processing Jobs
- `POST /api/jobs/` - Create a conversion job
- `GET /api/jobs/` - List user's conversion jobs
- `GET /api/jobs/<id>/` - Job progress & status
- `POST /api/jobs/<id>/cancel/` - Cancel in-flight job
- `POST /api/jobs/<id>/retry/` - Retry failed job

### Generated Clips
- `GET /api/clips/` - List generated 9:16 clips
- `GET /api/clips/<id>/` - Clip details & thumbnail
- `GET /api/clips/<id>/download/` - Authenticated MP4 download
- `DELETE /api/clips/<id>/` - Delete clip and media files

### Audit
- `GET /api/audit/` - List user's compliance audit log
