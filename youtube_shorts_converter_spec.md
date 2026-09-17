# YouTube Long Video to Shorts Converter --- Django Specification

## 1. Project Overview

Build a web-based tool using **Python + Django** that allows users to
upload or provide authorized video sources, convert long-form videos
into short vertical clips, and apply professional editing features.

> **Important compliance requirement:** The tool must not be designed to
> evade YouTube Content ID, copyright detection, or platform
> enforcement. It should support content that the user owns, has
> permission to use, or is licensed to transform. Add clear
> rights-confirmation and responsible-use controls.

The application should be designed for development through
**Antigravity** and should use a modular, production-ready architecture.

------------------------------------------------------------------------

## 2. Main Objectives

The tool should:

1.  Accept a user-uploaded video or an authorized source URL.
2.  Download/import video only when the user has the necessary rights
    and the source permits it.
3.  Convert long videos into short clips.
4.  Support configurable clip durations:
    -   15 seconds
    -   30 seconds
    -   45 seconds
    -   60 seconds
    -   90 seconds
5.  Convert landscape videos into vertical **9:16** format.
6.  Detect interesting segments using transcript, scene changes, audio
    peaks, or user-selected timestamps.
7.  Add captions/subtitles automatically.
8.  Provide editing features such as:
    -   Smart cropping
    -   Face/person tracking where technically feasible
    -   Intro/outro
    -   Background music supplied by the user or licensed sources
    -   Watermark/logo
    -   Text overlays
    -   Progress bars
    -   Color adjustments
9.  Export videos in a YouTube Shorts-friendly format.
10. Provide a download link for the processed result.
11. Maintain job history and processing status.
12. Include safeguards against copyright abuse.

------------------------------------------------------------------------

## 3. Recommended Technology Stack

### Backend

-   Python 3.12+
-   Django 5+
-   Django REST Framework
-   Celery for background jobs
-   Redis as message broker and cache
-   PostgreSQL for production
-   SQLite for local development

### Video Processing

-   FFmpeg
-   FFprobe
-   MoviePy or direct FFmpeg pipelines
-   OpenCV for video analysis
-   Whisper or another speech-to-text engine for captions
-   Optional: MediaPipe or another tracking solution

### Frontend

-   Django Templates + HTMX for a simple MVP, or
-   React/Next.js for a richer interface
-   Tailwind CSS
-   Upload progress indicators
-   Job status polling or WebSockets

### Deployment

-   Docker and Docker Compose
-   Nginx
-   Gunicorn
-   Celery worker
-   Redis
-   PostgreSQL
-   Object storage such as S3-compatible storage for production

------------------------------------------------------------------------

## 4. Core User Workflow

### Step 1: User Authentication

Users should be able to:

-   Register
-   Log in
-   Log out
-   Reset password
-   View their previous processing jobs

### Step 2: Rights Confirmation

Before processing a source, show a mandatory checkbox:

> "I confirm that I own this content or have the necessary
> permission/license to download, edit, and publish it."

The user must accept this confirmation before continuing.

### Step 3: Source Selection

Support:

-   Direct upload
-   Authorized URL import
-   Optional integration with an approved cloud storage provider

For URL imports:

-   Validate the URL
-   Check whether the source is supported
-   Avoid bypassing access controls, DRM, or platform restrictions
-   Display terms-of-use and rights warnings

### Step 4: Processing Configuration

Allow the user to select:

-   Clip duration
-   Number of clips
-   Aspect ratio
-   Caption style
-   Crop mode
-   Output resolution
-   Audio settings
-   Intro/outro
-   Watermark
-   Export format

### Step 5: Clip Generation

The system should:

1.  Validate the source.
2.  Store the original file temporarily.
3.  Extract metadata with FFprobe.
4.  Generate a transcript if captions or semantic selection is enabled.
5.  Detect candidate segments.
6.  Create clips.
7.  Apply vertical framing.
8.  Add captions and overlays.
9.  Encode the final video.
10. Run output validation.
11. Store the result.
12. Notify the user.

### Step 6: Result Page

Display:

-   Video preview
-   Clip duration
-   Resolution
-   File size
-   Processing time
-   Download button
-   Delete button
-   Optional regeneration button

