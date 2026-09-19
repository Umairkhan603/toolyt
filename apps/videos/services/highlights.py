import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class HighlightDetectorService:
    """
    Intelligently analyzes video metadata (YouTube heatmap, chapter markers, duration)
    to identify the most informative and engaging segments for Short generation.
    Always respects the requested clip_duration unless the video itself is shorter.
    """

    @classmethod
    def detect_highlights(
        cls,
        video_info: Dict[str, Any],
        clip_duration: float = 30.0,
        clip_count: int = 5
    ) -> List[Dict[str, Any]]:
        total_duration = float(video_info.get('duration') or 0.0)
        requested_duration = max(1.0, float(clip_duration))
        if total_duration <= 0:
            total_duration = max(300.0, requested_duration)  # Fallback

        clip_count = max(1, min(15, clip_count))
        # The target duration is the requested duration, capped only by the total video length
        target_duration = min(requested_duration, total_duration)

        # If the video is shorter than or equal to the requested duration, return the full video
        if total_duration <= requested_duration:
            return [{
                'index': 1,
                'title': video_info.get('title', 'Highlight #1'),
                'start_time': 0.0,
                'end_time': round(total_duration, 2),
                'duration': round(total_duration, 2),
                'reason': 'full_video'
            }]

        heatmap = video_info.get('heatmap') or []
        chapters = video_info.get('chapters') or []

        # Strategy 1: Heatmap Peaks (Most Replayed Moments)
        if heatmap and len(heatmap) >= clip_count:
            highlights = cls._detect_from_heatmap(heatmap, total_duration, target_duration, clip_count)
            if len(highlights) >= clip_count:
                return highlights

        # Strategy 2: Chapter Markers (Informative Topics)
        if chapters and len(chapters) >= 2:
            highlights = cls._detect_from_chapters(chapters, total_duration, target_duration, clip_count)
            if len(highlights) >= clip_count:
                return highlights

        # Strategy 3: Distributed Informative Segments (Paced evenly through the video)
        return cls._detect_distributed(total_duration, target_duration, clip_count, video_info.get('title', 'Highlight'))

    @classmethod
    def _detect_from_heatmap(
        cls,
        heatmap: List[Dict[str, Any]],
        total_duration: float,
        target_duration: float,
        clip_count: int
    ) -> List[Dict[str, Any]]:
        # Sort heatmap points by engagement value descending
        valid_points = [
            p for p in heatmap
            if isinstance(p.get('start_time'), (int, float)) and isinstance(p.get('value'), (int, float))
        ]
        if not valid_points:
            return []

        sorted_points = sorted(valid_points, key=lambda x: x.get('value', 0.0), reverse=True)

        max_start = max(0.0, total_duration - target_duration)
        min_distance = max(5.0, min(30.0, max_start / max(1, clip_count)))
        chosen_times = []
        highlights = []

        for pt in sorted_points:
            cand_start = float(pt.get('start_time', 0.0))
            cand_start = max(0.0, min(cand_start, max_start))

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
                'end_time': round(cand_start + target_duration, 2),
                'duration': round(target_duration, 2),
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
        target_duration: float,
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

        max_start = max(0.0, total_duration - target_duration)
        highlights = []
        for i, ch in enumerate(selected_chapters, 1):
            ch_start = float(ch.get('start_time', 0.0))
            ch_end = float(ch.get('end_time', total_duration))
            ch_dur = max(0.0, ch_end - ch_start)

            offset = min(15.0, ch_dur * 0.15) if ch_dur > (target_duration + 15.0) else 0.0
            clip_start = max(0.0, min(ch_start + offset, max_start))

            ch_title = ch.get('title', f"Highlight #{i}")
            highlights.append({
                'index': i,
                'title': f"Topic: {ch_title}",
                'start_time': round(clip_start, 2),
                'end_time': round(clip_start + target_duration, 2),
                'duration': round(target_duration, 2),
                'reason': 'chapter_topic'
            })

        return highlights

    @classmethod
    def _detect_distributed(
        cls,
        total_duration: float,
        target_duration: float,
        clip_count: int,
        base_title: str
    ) -> List[Dict[str, Any]]:
        highlights = []
        max_start = max(0.0, total_duration - target_duration)

        if clip_count <= 1 or max_start <= 0.0:
            return [{
                'index': 1,
                'title': "Key Highlight #1",
                'start_time': 0.0,
                'end_time': round(target_duration, 2),
                'duration': round(target_duration, 2),
                'reason': 'single_highlight'
            }]

        # Distribute clip start times evenly across [0, max_start]
        # Every clip will have the exact target_duration (e.g. 90s)
        for i in range(clip_count):
            cand_start = (i / (clip_count - 1)) * max_start
            highlights.append({
                'index': i + 1,
                'title': f"Key Highlight #{i + 1}",
                'start_time': round(cand_start, 2),
                'end_time': round(cand_start + target_duration, 2),
                'duration': round(target_duration, 2),
                'reason': 'paced_distribution'
            })

        return highlights
