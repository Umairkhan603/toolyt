import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class HighlightDetectorService:
    """
    Intelligently analyzes video metadata (YouTube heatmap, chapter markers, duration)
    to identify the most informative and engaging segments for Short generation.
    """

    @classmethod
    def detect_highlights(
        cls,
        video_info: Dict[str, Any],
        clip_duration: float = 30.0,
        clip_count: int = 5
    ) -> List[Dict[str, Any]]:
        total_duration = float(video_info.get('duration') or 0.0)
        if total_duration <= 0:
            total_duration = 300.0  # Fallback 5 mins

        clip_count = max(1, min(15, clip_count))
        effective_clip_dur = max(0.5, min(90.0, clip_duration))

        # If video is shorter than clip duration and only 1 clip requested, return full video
        if total_duration <= effective_clip_dur and clip_count == 1:
            return [{
                'index': 1,
                'title': video_info.get('title', 'Highlight #1'),
                'start_time': 0.0,
                'end_time': total_duration,
                'duration': total_duration,
                'reason': 'full_video'
            }]

        heatmap = video_info.get('heatmap') or []
        chapters = video_info.get('chapters') or []

        # Strategy 1: Heatmap Peaks (Most Replayed Moments)
        if heatmap and len(heatmap) >= clip_count:
            highlights = cls._detect_from_heatmap(heatmap, total_duration, clip_duration, clip_count)
            if len(highlights) >= clip_count:
                return highlights

        # Strategy 2: Chapter Markers (Informative Topics)
        if chapters and len(chapters) >= 2:
            highlights = cls._detect_from_chapters(chapters, total_duration, clip_duration, clip_count)
            if len(highlights) >= clip_count:
                return highlights

        # Strategy 3: Distributed Informative Segments (Paced evenly through the video)
        return cls._detect_distributed(total_duration, clip_duration, clip_count, video_info.get('title', 'Highlight'))

    @classmethod
    def _detect_from_heatmap(
        cls,
        heatmap: List[Dict[str, Any]],
        total_duration: float,
        clip_duration: float,
        clip_count: int
    ) -> List[Dict[str, Any]]:
        # Sort heatmap points by engagement value descending
        valid_points = [
            p for p in heatmap
            if isinstance(p.get('start_time'), (int, float)) and isinstance(p.get('value'), (int, float))
        ]
        if not valid_points:
            return []

        # Exclude initial 10 seconds if score is just initial play artifact
        sorted_points = sorted(valid_points, key=lambda x: x.get('value', 0.0), reverse=True)

        min_distance = max(clip_duration * 1.5, total_duration / (clip_count * 2.5))
        chosen_times = []
        highlights = []

        for pt in sorted_points:
            cand_start = float(pt.get('start_time', 0.0))
            # Adjust if start is too close to the end
            if cand_start + clip_duration > total_duration:
                cand_start = max(0.0, total_duration - clip_duration)

            # Check distance from existing picks to ensure variety
            if any(abs(cand_start - chosen) < min_distance for chosen in chosen_times):
                continue

            chosen_times.append(cand_start)
            idx = len(highlights) + 1
            score = round(float(pt.get('value', 1.0)) * 100, 1)
            highlights.append({
                'index': idx,
                'title': f"Peak Moment #{idx} ({score}% Viewer Retention)",
                'start_time': round(cand_start, 2),
                'end_time': round(cand_start + clip_duration, 2),
                'duration': clip_duration,
                'reason': 'viewer_heatmap_peak',
                'score': score
            })

            if len(highlights) >= clip_count:
                break

        # Sort chronologically
        highlights.sort(key=lambda x: x['start_time'])
        for i, h in enumerate(highlights, 1):
            h['index'] = i

        return highlights

    @classmethod
    def _detect_from_chapters(
        cls,
        chapters: List[Dict[str, Any]],
        total_duration: float,
        clip_duration: float,
        clip_count: int
    ) -> List[Dict[str, Any]]:
        # Filter out generic or sponsor chapters
        skip_keywords = ['intro', 'outro', 'sponsor', 'subscribe', 'credits', 'advertisement']
        filtered = []
        for c in chapters:
            title = c.get('title', '').strip()
            if any(kw in title.lower() for kw in skip_keywords):
                continue
            filtered.append(c)

        pool = filtered if len(filtered) >= clip_count else chapters
        if not pool:
            return []

        # Select evenly spaced chapters from pool
        step = max(1, len(pool) // clip_count)
        selected_chapters = [pool[i] for i in range(0, len(pool), step)][:clip_count]

        highlights = []
        for i, ch in enumerate(selected_chapters, 1):
            ch_start = float(ch.get('start_time', 0.0))
            ch_end = float(ch.get('end_time', total_duration))
            ch_dur = max(0.0, ch_end - ch_start)

            # Start 10-20% into the chapter to catch the core point rather than transition words
            offset = min(15.0, ch_dur * 0.15) if ch_dur > (clip_duration + 15.0) else 0.0
            clip_start = ch_start + offset

            if clip_start + clip_duration > total_duration:
                clip_start = max(0.0, total_duration - clip_duration)

            ch_title = ch.get('title', f"Highlight #{i}")
            highlights.append({
                'index': i,
                'title': f"Topic: {ch_title}",
                'start_time': round(clip_start, 2),
                'end_time': round(clip_start + clip_duration, 2),
                'duration': clip_duration,
                'reason': 'chapter_topic'
            })

        return highlights

    @classmethod
    def _detect_distributed(
        cls,
        total_duration: float,
        clip_duration: float,
        clip_count: int,
        base_title: str
    ) -> List[Dict[str, Any]]:
        highlights = []
        if total_duration <= clip_duration * clip_count:
            step = total_duration / clip_count
            for i in range(clip_count):
                c_start = i * step
                c_dur = min(clip_duration, step)
                highlights.append({
                    'index': i + 1,
                    'title': f"Key Highlight #{i + 1}",
                    'start_time': round(c_start, 2),
                    'end_time': round(c_start + c_dur, 2),
                    'duration': round(c_dur, 2),
                    'reason': 'paced_distribution'
                })
            return highlights

        # Safe boundary margins (skip first 5% and last 5%)
        safe_start = total_duration * 0.05
        safe_end = max(safe_start + clip_duration, total_duration * 0.92 - clip_duration)
        span = safe_end - safe_start

        step = span / (clip_count + 1) if clip_count > 1 else span / 2

        for i in range(1, clip_count + 1):
            cand_start = safe_start + (i * step)
            if cand_start + clip_duration > total_duration:
                cand_start = max(0.0, total_duration - clip_duration)

            highlights.append({
                'index': i,
                'title': f"Key Highlight #{i}",
                'start_time': round(cand_start, 2),
                'end_time': round(cand_start + clip_duration, 2),
                'duration': clip_duration,
                'reason': 'paced_distribution'
            })

        return highlights