------------------------------------------------------------------------

## 5. Suggested Django App Structure

``` text
shorts_converter/
├── manage.py
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
├── apps/
│   ├── accounts/
│   ├── videos/
│   ├── processing/
│   ├── captions/
│   ├── exports/
│   └── audit/
├── media/
├── static/
├── templates/
├── requirements/
├── Dockerfile
├── docker-compose.yml
└── README.md
```

------------------------------------------------------------------------

## 6. Database Models

### User

Use Django's built-in user model, optionally extended with a profile.

Suggested fields:

-   `user`
-   `storage_quota`
-   `created_at`

### VideoSource

Fields:

-   `user`
-   `source_type` --- upload or authorized URL
-   `original_file`
-   `source_url`
-   `title`
-   `duration`
-   `width`
-   `height`
-   `file_size`
-   `rights_confirmed`
-   `status`
-   `created_at`

Suggested statuses:

-   `pending`
-   `validating`
-   `ready`
-   `processing`
-   `completed`
-   `failed`
-   `deleted`

### ProcessingJob

Fields:

-   `user`
-   `video_source`
-   `clip_duration`
-   `clip_count`
-   `aspect_ratio`
-   `caption_enabled`
-   `caption_style`
-   `crop_mode`
-   `watermark_enabled`
-   `status`
-   `progress`
-   `error_message`
-   `started_at`
-   `completed_at`
-   `created_at`

### GeneratedClip

Fields:

-   `job`
-   `start_time`
-   `end_time`
-   `output_file`
-   `thumbnail`
-   `duration`
-   `width`
-   `height`
-   `file_size`
-   `status`
-   `created_at`

### AuditEvent

Fields:

-   `user`
-   `event_type`
-   `ip_address`
-   `metadata`
-   `created_at`

Do not store unnecessary personal information.

------------------------------------------------------------------------

## 7. Video Processing Pipeline

### 7.1 Input Validation

Validate:

-   File extension
-   MIME type
-   File size
-   Video duration
-   Audio/video streams
-   Resolution
-   Corrupt media
-   Unsafe filenames

Use FFprobe to inspect the media rather than trusting file extensions.

### 7.2 Segment Selection

Provide two modes:

#### Manual Mode

The user selects:

-   Start timestamp
-   End timestamp
-   Number of clips

#### Assisted Mode

Use transcript and video signals to identify candidate clips based on:

-   Complete sentences
-   Topic changes
-   High speech energy
-   Scene changes
-   Keyword matches
-   User-defined keywords

The assisted mode should present suggested clips for user approval
instead of automatically publishing them.

### 7.3 Vertical Conversion

Default output:

-   Aspect ratio: `9:16`
-   Resolution: `1080x1920`
-   Codec: H.264
-   Audio codec: AAC
-   Frame rate: source frame rate or a configurable standard
-   Pixel format: `yuv420p`

Crop modes:

1.  Center crop
2.  Blur background
3.  Fit with background
4.  Subject-aware crop
5.  Manual crop

The system should avoid excessive cropping of faces or important visual
content.

### 7.4 Captions

Caption workflow:

1.  Extract audio.
2.  Run speech-to-text.
3.  Generate timestamped captions.
4.  Break captions into readable lines.
5.  Render captions using FFmpeg.
6.  Allow style customization.

Caption options:

-   Font size
-   Position
-   Background box
-   Highlighted words
-   Maximum words per line
-   Color and opacity

Only use fonts that are properly licensed.

### 7.5 Audio

Support:

-   Original audio
-   User-provided licensed music
-   Volume adjustment
-   Fade in/out
-   Audio normalization
-   Optional noise reduction

Do not include copyrighted music unless the user has the required rights
or license.

------------------------------------------------------------------------

## 8. Copyright and Responsible-Use Safeguards

The product must not claim that editing makes copyrighted content safe
to reuse.

Implement:

-   Mandatory rights confirmation
-   Terms-of-use page
-   Content ownership warning
-   User reporting process
-   Copyright complaint workflow
-   Audit logs
-   Rate limits
-   File retention limits
-   Ability to delete uploaded and generated files
-   No functionality intended to defeat Content ID or copyright
    enforcement
