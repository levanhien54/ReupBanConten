"""
Smart Clipper — Cắt video sử dụng FFmpeg.
"""
from __future__ import annotations

import os
import subprocess

from src.core.config import CutterConfig
from src.core.errors import ClipExportError
from src.core.logging import get_logger, log_duration
from src.core.types import Clip, SceneBoundary

logger = get_logger(__name__)


class SmartClipper:
    """Cắt video thành các segments nhỏ."""

    def __init__(self, config: CutterConfig) -> None:
        self._config = config

    @log_duration(msg_template="Clipping {func_name}")
    def export_clip(
        self,
        video_id: str,
        video_path: str,
        start_time: float,
        end_time: float,
        output_dir: str,
        video_filter: str | None = None,
    ) -> Clip:
        """Sử dụng FFmpeg stream copy để cắt cực nhanh không re-encode."""
        os.makedirs(output_dir, exist_ok=True)
        duration = end_time - start_time
        
        safe_start = str(start_time).replace(".", "_")
        filename = f"{video_id}_{safe_start}.mp4"
        output_path = os.path.join(output_dir, filename)

        # Cắt nhanh không encode
        cmd = ["ffmpeg", "-y", "-ss", str(start_time), "-t", str(duration), "-i", video_path]
        if video_filter:
            cmd.extend([
                "-filter_complex",
                video_filter,
                "-map",
                "[v]",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                "-shortest",
                output_path,
            ])
        else:
            cmd.extend([
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                output_path,
            ])

        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr.decode()}")
            raise ClipExportError(f"Failed to cut {filename}: {e}") from e

        return Clip(
            video_id=video_id,
            file_path=output_path,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
        )
