"""Evaluation utilities for combat-sports highlight workflows."""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Optional

from src.analyzer.combat_sports import CombatSportsAnalyzer
from src.core.config import AppConfig
from src.core.types import TranscriptResult


@dataclass
class ClipProbe:
    path: str
    exists: bool
    valid: bool
    duration: float = 0.0
    width: int = 0
    height: int = 0
    has_audio: bool = False
    size_bytes: int = 0
    error: str = ""


class CombatEvaluator:
    """Measure ranking speed and basic output validity for combat highlights."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def evaluate(
        self,
        *,
        input_path: str,
        transcript: Optional[TranscriptResult] = None,
        api_results: Optional[list[dict]] = None,
        output_dir: Optional[str] = None,
        top_k: int = 10,
        transcript_only: bool = False,
    ) -> dict:
        analyzer = CombatSportsAnalyzer(self._config.combat_sports)
        video_info = probe_video(input_path)

        started = time.perf_counter()
        highlights = analyzer.analyze(
            video_path=None if transcript_only else input_path,
            transcript=transcript,
            api_results=api_results,
            top_k=top_k,
        )
        ranking_seconds = time.perf_counter() - started

        clip_dir = output_dir or os.path.join(self._config.storage.clips, "combat")
        clips = probe_clip_directory(clip_dir)
        input_duration = max(video_info.duration, 0.001)

        valid_clips = [clip for clip in clips if clip.valid]
        report = {
            "input": asdict(video_info),
            "ranking": {
                "seconds": round(ranking_seconds, 3),
                "video_seconds_per_processing_second": round(input_duration / max(ranking_seconds, 0.001), 2),
                "highlight_count": len(highlights),
                "top_score": highlights[0].score if highlights else 0.0,
                "avg_score": round(sum(h.score for h in highlights) / len(highlights), 3) if highlights else 0.0,
                "signal_mix": _signal_mix(highlights),
            },
            "outputs": {
                "directory": clip_dir,
                "clip_count": len(clips),
                "valid_clip_count": len(valid_clips),
                "invalid_clip_count": len(clips) - len(valid_clips),
                "avg_clip_duration": round(sum(c.duration for c in valid_clips) / len(valid_clips), 3)
                if valid_clips else 0.0,
                "clips": [asdict(clip) for clip in clips],
            },
            "quality_estimate": estimate_quality(highlights, clips),
        }
        return report


def write_report(report: dict, report_path: str) -> None:
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def probe_clip_directory(directory: str) -> list[ClipProbe]:
    if not os.path.isdir(directory):
        return []
    clips = []
    for name in sorted(os.listdir(directory)):
        if not name.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
            continue
        clips.append(probe_video(os.path.join(directory, name)))
    return clips


def probe_video(path: str) -> ClipProbe:
    if not os.path.exists(path):
        return ClipProbe(path=path, exists=False, valid=False, error="file_not_found")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True, text=True)
        payload = json.loads(result.stdout or "{}")
    except FileNotFoundError:
        return ClipProbe(
            path=path,
            exists=True,
            valid=False,
            size_bytes=os.path.getsize(path),
            error="ffprobe_not_found",
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return ClipProbe(
            path=path,
            exists=True,
            valid=False,
            size_bytes=os.path.getsize(path),
            error=str(exc),
        )

    streams = payload.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float((payload.get("format") or {}).get("duration") or 0.0)
    valid = bool(video_stream) and duration > 0.0
    return ClipProbe(
        path=path,
        exists=True,
        valid=valid,
        duration=round(duration, 3),
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        has_audio=has_audio,
        size_bytes=os.path.getsize(path),
    )


def estimate_quality(highlights, clips: list[ClipProbe]) -> dict:
    valid_clips = [clip for clip in clips if clip.valid]
    output_validity = 5.0 if clips and len(valid_clips) == len(clips) else 0.0
    avg_score = sum(h.score for h in highlights) / len(highlights) if highlights else 0.0
    hook_strength = min(5.0, round(avg_score * 5.0, 2))
    duplicate_control = 5.0
    if highlights:
        hook_times = sorted(round(h.hook_time, 1) for h in highlights)
        duplicates = sum(1 for idx, value in enumerate(hook_times[1:], start=1) if abs(value - hook_times[idx - 1]) < 2.0)
        duplicate_control = max(1.0, 5.0 - duplicates)
    return {
        "hook_strength_estimate": hook_strength,
        "output_validity": output_validity,
        "duplicate_control_estimate": duplicate_control,
        "needs_human_review": True,
        "note": "Automated score checks validity and signal strength; visual hook quality still needs review.",
    }


def _signal_mix(highlights) -> dict[str, int]:
    mix: dict[str, int] = {}
    for highlight in highlights:
        for signal in highlight.signals:
            mix[signal.kind] = mix.get(signal.kind, 0) + 1
    return dict(sorted(mix.items()))