-   No artificial claims that cropping, mirroring, changing speed,
    adding borders, or changing audio prevents claims
-   Optional similarity/originality review that provides warnings, not
    guarantees

The UI should clearly state:

> "Transformative editing does not automatically grant permission to use
> copyrighted material. Verify ownership, licensing, and platform rules
> before publishing."

------------------------------------------------------------------------

## 9. REST API Endpoints

### Authentication

``` text
POST /api/auth/register/
POST /api/auth/login/
POST /api/auth/logout/
```

### Video Sources

``` text
GET    /api/videos/
POST   /api/videos/upload/
POST   /api/videos/import-url/
GET    /api/videos/<id>/
DELETE /api/videos/<id>/
```

### Processing Jobs

``` text
POST /api/jobs/
GET  /api/jobs/
GET  /api/jobs/<id>/
POST /api/jobs/<id>/cancel/
POST /api/jobs/<id>/retry/
```

### Generated Clips

``` text
GET    /api/clips/
GET    /api/clips/<id>/
GET    /api/clips/<id>/download/
DELETE /api/clips/<id>/
```

Use authentication and object-level permissions on every endpoint.

------------------------------------------------------------------------

## 10. Background Processing

Video processing must not run inside a normal Django request.

Use:

-   Celery task queue
-   Redis broker
-   Separate worker process
-   Job progress tracking
-   Retry logic
-   Timeouts
-   Temporary directory cleanup

Suggested tasks:

``` text
validate_source_task
extract_metadata_task
generate_transcript_task
detect_segments_task
render_clip_task
generate_thumbnail_task
validate_output_task
cleanup_temp_files_task
```

Each task should:

-   Be idempotent where possible
-   Log errors safely
-   Update job progress
-   Avoid exposing internal paths to users
-   Clean up temporary resources

------------------------------------------------------------------------

## 11. FFmpeg Export Requirements

Example output command concept:

``` bash
ffmpeg -i input.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -c:v libx264 \
  -preset medium \
  -crf 20 \
  -c:a aac \
  -b:a 128k \
  -pix_fmt yuv420p \
  -movflags +faststart \
  output.mp4
```

The implementation should dynamically construct commands using safe
argument lists, not unsafe shell string concatenation.

For user-supplied filenames and paths:

-   Use subprocess argument arrays
-   Never execute user input as shell code
-   Validate all paths
-   Use isolated temporary directories

------------------------------------------------------------------------

## 12. Security Requirements

Implement:

-   CSRF protection
-   Authentication
-   Authorization
-   Upload size limits
-   MIME and codec validation
-   Virus/malware scanning where available
-   Rate limiting
-   Secure media URLs
-   Signed download URLs for production
-   Storage cleanup
-   Secrets through environment variables
-   No debug mode in production
-   Secure headers
-   Protection against path traversal
-   Protection against command injection
-   Logging without sensitive data

------------------------------------------------------------------------

## 13. UI Pages

### Public Pages

-   Home
-   Features
-   Pricing, if applicable
-   Terms of Use
-   Privacy Policy
-   Copyright Policy

### Authenticated Pages

-   Dashboard
-   Upload/Import page
-   Editing settings page
-   Processing progress page
-   Generated clips gallery
-   Clip preview/editor
-   Account settings

### Dashboard Components

-   Upload button
-   Recent jobs
-   Processing progress
-   Storage usage
-   Error notifications
-   Delete controls

------------------------------------------------------------------------

## 14. MVP Scope

Build the MVP in this order:

### Phase 1

-   Django project setup
-   User authentication
-   Video upload
-   FFprobe metadata extraction
-   Manual start/end clip selection
-   FFmpeg clip generation
-   9:16 export
-   Download generated clip

### Phase 2

-   Celery + Redis
-   Job progress tracking
-   Captions using speech-to-text
-   Thumbnail generation
-   Clip history
-   Storage cleanup

### Phase 3

-   Assisted segment detection
-   Smart cropping
-   Caption customization
-   Watermarks
-   Intro/outro
-   Better error handling

