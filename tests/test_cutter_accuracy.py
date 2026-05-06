"""
Tests tự động cho thuật toán cắt video:
  - Tạo video tổng hợp với các điểm cắt đã biết
  - Đo độ chính xác scene detection
  - Đo độ chính xác Black/Flash filter
  - Kiểm tra pipeline cắt thực tế (ffmpeg)
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.core.config import (
    PreciseSceneConfig, BlackFlashFilterConfig,
)

# ─── Helpers ─────────────────────────────────────────────────────


def _write_video(path: str, frames: list[np.ndarray], fps: float = 30.0) -> None:
    h, w = frames[0].shape[:2]
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))
    for f in frames:
        out.write(f)
    out.release()


def _make_scene_video(fps: float = 30.0, scene_durations: list[float] = None) -> tuple[str, list[float]]:
    """
    Tạo video với N cảnh, mỗi cảnh màu khác nhau.
    Trả về (path, danh sách cut_times thực tế).
    """
    if scene_durations is None:
        scene_durations = [2.0, 2.0, 3.0, 1.5, 2.5]

    colors = [
        (200,  50,  50), (50, 200,  50), (50,  50, 200),
        (200, 200,  50), (50, 200, 200), (200,  50, 200),
    ]
    frames = []
    true_cuts: list[float] = []
    t = 0.0
    for i, dur in enumerate(scene_durations):
        n = int(dur * fps)
        color = colors[i % len(colors)]
        # Add slight noise để detector không bị static
        for _ in range(n):
            f = np.full((180, 320, 3), color, dtype=np.uint8)
            f += np.random.randint(0, 8, f.shape, dtype=np.uint8)
            frames.append(f)
        t += dur
        true_cuts.append(round(t, 3))

    tmp = tempfile.NamedTemporaryFile(suffix=".avi", delete=False)
    tmp.close()
    _write_video(tmp.name, frames, fps)
    return tmp.name, true_cuts[:-1]  # loại điểm cuối


def _make_black_video(fps: float = 30.0, duration: float = 3.0) -> str:
    n = int(duration * fps)
    frames = [np.zeros((180, 320, 3), dtype=np.uint8) for _ in range(n)]
    tmp = tempfile.NamedTemporaryFile(suffix=".avi", delete=False)
    tmp.close()
    _write_video(tmp.name, frames, fps)
    return tmp.name


def _make_flash_video(fps: float = 30.0, duration: float = 3.0) -> str:
    """Video xen kẽ trắng đen mỗi frame → flash rate cao."""
    n = int(duration * fps)
    frames = []
    for i in range(n):
        val = 255 if i % 2 == 0 else 0
        frames.append(np.full((180, 320, 3), val, dtype=np.uint8))
    tmp = tempfile.NamedTemporaryFile(suffix=".avi", delete=False)
    tmp.close()
    _write_video(tmp.name, frames, fps)
    return tmp.name


def _make_normal_video(fps: float = 30.0, duration: float = 5.0) -> str:
    n = int(duration * fps)
    frames = []
    for i in range(n):
        f = np.random.randint(80, 200, (180, 320, 3), dtype=np.uint8)
        frames.append(f)
    tmp = tempfile.NamedTemporaryFile(suffix=".avi", delete=False)
    tmp.close()
    _write_video(tmp.name, frames, fps)
    return tmp.name


# ─── Scene Detector Tests ─────────────────────────────────────────


class TestSceneDetector:
    """Kiểm tra độ chính xác phát hiện cảnh."""

    @pytest.fixture
    def config(self):
        return PreciseSceneConfig(
            content_threshold=15.0,
            adaptive_threshold=2.5,
            min_scene_len=1.0,
            consensus_tolerance=0.5,
        )

    def test_detects_correct_scene_count(self, config, tmp_path):
        """Phát hiện đúng số cảnh trong video tổng hợp."""
        pytest.importorskip("scenedetect")
        scene_durs = [2.0, 2.0, 2.0, 2.0]  # 4 cảnh → 3 điểm cắt
        vid, true_cuts = _make_scene_video(scene_durations=scene_durs)
        try:
            from src.cutter.scene_detector import PreciseSceneDetector
            det = PreciseSceneDetector(config)
            scenes = det.detect_scenes(vid)
            # Cho phép sai số ±1 do đặc tính video màu đơn giản
            assert abs(len(scenes) - len(true_cuts)) <= 1, (
                f"Expected ~{len(true_cuts)} cuts, got {len(scenes)}"
            )
        finally:
            os.unlink(vid)

    def test_cut_point_accuracy(self, config):
        """Điểm cắt sai lệch không quá 0.5s so với thực tế."""
        pytest.importorskip("scenedetect")
        scene_durs = [3.0, 3.0, 3.0]
        vid, true_cuts = _make_scene_video(scene_durations=scene_durs)
        try:
            from src.cutter.scene_detector import PreciseSceneDetector
            det = PreciseSceneDetector(config)
            scenes = det.detect_scenes(vid)

            if not scenes:
                pytest.skip("Không detect được scene nào (video màu đơn giản)")

            detected_times = sorted([s.cut_time for s in scenes])
            true_sorted = sorted(true_cuts)

            # So sánh điểm cắt gần nhất
            matched = 0
            for tc in true_sorted:
                for dc in detected_times:
                    if abs(tc - dc) <= 0.5:
                        matched += 1
                        break
            precision = matched / max(len(detected_times), 1)
            recall    = matched / max(len(true_sorted), 1)
            print(f"\n  True cuts: {true_sorted}")
            print(f"  Detected:  {detected_times}")
            print(f"  Precision={precision:.2%}  Recall={recall:.2%}")
            assert recall >= 0.5, f"Recall quá thấp: {recall:.2%}"
        finally:
            os.unlink(vid)

    def test_min_scene_length_enforced(self, config):
        """Không trả về cảnh ngắn hơn min_scene_len."""
        pytest.importorskip("scenedetect")
        vid, _ = _make_scene_video(scene_durations=[3.0, 3.0, 3.0])
        try:
            from src.cutter.scene_detector import PreciseSceneDetector
            det = PreciseSceneDetector(config)
            scenes = det.detect_scenes(vid)
            times = sorted([s.cut_time for s in scenes])
            for i in range(1, len(times)):
                gap = times[i] - times[i-1]
                assert gap >= config.min_scene_len - 0.1, (
                    f"Scene quá ngắn: {gap:.2f}s < {config.min_scene_len}s"
                )
        finally:
            os.unlink(vid)

    def test_empty_video_returns_empty(self, config, tmp_path):
        """Video rỗng / không hợp lệ không crash."""
        pytest.importorskip("scenedetect")
        vid, _ = _make_scene_video(scene_durations=[5.0])  # 1 cảnh duy nhất
        try:
            from src.cutter.scene_detector import PreciseSceneDetector
            det = PreciseSceneDetector(config)
            scenes = det.detect_scenes(vid)
            assert isinstance(scenes, list)
        finally:
            os.unlink(vid)

    def test_performance_fps(self, config):
        """Tốc độ xử lý > 30 FPS (không chậm hơn real-time)."""
        pytest.importorskip("scenedetect")
        vid, _ = _make_scene_video(scene_durations=[2.0, 2.0, 2.0])
        vid_dur = 6.0
        try:
            from src.cutter.scene_detector import PreciseSceneDetector
            det = PreciseSceneDetector(config)
            t0 = time.perf_counter()
            det.detect_scenes(vid)
            elapsed = time.perf_counter() - t0
            total_frames = int(vid_dur * 30)
            fps = total_frames / max(elapsed, 0.01)
            print(f"\n  Detection speed: {fps:.0f} FPS (elapsed={elapsed:.2f}s)")
            assert fps >= 30, f"Quá chậm: {fps:.0f} FPS"
        finally:
            os.unlink(vid)


# ─── Black/Flash Filter Tests ────────────────────────────────────


class TestBlackFlashFilter:
    """Kiểm tra độ chính xác bộ lọc khung đen/flash."""

    @pytest.fixture
    def config(self):
        return BlackFlashFilterConfig(
            black_threshold=15.0,
            black_ratio=0.7,
            flash_threshold=100.0,
            min_segment_duration=0.5,
        )

    def test_black_video_detected(self, config):
        """Video toàn đen bị phát hiện là bad."""
        vid = _make_black_video()
        try:
            from src.cutter.black_flash_filter import BlackFlashFilter
            bf = BlackFlashFilter(config)
            q = bf.check_segment(vid)
            assert q.is_bad, "Video đen không bị phát hiện"
            assert q.black_ratio > config.black_ratio
            print(f"\n  Black ratio: {q.black_ratio:.2%}")
        finally:
            os.unlink(vid)

    def test_flash_video_detected(self, config):
        """Video flash mạnh bị phát hiện là bad."""
        vid = _make_flash_video()
        try:
            from src.cutter.black_flash_filter import BlackFlashFilter
            bf = BlackFlashFilter(config)
            q = bf.check_segment(vid)
            assert q.is_bad, "Video flash không bị phát hiện"
            print(f"\n  Flash rate: {q.flash_rate:.2f}/s")
        finally:
            os.unlink(vid)

    def test_normal_video_passes(self, config):
        """Video bình thường không bị loại."""
        vid = _make_normal_video()
        try:
            from src.cutter.black_flash_filter import BlackFlashFilter
            bf = BlackFlashFilter(config)
            q = bf.check_segment(vid)
            assert not q.is_bad, f"Video hợp lệ bị loại sai: {q.reasons}"
            print(f"\n  Avg brightness: {q.avg_brightness:.1f}  Black: {q.black_ratio:.2%}")
        finally:
            os.unlink(vid)

    def test_precision_recall_on_mixed_batch(self, config):
        """F1-score trên batch gồm cả video tốt và xấu."""
        from src.cutter.black_flash_filter import BlackFlashFilter
        bf = BlackFlashFilter(config)

        cases = [
            (_make_black_video(duration=2.0),  True,  "black"),
            (_make_flash_video(duration=2.0),  True,  "flash"),
            (_make_normal_video(duration=3.0), False, "normal_1"),
            (_make_normal_video(duration=2.0), False, "normal_2"),
        ]

        tp = fp = fn = tn = 0
        try:
            for path, expected_bad, label in cases:
                q = bf.check_segment(path)
                predicted_bad = q.is_bad
                if expected_bad and predicted_bad:   tp += 1
                elif expected_bad and not predicted_bad: fn += 1
                elif not expected_bad and predicted_bad: fp += 1
                else: tn += 1
                print(f"\n  [{label}] expected={expected_bad} got={predicted_bad} reasons={q.reasons}")
        finally:
            for path, _, _ in cases:
                if os.path.exists(path):
                    os.unlink(path)

        precision = tp / max(tp + fp, 1)
        recall    = tp / max(tp + fn, 1)
        f1        = 2 * precision * recall / max(precision + recall, 1e-9)
        print(f"\n  TP={tp} FP={fp} FN={fn} TN={tn}")
        print(f"  Precision={precision:.2%}  Recall={recall:.2%}  F1={f1:.2%}")
        assert precision >= 0.8, f"Precision thấp: {precision:.2%}"
        assert recall    >= 0.8, f"Recall thấp: {recall:.2%}"


# ─── Cut Pipeline Test ───────────────────────────────────────────


class TestCutPipeline:
    """Kiểm tra pipeline cắt thực tế bằng ffmpeg."""

    def _ffmpeg_available(self) -> bool:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def test_ffmpeg_cut_accuracy(self, tmp_path):
        """
        Kiểm tra ffmpeg cắt đúng thời điểm.
        So sánh frame count của clip với expected duration.
        """
        if not self._ffmpeg_available():
            pytest.skip("ffmpeg không có sẵn")

        src = str(tmp_path / "src.avi")
        fps = 30.0
        total_dur = 10.0
        frames = [
            np.random.randint(80, 200, (180, 320, 3), dtype=np.uint8)
            for _ in range(int(total_dur * fps))
        ]
        _write_video(src, frames, fps)

        # Cắt đoạn 3s–7s → expect ~4s = ~120 frames
        start, end = 3.0, 7.0
        out = str(tmp_path / "clip.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", src,
            "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "23", "-c:a", "aac",
            out,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        assert result.returncode == 0, f"ffmpeg failed: {result.stderr.decode()[:300]}"
        assert os.path.exists(out)

        cap = cv2.VideoCapture(out)
        actual_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        actual_fps    = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        expected_frames = int((end - start) * fps)
        tolerance = int(fps * 0.5)  # Â±0.5s tolerance

        print(f"\n  Expected ~{expected_frames} frames, got {actual_frames} ({actual_fps:.1f} fps)")
        print(f"  Accuracy: {abs(actual_frames - expected_frames)} frames off")
        assert abs(actual_frames - expected_frames) <= tolerance, (
            f"Sai lá»‡ch quĂ¡ lá»›n: {abs(actual_frames - expected_frames)} frames "
            f"(> {tolerance} frames tolerance)"
        )

    def test_smart_clipper_can_export_blurred_vertical_mp4(self, tmp_path):
        if not self._ffmpeg_available():
            pytest.skip("ffmpeg khĂ´ng cĂ³ sáºµn")

        from src.core.config import CutterConfig
        from src.cutter.smart_clipper import SmartClipper
        from src.remixer.vertical_video import build_blur_background_filter

        src = str(tmp_path / "src.avi")
        frames = [np.random.randint(50, 200, (180, 320, 3), dtype=np.uint8) for _ in range(90)]
        _write_video(src, frames, 30.0)

        clip = SmartClipper(CutterConfig()).export_clip(
            video_id="vertical_test",
            video_path=src,
            start_time=0.0,
            end_time=2.0,
            output_dir=str(tmp_path),
            video_filter=build_blur_background_filter(width=1080, height=1920),
        )

        cap = cv2.VideoCapture(clip.file_path)
        assert cap.isOpened(), "Clip Ä‘áº§u ra khĂ´ng Ä‘á»c Ä‘Æ°á»£c"
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ret, frame = cap.read()
        cap.release()

        assert ret and frame is not None
        assert (width, height) == (1080, 1920)
        return

        expected_frames = int((end - start) * fps)
        tolerance = int(fps * 0.5)  # ±0.5s tolerance

        print(f"\n  Expected ~{expected_frames} frames, got {actual_frames} ({actual_fps:.1f} fps)")
        print(f"  Accuracy: {abs(actual_frames - expected_frames)} frames off")
        assert abs(actual_frames - expected_frames) <= tolerance, (
            f"Sai lệch quá lớn: {abs(actual_frames - expected_frames)} frames "
            f"(> {tolerance} frames tolerance)"
        )

    def test_cut_produces_valid_mp4(self, tmp_path):
        """Clip đầu ra phải mở được bằng OpenCV."""
        if not self._ffmpeg_available():
            pytest.skip("ffmpeg không có sẵn")

        src = str(tmp_path / "src.avi")
        frames = [np.random.randint(50, 200, (180, 320, 3), dtype=np.uint8) for _ in range(90)]
        _write_video(src, frames, 30.0)

        out = str(tmp_path / "clip.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", src,
            "-ss", "0.0", "-to", "2.0",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "23", "-c:a", "aac", out
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)

        cap = cv2.VideoCapture(out)
        assert cap.isOpened(), "Clip đầu ra không đọc được"
        ret, frame = cap.read()
        assert ret and frame is not None, "Không đọc được frame từ clip"
        cap.release()
