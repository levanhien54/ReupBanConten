"""Heuristic highlight analyzer for combat sports.

This module is intentionally lightweight. It can rank transcript-only moments in
tests and small workflows, and it opportunistically adds audio/video signals when
librosa or OpenCV are available.
"""
from __future__ import annotations

import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from src.core.config import CombatSportsHighlightConfig
from src.core.logging import get_logger
from src.core.types import CombatHighlight, CombatSignal, TranscriptResult

logger = get_logger(__name__)


KEYWORD_GROUPS: dict[str, tuple[float, tuple[str, ...]]] = {
    "impact": (
        1.0,
        (
            "knockout",
            "ko",
            "knock-out",
            "knockdown",
            "knocked down",
            "down goes",
            "big shot",
            "huge shot",
            "clean shot",
            "left hook",
            "right hand",
            "head kick",
            "body shot",
            "slam",
            "dropped",
            "hurt badly",
            "guc",
            "ha knock",
            "ha guc",
            "dam trung",
            "cu dam",
            "da trung",
            "don chan",
        ),
    ),
    "submission": (
        0.92,
        (
            "submission",
            "tap",
            "tapout",
            "choke",
            "rear naked",
            "armbar",
            "triangle",
            "guillotine",
            "kimura",
            "heel hook",
            "khoa siet",
            "siet co",
            "bop co",
            "khoa tay",
            "xin thua",
        ),
    ),
    "scramble": (
        0.78,
        (
            "takedown",
            "scramble",
            "reversal",
            "ground and pound",
            "mount",
            "back take",
            "double leg",
            "single leg",
            "vat nga",
            "dap san",
            "quang nga",
            "vat",
            "be khoa",
        ),
    ),
    "reaction": (
        0.70,
        (
            "crowd erupts",
            "listen to the crowd",
            "unbelievable",
            "what a finish",
            "he is hurt",
            "she is hurt",
            "referee stops",
            "stop the fight",
            "khong tin noi",
            "qua hay",
            "qua manh",
            "trong tai dung",
            "dung tran dau",
        ),
    ),
    "replay_or_slowmo": (
        0.55,
        (
            "replay",
            "slow motion",
            "slow-mo",
            "look again",
            "xem lai",
            "quay cham",
            "pha quay cham",
        ),
    ),
}


@dataclass(frozen=True)
class SignalWindow:
    center: float
    signals: list[CombatSignal]


