"""Read combat pipeline output metadata for UI summaries."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CombatOutputSummary:
    json_path: str
    clip_path: str
    final_video_path: str
    score: float
    ready: bool
    width: int
    height: int
    has_audio: bool
    duration: float
    language: str
    start_time: float
    end_time: float
    hook_time: float
    commentary_text: str


def load_combat_output_summaries(output_dir: str) -> list[CombatOutputSummary]:
    if not os.path.isdir(output_dir):
        return []
    summaries = []
    for name in sorted(os.listdir(output_dir)):
        if not name.endswith(".commentary.json"):
            continue
        path = os.path.join(output_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        probe = payload.get("final_video_probe") or {}
        highlight = payload.get("highlight") or {}
        commentary = payload.get("commentary") or {}
        summaries.append(
            CombatOutputSummary(
                json_path=path,
                clip_path=str(payload.get("clip_path") or ""),
                final_video_path=payload.get("final_video_path") or "",
                score=float(highlight.get("score") or 0.0),
                ready=bool(payload.get("final_video_ready")),
                width=int(probe.get("width") or 0),
                height=int(probe.get("height") or 0),
                has_audio=bool(probe.get("has_audio")),
                duration=float(probe.get("duration") or 0.0),
                language=str(payload.get("language") or ""),
                start_time=float(highlight.get("start_time") or 0.0),
                end_time=float(highlight.get("end_time") or 0.0),
                hook_time=float(highlight.get("hook_time") or 0.0),
                commentary_text=str(commentary.get("text") or ""),
            )
        )
    return summaries


def _shorten(text: str, limit: int = 90) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def format_combat_output_summary(summaries: list[CombatOutputSummary]) -> str:
    if not summaries:
        return "No commentary JSON outputs found yet."

    ready = sum(1 for item in summaries if item.ready)
    lines = [f"Final videos ready: {ready}/{len(summaries)}", ""]
    for idx, item in enumerate(summaries, start=1):
        status = "READY" if item.ready else "CHECK"
        audio = "audio" if item.has_audio else "no-audio"
        final_name = os.path.basename(item.final_video_path) if item.final_video_path else "-"
        lines.append(
            f"{idx:02d}. {status} score={item.score:.2f} "
            f"{item.width}x{item.height} {audio} {item.duration:.2f}s "
            f"lang={item.language} hook={item.hook_time:.2f}s file={final_name}"
        )
        if item.commentary_text:
            lines.append(f"    commentary: {_shorten(item.commentary_text)}")
    return "\n".join(lines)
