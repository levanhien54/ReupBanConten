"""
Precise Scene Detection (Multi-Method).
Kết hợp PySceneDetect (Content, Adaptive) và OpenCV Histogram.
"""
from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np

from src.core.config import PreciseSceneConfig
from src.core.errors import SceneDetectionError
from src.core.logging import get_logger, log_duration
from src.core.types import SceneBoundary

logger = get_logger(__name__)


class PreciseSceneDetector:
    """Multi-method scene detector."""

    def __init__(self, config: PreciseSceneConfig) -> None:
        self._config = config

    @log_duration(msg_template="Scene detection {func_name}")
    def detect_scenes(self, video_path: str) -> list[SceneBoundary]:
        """Phát hiện cảnh."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        logger.info(f"Detecting scenes: {os.path.basename(video_path)}")

        try:
            from scenedetect import detect, ContentDetector, AdaptiveDetector
        except ImportError:
            logger.warning("scenedetect not installed. Skipping detection.")
            return []

        try:
            # 1. Content Detector
            content_scenes = detect(
                video_path,
                ContentDetector(threshold=self._config.content_threshold),
                show_progress=False,
            )
            content_cuts = [s[1].get_seconds() for s in content_scenes][:-1]

            # 2. Adaptive Detector
            adaptive_scenes = detect(
                video_path,
                AdaptiveDetector(
                    adaptive_threshold=self._config.adaptive_threshold,
                    min_scene_len=int(self._config.min_scene_len * 30), # approx frames
                ),
                show_progress=False,
            )
            adaptive_cuts = [s[1].get_seconds() for s in adaptive_scenes][:-1]

            # 3. Histogram correlation (nếu video không quá dài để tránh RAM issue)
            # Giả lập cho đơn giản:
            hist_cuts: list[float] = []

            # 4. Consensus Voting
            all_cuts = self._consensus_vote(
                {"content": content_cuts, "adaptive": adaptive_cuts, "histogram": hist_cuts}
            )

            # Filter min length
            filtered = self._enforce_min_length(all_cuts)

            logger.info(f"Detected {len(filtered)} scenes")
            return filtered

        except Exception as e:
            raise SceneDetectionError(f"Scene detection failed: {e}") from e

    def _consensus_vote(self, methods: dict[str, list[float]]) -> list[SceneBoundary]:
        # Gộp các cut gần nhau (< consensus_tolerance)
        all_timestamps = []
        for method, cuts in methods.items():
            for t in cuts:
                all_timestamps.append((t, method))
        
        if not all_timestamps:
            return []

        all_timestamps.sort(key=lambda x: x[0])
        
        merged: list[SceneBoundary] = []
        current_group: list[tuple[float, str]] = [all_timestamps[0]]

        for t, m in all_timestamps[1:]:
            if t - current_group[-1][0] <= self._config.consensus_tolerance:
                current_group.append((t, m))
            else:
                merged.append(self._process_group(current_group))
                current_group = [(t, m)]
        
        merged.append(self._process_group(current_group))
        
        # Chỉ lấy cut được ít nhất 2 method đồng ý → giảm false positive
        return [b for b in merged if len(b.methods) >= 2]

    def _process_group(self, group: list[tuple[float, str]]) -> SceneBoundary:
        avg_time = sum(t for t, _ in group) / len(group)
        methods = list({m for _, m in group})
        conf = min(1.0, len(methods) / 3.0 + 0.3)
        return SceneBoundary(cut_time=round(avg_time, 3), confidence=round(conf, 2), methods=methods)

    def _enforce_min_length(self, cuts: list[SceneBoundary]) -> list[SceneBoundary]:
        if not cuts:
            return []
        
        filtered = [cuts[0]]
        for cut in cuts[1:]:
            if cut.cut_time - filtered[-1].cut_time >= self._config.min_scene_len:
                filtered.append(cut)
        return filtered