class CombatSportsAnalyzer:
    """Rank short highlight candidates for combat-sports footage."""

    def __init__(self, config: Optional[CombatSportsHighlightConfig] = None) -> None:
        self._config = config or CombatSportsHighlightConfig()

    def analyze(
        self,
        video_path: Optional[str] = None,
        transcript: Optional[TranscriptResult] = None,
        *,
        top_k: int = 20,
    ) -> list[CombatHighlight]:
        """Collect available signals and return ranked highlight candidates."""
        signals: list[CombatSignal] = []
        if transcript:
            signals.extend(self.score_transcript(transcript))
        if video_path:
            signals.extend(self.score_audio(video_path))
            signals.extend(self.score_motion(video_path))

        return self.rank_signals(signals, top_k=top_k)

    def score_transcript(self, transcript: TranscriptResult) -> list[CombatSignal]:
        """Score transcript segments using combat-sports keyword groups."""
        signals: list[CombatSignal] = []
        for segment in transcript.segments:
            normalized = _normalize(segment.text)
            matches: list[tuple[str, float, str]] = []
            for kind, (base_score, keywords) in KEYWORD_GROUPS.items():
                matched = _find_keyword(normalized, keywords)
                if matched:
                    matches.append((kind, base_score, matched))

            if not matches:
                continue

            kind, base_score, matched_keyword = max(matches, key=lambda item: item[1])
            density_bonus = min(0.18, 0.04 * (len(matches) - 1))
            score = _clamp(base_score + density_bonus)
            signals.append(
                CombatSignal(
                    time=(segment.start + segment.end) / 2,
                    start_time=segment.start,
                    end_time=segment.end,
                    score=score,
                    kind=kind,
                    reason=f"keyword:{matched_keyword}",
                )
            )

        return signals

    def score_audio(self, video_path: str) -> list[CombatSignal]:
        """Detect loud audio bursts. Returns no signals when librosa cannot load."""
        if not os.path.exists(video_path):
            return []

        try:
            import librosa
            import numpy as np
        except ImportError:
            logger.debug("librosa/numpy unavailable; skipping combat audio scoring")
            return []

        try:
            y, sr = librosa.load(video_path, sr=16000, mono=True)
            if y.size == 0:
                return []
            hop_length = 512
            rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
            if rms.size < 4:
                return []

            threshold = float(np.percentile(rms, 92))
            peak = float(np.max(rms)) or 1.0
            times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)
            signals = []
            last_time = -999.0
            for t, value in zip(times, rms):
                if value < threshold or t - last_time < 0.75:
                    continue
                score = _clamp(float(value / peak))
                signals.append(
                    CombatSignal(
                        time=float(t),
                        score=score,
                        kind="crowd_audio",
                        reason="audio_spike",
                    )
                )
                last_time = float(t)
            return signals
        except Exception as e:
            logger.debug(f"Combat audio scoring skipped: {e}")
            return []

    def score_motion(self, video_path: str) -> list[CombatSignal]:
        """Detect sudden frame-difference bursts with OpenCV."""
        if not os.path.exists(video_path):
            return []

        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.debug("cv2/numpy unavailable; skipping combat motion scoring")
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        sample_every = max(1, int(fps // 6))
        diffs: list[tuple[float, float]] = []
        prev_gray = None
        frame_index = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_index % sample_every != 0:
                    frame_index += 1
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (160, 90))
                if prev_gray is not None:
                    diff = float(np.mean(cv2.absdiff(gray, prev_gray)))
                    diffs.append((frame_index / fps, diff))
                prev_gray = gray
                frame_index += 1
        finally:
            cap.release()

        if len(diffs) < 4:
            return []

        values = [d for _, d in diffs]
        threshold = _percentile(values, 88)
        peak = max(values) or 1.0
        signals = []
        last_time = -999.0
        for t, diff in diffs:
            if diff < threshold or t - last_time < 0.75:
                continue
            signals.append(
                CombatSignal(
                    time=t,
                    score=_clamp(diff / peak),
                    kind="motion",
                    reason="motion_burst",
                )
            )
            last_time = t
        return signals

    def rank_signals(
        self,
        signals: Iterable[CombatSignal],
        *,
        top_k: int = 20,
        merge_tolerance: float = 1.5,
    ) -> list[CombatHighlight]:
        """Merge nearby signals and compute final highlight windows."""
        sorted_signals = sorted(signals, key=lambda s: s.time)
        windows: list[SignalWindow] = []
        current: list[CombatSignal] = []

        for signal in sorted_signals:
            if not current:
                current = [signal]
                continue
            current_center = sum(s.time for s in current) / len(current)
            if abs(signal.time - current_center) <= merge_tolerance:
                current.append(signal)
            else:
                windows.append(SignalWindow(current_center, current))
                current = [signal]
        if current:
            center = sum(s.time for s in current) / len(current)
            windows.append(SignalWindow(center, current))

        highlights = [self._build_highlight(window) for window in windows]
        highlights = [
            h for h in highlights
            if h.score >= self._config.min_highlight_score
        ]
        highlights.sort(key=lambda h: h.score, reverse=True)
        return highlights[:top_k]

    def _build_highlight(self, window: SignalWindow) -> CombatHighlight:
        weighted_total = 0.0
        weight_seen = 0.0
        reasons = []
        for signal in window.signals:
            weight = self._config.weights.get(signal.kind, 0.12)
            weighted_total += signal.score * weight
            weight_seen += weight
            if signal.reason:
                reasons.append(f"{signal.kind}:{signal.reason}")

        diversity_bonus = min(0.18, 0.05 * (len({s.kind for s in window.signals}) - 1))
        raw_score = (weighted_total / max(weight_seen, 0.001)) + diversity_bonus
        score = _clamp(raw_score)

        hook_time = min(s.time for s in window.signals)
        start = max(0.0, hook_time - self._config.pre_action_padding)
        end = max(
            start + self._config.target_clip_duration,
            max(s.time for s in window.signals) + self._config.post_action_padding,
        )

        return CombatHighlight(
            start_time=round(start, 3),
            end_time=round(end, 3),
            hook_time=round(hook_time, 3),
            score=round(score, 3),
            reasons=sorted(set(reasons)),
            signals=window.signals,
        )


def _normalize(text: str) -> str:
    text = text.lower()
    replacements = {
        "đ": "d",
        "á": "a", "à": "a", "ả": "a", "ã": "a", "ạ": "a",
        "ă": "a", "ắ": "a", "ằ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
        "â": "a", "ấ": "a", "ầ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "é": "e", "è": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
        "ê": "e", "ế": "e", "ề": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "í": "i", "ì": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
        "ó": "o", "ò": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "ô": "o", "ố": "o", "ồ": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
        "ơ": "o", "ớ": "o", "ờ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
        "ú": "u", "ù": "u", "ủ": "u", "ũ": "u", "ụ": "u",
        "ư": "u", "ứ": "u", "ừ": "u", "ử": "u", "ữ": "u", "ự": "u",
        "ý": "y", "ỳ": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text)


def _find_keyword(text: str, keywords: Iterable[str]) -> Optional[str]:
    for keyword in keywords:
        normalized_keyword = _normalize(keyword)
        if re.search(rf"(^|\W){re.escape(normalized_keyword)}($|\W)", text):
            return normalized_keyword
    return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if math.isnan(value):
        return low
    return max(low, min(high, value))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((percentile / 100.0) * (len(ordered) - 1)))
    return ordered[index]

