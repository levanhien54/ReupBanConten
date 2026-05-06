"""
Algorithm Benchmark — Đánh giá hiệu năng và độ chính xác.

Đo đạc:
  - Scene Detector: tốc độ (fps), phân bố confidence, false positive rate.
  - Black/Flash Filter: tốc độ, precision/recall trên synthetic data.
  - Overall pipeline latency.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from src.core.config import PreciseSceneConfig, BlackFlashFilterConfig
from src.core.logging import get_logger
from src.cutter.black_flash_filter import BlackFlashFilter

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────
#  Result dataclasses
# ──────────────────────────────────────────────────────────

@dataclass
class SceneDetectionBenchmark:
    """Kết quả benchmark phát hiện cảnh."""
    video_duration_s: float = 0.0
    total_time_ms: float = 0.0
    scenes_found: int = 0
    # Per-method
    content_count: int = 0
    adaptive_count: int = 0
    consensus_count: int = 0          # sau consensus vote
    # Confidence phân bố
    confidence_avg: float = 0.0
    confidence_min: float = 0.0
    confidence_max: float = 0.0
    high_conf_ratio: float = 0.0      # tỷ lệ confidence >= 0.7
    # Hiệu năng
    fps_processed: float = 0.0        # frame / s xử lý
    realtime_ratio: float = 0.0       # 1.0 = real-time, >1 = nhanh hơn
    # Đánh giá
    estimated_fp_rate: float = 0.0    # ước tính false positive (low-conf cuts)
    grade: str = "N/A"


@dataclass
class FilterBenchmark:
    """Kết quả benchmark Black/Flash Filter."""
    # Dữ liệu tổng hợp (synthetic)
    synthetic_total: int = 0
    synthetic_true_bad: int = 0       # ground truth
    synthetic_detected_bad: int = 0   # filter phát hiện
    # Metrics
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    # Hiệu năng
    avg_time_ms_per_segment: float = 0.0
    total_time_ms: float = 0.0
    grade: str = "N/A"


@dataclass
class BenchmarkReport:
    """Báo cáo tổng hợp."""
    scene: SceneDetectionBenchmark = field(default_factory=SceneDetectionBenchmark)
    filter: FilterBenchmark = field(default_factory=FilterBenchmark)
    overall_grade: str = "N/A"
    summary: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────
#  Video Synthesis Helpers
# ──────────────────────────────────────────────────────────

def _create_synthetic_video(
    path: str,
    duration_s: float = 10.0,
    fps: int = 30,
    scene_cuts: list[float] | None = None,
    has_black_frames: bool = False,
    has_flashes: bool = False,
) -> dict:
    """
    Tạo video giả lập bằng OpenCV VideoWriter.
    Trả về metadata để dùng làm ground truth.
    """
    w, h = 640, 360
    # MJPG + AVI: được hỗ trợ đầy đủ trên Windows với OpenCV
    avi_path = path.replace(".mp4", ".avi")
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(avi_path, fourcc, fps, (w, h))
    if not out.isOpened():
        # Fallback: mp4v
        avi_path = path
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(avi_path, fourcc, fps, (w, h))

    total_frames = int(duration_s * fps)
    gt_cut_frames: list[int] = []
    gt_black_frames: list[int] = []
    gt_flash_frames: list[int] = []

    if scene_cuts:
        gt_cut_frames = [int(t * fps) for t in scene_cuts]

    scene_colors = [
        (30, 80, 180), (80, 160, 40), (200, 50, 50),
        (180, 120, 30), (60, 60, 200), (100, 200, 100),
    ]

    # Black frames: 10%-95% = 85% of video → well above black_ratio=0.7 threshold
    black_start = int(total_frames * 0.10)
    black_end   = int(total_frames * 0.95)
    # Flash: alternate every frame for 20% of video → flash_rate >> 2.0/s
    flash_start = int(total_frames * 0.00)
    flash_end   = int(total_frames * 0.20)

    current_scene = 0
    for f_idx in range(total_frames):
        if f_idx in gt_cut_frames:
            current_scene = (current_scene + 1) % len(scene_colors)

        color = scene_colors[current_scene % len(scene_colors)]
        frame = np.full((h, w, 3), color, dtype=np.uint8)

        # Khung đen thuần túy
        if has_black_frames and black_start <= f_idx < black_end:
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            gt_black_frames.append(f_idx)

        # Flash: xen kẽ trắng/đen rất nhanh
        if has_flashes and flash_start <= f_idx < flash_end:
            brightness = 255 if f_idx % 2 == 0 else 0
            frame = np.full((h, w, 3), brightness, dtype=np.uint8)
            gt_flash_frames.append(f_idx)

        out.write(frame)

    out.release()
    return {
        "path": avi_path,           # actual file written
        "duration": duration_s,
        "fps": fps,
        "scene_cuts": scene_cuts or [],
        "gt_black_frames": gt_black_frames,
        "gt_flash_frames": gt_flash_frames,
        "has_black": has_black_frames,
        "has_flashes": has_flashes,
    }


# ──────────────────────────────────────────────────────────
#  Scene Detection Benchmark
# ──────────────────────────────────────────────────────────

def benchmark_scene_detector(
    config: PreciseSceneConfig,
    video_path: Optional[str] = None,
    progress_cb=None,
) -> SceneDetectionBenchmark:
    """
    Chạy benchmark trên video thực hoặc video tổng hợp.
    progress_cb(float 0..1, str msg): callback cập nhật tiến độ.
    """

    def _progress(pct: float, msg: str) -> None:
        if progress_cb:
            progress_cb(pct, msg)
        logger.info(f"[SceneBenchmark] {int(pct*100)}% — {msg}")

    result = SceneDetectionBenchmark()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Nếu không có video thực, dùng synthetic
        use_synthetic = video_path is None or not os.path.exists(video_path)

        if use_synthetic:
            _progress(0.05, "Tao video tong hop (10s, 5 scenes)...")
            synth_path = os.path.join(tmpdir, "synth_scene.mp4")
            gt = _create_synthetic_video(
                synth_path,
                duration_s=10.0,
                fps=30,
                scene_cuts=[2.0, 4.0, 6.0, 8.0],
            )
            video_path = gt.get("path", synth_path)  # use actual written path
            result.video_duration_s = gt["duration"]
        else:
            cap = cv2.VideoCapture(video_path)
            duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
            cap.release()
            result.video_duration_s = duration

        _progress(0.20, "Chạy Content Detector...")
        t_start = time.perf_counter()

        try:
            from scenedetect import detect, ContentDetector, AdaptiveDetector

            t0 = time.perf_counter()
            content_scenes = detect(
                video_path,
                ContentDetector(threshold=config.content_threshold),
                show_progress=False,
            )
            t_content = time.perf_counter() - t0
            content_cuts = [s[1].get_seconds() for s in content_scenes][:-1]
            result.content_count = len(content_cuts)

            _progress(0.50, f"Content: {len(content_cuts)} cuts ({t_content*1000:.0f}ms). Chạy Adaptive...")

            t0 = time.perf_counter()
            adaptive_scenes = detect(
                video_path,
                AdaptiveDetector(adaptive_threshold=config.adaptive_threshold),
                show_progress=False,
            )
            t_adaptive = time.perf_counter() - t0
            adaptive_cuts = [s[1].get_seconds() for s in adaptive_scenes][:-1]
            result.adaptive_count = len(adaptive_cuts)

            _progress(0.75, f"Adaptive: {len(adaptive_cuts)} cuts ({t_adaptive*1000:.0f}ms). Consensus Vote...")

            # Consensus
            all_ts: list[tuple[float, str]] = []
            for t in content_cuts:
                all_ts.append((t, "content"))
            for t in adaptive_cuts:
                all_ts.append((t, "adaptive"))
            all_ts.sort(key=lambda x: x[0])

            merged_cuts = []
            if all_ts:
                grp = [all_ts[0]]
                for ts, m in all_ts[1:]:
                    if ts - grp[-1][0] <= config.consensus_tolerance:
                        grp.append((ts, m))
                    else:
                        methods = {x[1] for x in grp}
                        avg_t = sum(x[0] for x in grp) / len(grp)
                        conf = min(1.0, len(methods) / 3.0 + 0.3)
                        merged_cuts.append({"t": avg_t, "conf": conf, "methods": list(methods)})
                        grp = [(ts, m)]
                if grp:
                    methods = {x[1] for x in grp}
                    avg_t = sum(x[0] for x in grp) / len(grp)
                    conf = min(1.0, len(methods) / 3.0 + 0.3)
                    merged_cuts.append({"t": avg_t, "conf": conf, "methods": list(methods)})

            result.consensus_count = len(merged_cuts)
            result.scenes_found = len(merged_cuts)

            # Phân bố confidence
            if merged_cuts:
                confs = [c["conf"] for c in merged_cuts]
                result.confidence_avg = float(np.mean(confs))
                result.confidence_min = float(np.min(confs))
                result.confidence_max = float(np.max(confs))
                result.high_conf_ratio = sum(1 for c in confs if c >= 0.7) / len(confs)
                result.estimated_fp_rate = sum(1 for c in confs if c < 0.4) / len(confs)

            total_t = time.perf_counter() - t_start
            result.total_time_ms = total_t * 1000

            # Hiệu năng
            cap_tmp = cv2.VideoCapture(video_path)
            total_frames = int(cap_tmp.get(cv2.CAP_PROP_FRAME_COUNT))
            cap_tmp.release()
            result.fps_processed = total_frames / max(total_t, 0.001)
            result.realtime_ratio = result.video_duration_s / max(total_t, 0.001)

        except ImportError:
            logger.warning("scenedetect not installed — skipping scene benchmark.")

        # Grade
        if result.confidence_avg >= 0.75 and result.estimated_fp_rate < 0.1:
            result.grade = "A+"
        elif result.confidence_avg >= 0.60:
            result.grade = "A"
        elif result.confidence_avg >= 0.45:
            result.grade = "B"
        else:
            result.grade = "C"

        _progress(1.0, f"Scene benchmark xong. Grade: {result.grade}")
        return result


# ──────────────────────────────────────────────────────────
#  Black/Flash Filter Benchmark
# ──────────────────────────────────────────────────────────

def benchmark_filter(
    config: BlackFlashFilterConfig,
    progress_cb=None,
) -> FilterBenchmark:
    """
    Tạo synthetic video clips với ground truth và đo precision/recall.
    """
    def _progress(pct: float, msg: str) -> None:
        if progress_cb:
            progress_cb(pct, msg)
        logger.info(f"[FilterBenchmark] {int(pct*100)}% — {msg}")

    result = FilterBenchmark()
    bf = BlackFlashFilter(config)

    test_cases: list[dict] = [
        # (label, has_black, has_flashes, gt_bad)
        {"label": "Normal video",       "black": False, "flash": False, "gt_bad": False},
        {"label": "Black frames >70%",  "black": True,  "flash": False, "gt_bad": True},
        {"label": "Flash attack",       "black": False, "flash": True,  "gt_bad": True},
        {"label": "Both bad",           "black": True,  "flash": True,  "gt_bad": True},
        {"label": "Normal variant 2",   "black": False, "flash": False, "gt_bad": False},
    ]

    result.synthetic_total = len(test_cases)
    total_time = 0.0

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, tc in enumerate(test_cases):
            _progress(i / len(test_cases), f"Testing: {tc['label']}...")

            path = os.path.join(tmpdir, f"test_{i}.mp4")
            gt = _create_synthetic_video(
                path,
                duration_s=3.0,
                fps=30,
                has_black_frames=tc["black"],
                has_flashes=tc["flash"],
            )
            actual_path = gt.get("path", path)

            t0 = time.perf_counter()
            quality = bf.check_segment(actual_path)
            elapsed = (time.perf_counter() - t0) * 1000
            total_time += elapsed

            gt_bad = tc["gt_bad"]
            detected_bad = quality.is_bad

            if gt_bad:
                result.synthetic_true_bad += 1
                if detected_bad:
                    result.true_positive += 1
                    result.synthetic_detected_bad += 1
                else:
                    result.false_negative += 1
            else:
                if detected_bad:
                    result.false_positive += 1
                    result.synthetic_detected_bad += 1

    result.total_time_ms = total_time
    result.avg_time_ms_per_segment = total_time / len(test_cases)

    # Precision / Recall / F1
    tp = result.true_positive
    fp = result.false_positive
    fn = result.false_negative

    result.precision = tp / max(tp + fp, 1)
    result.recall    = tp / max(tp + fn, 1)
    f1_denom = result.precision + result.recall
    result.f1_score  = 2 * result.precision * result.recall / max(f1_denom, 1e-9)

    if result.f1_score >= 0.9:
        result.grade = "A+"
    elif result.f1_score >= 0.75:
        result.grade = "A"
    elif result.f1_score >= 0.60:
        result.grade = "B"
    else:
        result.grade = "C"

    _progress(1.0, f"Filter benchmark xong. F1={result.f1_score:.2f} Grade={result.grade}")
    return result


# ──────────────────────────────────────────────────────────
#  Full Combined Benchmark
# ──────────────────────────────────────────────────────────

def run_full_benchmark(
    scene_config: PreciseSceneConfig,
    filter_config: BlackFlashFilterConfig,
    video_path: Optional[str] = None,
    progress_cb=None,
) -> BenchmarkReport:
    """Chạy toàn bộ benchmark và tổng hợp báo cáo."""
    report = BenchmarkReport()

    def _scene_progress(pct: float, msg: str) -> None:
        if progress_cb:
            progress_cb(pct * 0.55, f"[Scene] {msg}")

    def _filter_progress(pct: float, msg: str) -> None:
        if progress_cb:
            progress_cb(0.55 + pct * 0.45, f"[Filter] {msg}")

    report.scene = benchmark_scene_detector(scene_config, video_path, _scene_progress)
    report.filter = benchmark_filter(filter_config, _filter_progress)

    # Overall grade
    grades = {"A+": 4, "A": 3, "B": 2, "C": 1, "N/A": 0}
    avg = (grades.get(report.scene.grade, 0) + grades.get(report.filter.grade, 0)) / 2
    if avg >= 3.5:
        report.overall_grade = "A+"
    elif avg >= 2.5:
        report.overall_grade = "A"
    elif avg >= 1.5:
        report.overall_grade = "B"
    else:
        report.overall_grade = "C"

    report.summary = _build_summary(report)
    return report


def _build_summary(r: BenchmarkReport) -> list[str]:
    s = r.scene
    f = r.filter
    lines = [
        "═══════════════════════════════════════════════",
        "         BENCHMARK REPORT — CUTTER MODULE",
        "═══════════════════════════════════════════════",
        "",
        "── Scene Detector ──────────────────────────",
        f"  Video duration     : {s.video_duration_s:.1f}s",
        f"  Processing time    : {s.total_time_ms:.0f}ms",
        f"  Realtime ratio     : {s.realtime_ratio:.1f}x  {'✅' if s.realtime_ratio > 1 else '⚠️'}",
        f"  Throughput         : {s.fps_processed:.0f} fps",
        f"  Content cuts       : {s.content_count}",
        f"  Adaptive cuts      : {s.adaptive_count}",
        f"  After consensus    : {s.consensus_count}",
        f"  Confidence avg     : {s.confidence_avg:.2f}  (min {s.confidence_min:.2f} / max {s.confidence_max:.2f})",
        f"  High-conf ratio    : {s.high_conf_ratio:.1%}  (≥0.7)",
        f"  Est. FP rate       : {s.estimated_fp_rate:.1%}",
        f"  Grade              : {s.grade}",
        "",
        "── Black / Flash Filter ────────────────────",
        f"  Test cases         : {f.synthetic_total}  (synthetic ground truth)",
        f"  True bad videos    : {f.synthetic_true_bad}",
        f"  Detected correctly : TP={f.true_positive}  FP={f.false_positive}  FN={f.false_negative}",
        f"  Precision          : {f.precision:.1%}",
        f"  Recall             : {f.recall:.1%}",
        f"  F1 Score           : {f.f1_score:.2f}",
        f"  Avg time/segment   : {f.avg_time_ms_per_segment:.0f}ms",
        f"  Grade              : {f.grade}",
        "",
        "── Overall ─────────────────────────────────",
        f"  Overall Grade      : {r.overall_grade}",
        "═══════════════════════════════════════════════",
    ]
    return lines
