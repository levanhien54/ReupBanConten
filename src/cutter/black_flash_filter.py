"""
Black Frame & Flash Filter.
"""
from __future__ import annotations

import os

import cv2
import numpy as np

from src.core.config import BlackFlashFilterConfig
from src.core.logging import get_logger, log_duration
from src.core.types import SegmentQuality

logger = get_logger(__name__)


class BlackFlashFilter:
    def __init__(self, config: BlackFlashFilterConfig) -> None:
        self._config = config

    @log_duration(msg_template="Filter quality {func_name}")
    def check_segment(self, segment_path: str) -> SegmentQuality:
        if not os.path.exists(segment_path):
            return SegmentQuality(is_bad=True, reasons=["File not found"])

        cap = cv2.VideoCapture(segment_path)
        if not cap.isOpened():
            return SegmentQuality(is_bad=True, reasons=["Cannot open video"])

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if total_frames <= 0 or fps <= 0:
            return SegmentQuality(is_bad=True, reasons=["Invalid video properties"])

        duration = total_frames / fps
        if duration < self._config.min_segment_duration:
            return SegmentQuality(is_bad=True, reasons=["Too short"], duration=duration)

        black_frames = 0
        flash_count = 0
        prev_brightness = None
        brightness_list = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Grayscale for brightness
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            avg_b = float(np.mean(gray))
            brightness_list.append(avg_b)

            if avg_b < self._config.black_threshold:
                black_frames += 1

            if prev_brightness is None:
                prev_brightness = avg_b
                continue

            diff = abs(avg_b - prev_brightness)
            if diff > self._config.flash_threshold:
                flash_count += 1
            
            prev_brightness = avg_b

        cap.release()

        reasons = []
        is_bad = False

        actual_frames = len(brightness_list)
        if actual_frames == 0:
            return SegmentQuality(is_bad=True, reasons=["No frames read"])

        black_ratio = black_frames / actual_frames
        if black_ratio > self._config.black_ratio:
            reasons.append(f"Too much black ({black_ratio:.1%})")
            is_bad = True

        flash_rate = flash_count / duration
        if flash_rate > 2.0: # arbitrary threshold for epilepsy safety
            reasons.append("Too many flashes")
            is_bad = True

        return SegmentQuality(
            is_bad=is_bad,
            reasons=reasons,
            black_ratio=black_ratio,
            flash_rate=flash_rate,
            flash_count=flash_count,
            avg_brightness=float(np.mean(brightness_list)),
            brightness_std=float(np.std(brightness_list)),
            duration=duration,
        )