### Phase 4

-   Production deployment
-   Object storage
-   Monitoring
-   Usage quotas
-   Billing, if required
-   Review and abuse reporting tools

------------------------------------------------------------------------

## 15. Antigravity Development Instructions

Use Antigravity to implement the project incrementally.

### General Rules

-   Write clean, modular, documented Python code.
-   Follow Django best practices.
-   Use type hints where practical.
-   Add unit and integration tests.
-   Keep business logic outside views where possible.
-   Use service classes for video processing.
-   Keep FFmpeg operations isolated in a dedicated module.
-   Use environment variables for configuration.
-   Never hardcode API keys or secrets.
-   Provide migration files.
-   Add a clear README.
-   Use Docker for consistent development.

### Suggested Implementation Prompts

#### Prompt 1: Project Setup

> Create a Django 5 project named `shorts_converter` with
> PostgreSQL-ready settings, environment variable support, Docker
> configuration, Django REST Framework, Celery, and Redis. Separate
> development and production settings.

#### Prompt 2: Upload System

> Implement secure video upload with MIME validation, file-size limits,
> FFprobe metadata extraction, rights confirmation, and a VideoSource
> model. Add tests for invalid files and unauthorized access.

#### Prompt 3: Processing System

> Implement a Celery-based processing pipeline for manually selected
> timestamps. Use FFmpeg through safe subprocess argument arrays. Track
> progress and errors in a ProcessingJob model.

#### Prompt 4: Vertical Export

> Add a service that converts clips into 1080x1920 9:16 videos. Support
> center crop, blurred background, and fit modes. Validate output
> metadata after encoding.

#### Prompt 5: Captions

> Add optional speech-to-text caption generation with timestamped
> segments and configurable caption styles. Keep caption processing
> asynchronous and provide graceful failure handling.

#### Prompt 6: Dashboard

> Build a responsive dashboard showing uploads, jobs, progress,
> previews, downloads, and deletion controls. Use authenticated API
> endpoints and object-level permissions.

#### Prompt 7: Compliance

> Add rights confirmation, terms links, copyright warnings, audit
> events, abuse reporting, retention limits, and deletion workflows. Do
> not implement any Content ID evasion or copyright-detection bypass
> features.

------------------------------------------------------------------------

## 16. Testing Strategy

### Unit Tests

Test:

-   File validation
-   Rights confirmation
-   Permission checks
-   Timestamp validation
-   Clip duration calculation
-   FFmpeg command construction
-   Caption formatting
-   Filename sanitization

### Integration Tests

Test:

-   Upload-to-export workflow
-   Celery task execution
-   Failed processing recovery
-   Unauthorized file access
-   Deletion and cleanup
-   API authentication

### Security Tests

Test:

-   Path traversal
-   Command injection
-   Oversized uploads
-   Invalid MIME types
-   Missing rights confirmation
-   Cross-user resource access

------------------------------------------------------------------------

## 17. Acceptance Criteria

The project is considered MVP-ready when:

-   A registered user can upload a valid video.
-   The user must confirm rights before processing.
-   The system validates the media with FFprobe.
-   The user can select start and end timestamps.
-   The system generates a vertical 9:16 clip.
-   The result is encoded as MP4 with H.264/AAC.
-   The processing runs asynchronously.
-   The dashboard shows progress and errors.
-   The user can preview and download the result.
-   Unauthorized users cannot access another user's files.
-   Temporary files are cleaned up.
-   Tests cover the main security and processing workflows.
-   The UI does not promise copyright immunity or Content ID avoidance.

------------------------------------------------------------------------

## 18. Final Product Positioning

Position the application as:

> "A rights-respecting AI-assisted video repurposing platform for
> creators who want to turn their own or properly licensed long-form
> videos into engaging short-form content."

Avoid marketing claims such as:

-   "No copyright guaranteed"
-   "100% Content ID bypass"
-   "Copyright-proof editing"
-   "YouTube cannot detect this"

Instead, focus on:

-   Faster editing
-   Better vertical framing
-   Automatic captions
-   Creator-controlled clip selection
-   Licensed media workflows
-   Transparent compliance controls
