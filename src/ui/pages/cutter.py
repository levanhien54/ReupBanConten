"""
Cutter Page — Scene detection settings + Benchmark panel.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QFrame, QSpinBox,
    QDoubleSpinBox, QSplitter, QProgressBar, QTextEdit,
    QFileDialog, QGroupBox, QFormLayout, QScrollArea
)

from src.core.config import AppConfig
from src.ui.utils import Worker
from src.core.logging import get_logger
import cv2

logger = get_logger(__name__)


class CutterPage(QWidget):
    """Trang phát hiện cảnh và cắt video + Benchmark."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._threadpool = QThreadPool()
        from src.core.database import get_database, VideoRepository, ClipRepository
        db = get_database()
        self._video_repo = VideoRepository(db)
        self._clip_repo = ClipRepository(db)
        self._video_path: str = ""
        self._output_dir: str = str(config.storage.clips
                                    if hasattr(config.storage, 'clips')
                                    else config.storage.downloads)
        self._detected_scenes: list = []
        self._setup_ui()

    # ──────────────────── Setup ────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Bọc controls vào ScrollArea để cuộn khi cửa sổ nhỏ
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0F172A; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #334155; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        left_scroll.setWidget(self._build_controls())
        left_scroll.setMinimumWidth(320)

        # Bọc results vào ScrollArea
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0F172A; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #334155; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        right_scroll.setWidget(self._build_results())

        splitter.addWidget(left_scroll)
        splitter.addWidget(right_scroll)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)

    # ──────────────── Controls Panel (Left) ────────────────

    def _build_controls(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(12)

        _frame_style = """
            QGroupBox {
                color: #3B82F6; font-weight: bold; font-size: 13px;
                border: 1px solid #334155; border-radius: 8px;
                margin-top: 8px; padding: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QLabel { color: #94A3B8; }
            QDoubleSpinBox, QSpinBox {
                padding: 5px; background: #0F172A; color: #F8FAFC;
                border: 1px solid #334155; border-radius: 4px;
            }
        """

        # ── Chọn video ──
        grp_video = QGroupBox("🎬 Video Nguồn")
        grp_video.setStyleSheet(_frame_style)
        v_layout = QVBoxLayout(grp_video)

        self.lbl_video = QLabel("Chưa chọn video")
        self.lbl_video.setStyleSheet("color: #64748B; font-style: italic; font-size: 12px;")
        self.lbl_video.setWordWrap(True)

        btn_choose = QPushButton("📁 Chọn Video...")
        btn_choose.setStyleSheet("background:#1E293B; color:white; padding:8px; border-radius:4px;")
        btn_choose.clicked.connect(self._choose_video)

        v_layout.addWidget(self.lbl_video)
        v_layout.addWidget(btn_choose)
        layout.addWidget(grp_video)

        # ── Chọn thư mục lưu clips ──
        grp_out = QGroupBox("📂 Thư Mục Lưu Clips")
        grp_out.setStyleSheet(_frame_style)
        out_layout = QVBoxLayout(grp_out)
        out_layout.setSpacing(6)

        self.lbl_out_dir = QLabel(self._output_dir)
        self.lbl_out_dir.setStyleSheet(
            "color: #10B981; font-size: 11px; "
            "border: 1px solid #334155; border-radius: 4px; padding: 4px 6px;"
        )
        self.lbl_out_dir.setWordWrap(True)

        btn_out_row = QHBoxLayout()
        btn_choose_out = QPushButton("📁 Đổi thư mục...")
        btn_choose_out.setStyleSheet(
            "background:#1E293B; color:white; padding:7px; border-radius:4px;"
        )
        btn_choose_out.clicked.connect(self._choose_output_dir)

        btn_open_out = QPushButton("🔍 Mở")
        btn_open_out.setFixedWidth(52)
        btn_open_out.setStyleSheet(
            "background:#0F172A; color:#64748B; padding:7px; border-radius:4px;"
        )
        btn_open_out.clicked.connect(self._open_output_dir)

        btn_out_row.addWidget(btn_choose_out, 1)
        btn_out_row.addWidget(btn_open_out)
        out_layout.addWidget(self.lbl_out_dir)
        out_layout.addLayout(btn_out_row)
        layout.addWidget(grp_out)

        # ── Scene Detection settings ──
        grp_scene = QGroupBox("✂️ Scene Detector")
        grp_scene.setStyleSheet(_frame_style)
        form = QFormLayout(grp_scene)
        form.setSpacing(8)

        self.spn_content_thr = QDoubleSpinBox()
        self.spn_content_thr.setRange(5.0, 60.0)
        self.spn_content_thr.setSingleStep(1.0)
        self.spn_content_thr.setValue(self._config.scene_detection_precise.content_threshold)
        self.spn_content_thr.setToolTip("Ngưỡng càng thấp → cắt nhiều hơn")

        self.spn_adaptive_thr = QDoubleSpinBox()
        self.spn_adaptive_thr.setRange(1.0, 15.0)
        self.spn_adaptive_thr.setSingleStep(0.5)
        self.spn_adaptive_thr.setValue(self._config.scene_detection_precise.adaptive_threshold)

        self.spn_min_len = QDoubleSpinBox()
        self.spn_min_len.setRange(0.5, 10.0)
        self.spn_min_len.setSingleStep(0.5)
        self.spn_min_len.setValue(self._config.scene_detection_precise.min_scene_len)
        self.spn_min_len.setToolTip("Độ dài tối thiểu mỗi cảnh (giây)")

        form.addRow("Content Threshold:", self.spn_content_thr)
        form.addRow("Adaptive Threshold:", self.spn_adaptive_thr)
        form.addRow("Min Scene Len (s):", self.spn_min_len)
        layout.addWidget(grp_scene)

        # ── Black/Flash Filter settings ──
        grp_filter = QGroupBox("🚫 Black/Flash Filter")
        grp_filter.setStyleSheet(_frame_style)
        form2 = QFormLayout(grp_filter)
        form2.setSpacing(8)

        self.spn_black_thr = QDoubleSpinBox()
        self.spn_black_thr.setRange(0.0, 50.0)
        self.spn_black_thr.setValue(self._config.black_flash_filter.black_threshold)

        self.spn_black_ratio = QDoubleSpinBox()
        self.spn_black_ratio.setRange(0.1, 1.0)
        self.spn_black_ratio.setSingleStep(0.05)
        self.spn_black_ratio.setValue(self._config.black_flash_filter.black_ratio)
        self.spn_black_ratio.setToolTip("Tỷ lệ khung đen tối đa cho phép")

        self.spn_flash_thr = QDoubleSpinBox()
        self.spn_flash_thr.setRange(20.0, 200.0)
        self.spn_flash_thr.setSingleStep(10.0)
        self.spn_flash_thr.setValue(self._config.black_flash_filter.flash_threshold)

        form2.addRow("Black Threshold:", self.spn_black_thr)
        form2.addRow("Max Black Ratio:", self.spn_black_ratio)
        form2.addRow("Flash Delta:", self.spn_flash_thr)
        layout.addWidget(grp_filter)

        # ── Action buttons ──
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_detect = QPushButton("✂️  Detect Scenes")
        self.btn_detect.setStyleSheet(
            "background:#F59E0B;color:white;padding:11px;font-weight:bold;border-radius:6px;font-size:13px;"
        )
        self.btn_detect.clicked.connect(self._on_detect)

        self.btn_cut = QPushButton("✂️  Cắt & Lưu Clips")
        self.btn_cut.setEnabled(False)
        self.btn_cut.setStyleSheet(
            "background:#10B981;color:white;padding:11px;font-weight:bold;"
            "border-radius:6px;font-size:13px;"
        )
        self.btn_cut.clicked.connect(self._on_cut_clips)

        self.btn_benchmark = QPushButton("📊  Run Benchmark")
        self.btn_benchmark.setStyleSheet(
            "background:#8B5CF6;color:white;padding:11px;font-weight:bold;border-radius:6px;font-size:13px;"
        )
        self.btn_benchmark.clicked.connect(self._on_benchmark)

        btn_layout.addWidget(self.btn_detect)
        btn_layout.addWidget(self.btn_cut)
        btn_layout.addWidget(self.btn_benchmark)
        layout.addLayout(btn_layout)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar { background:#1E293B; border:1px solid #334155; border-radius:4px; height:10px; }
            QProgressBar::chunk { background: #8B5CF6; border-radius:4px; }
        """)
        layout.addWidget(self.progress)
        self.lbl_progress = QLabel("Ready.")
        self.lbl_progress.setStyleSheet("color: #64748B; font-size: 12px;")
        layout.addWidget(self.lbl_progress)

        layout.addStretch()
        return widget

    # ──────────────── Results Panel (Right) ────────────────

    def _build_results(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(10)

        # Tab-like header
        header = QHBoxLayout()
        lbl_res = QLabel("Results / Benchmark Report")
        lbl_res.setStyleSheet("font-size: 15px; font-weight: bold; color: #F8FAFC;")
        self.btn_clear = QPushButton("🗑 Clear")
        self.btn_clear.setStyleSheet(
            "background:#1E293B;color:#94A3B8;padding:4px 12px;border-radius:4px;"
        )
        self.btn_clear.clicked.connect(lambda: self.txt_result.clear())
        header.addWidget(lbl_res)
        header.addStretch()
        header.addWidget(self.btn_clear)
        layout.addLayout(header)

        # Output area
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setStyleSheet("""
            QTextEdit {
                background-color: #020617;
                color: #A5F3FC;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        self.txt_result.setPlaceholderText(
            "Kết quả phát hiện cảnh hoặc báo cáo benchmark sẽ xuất hiện ở đây...\n"
            "▶ Chọn video → Detect Scenes để cắt thực tế.\n"
            "▶ Không cần video → Run Benchmark tự tạo dữ liệu kiểm thử."
        )
        layout.addWidget(self.txt_result)

        # Clip list (kết quả detect thực)
        lbl_clips = QLabel("Detected Scenes")
        lbl_clips.setStyleSheet("color: #94A3B8; font-weight: bold;")
        layout.addWidget(lbl_clips)

        self.list_clips = QListWidget()
        self.list_clips.setMaximumHeight(160)
        self.list_clips.setStyleSheet("""
            QListWidget {
                background: #1E293B; border: 1px solid #334155;
                border-radius: 6px; color: #F8FAFC; padding: 6px;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #334155; }
        """)
        layout.addWidget(self.list_clips)

        return widget

    # ──────────────── Handlers ────────────────

    def _choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video", "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.webm)"
        )
        if path:
            self._video_path = path
            name = path.split("/")[-1].split("\\")[-1]
            self.lbl_video.setText(f"✅ {name}")
            self.lbl_video.setStyleSheet("color: #10B981; font-size: 12px;")
            self.btn_cut.setEnabled(False)  # reset khi đổi video
            self._detected_scenes = []

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu clips")
        if path:
            self._output_dir = path
            self.lbl_out_dir.setText(path)
            self.lbl_out_dir.setStyleSheet(
                "color: #10B981; font-size: 11px;"
                "border: 1px solid #334155; border-radius: 4px; padding: 4px 6px;"
            )

    def _open_output_dir(self) -> None:
        import subprocess, os
        path = self._output_dir
        if os.path.exists(path):
            subprocess.Popen(f'explorer "{path}"')
        else:
            os.makedirs(path, exist_ok=True)
            subprocess.Popen(f'explorer "{path}"')

    def _on_detect(self) -> None:
        self.btn_detect.setEnabled(False)
        self.btn_benchmark.setEnabled(False)
        self.btn_detect.setText("⏳ Detecting...")
        self.list_clips.clear()
        self.txt_result.clear()
        self.progress.setValue(5)
        self.lbl_progress.setText("Đang phát hiện cảnh...")

        worker = Worker(self._run_detect_task)
        worker.signals.result.connect(self._on_detect_done)
        worker.signals.error.connect(self._on_task_error)
        worker.signals.finished.connect(self._reset_buttons)
        self._threadpool.start(worker)

    def _on_benchmark(self) -> None:
        self.btn_detect.setEnabled(False)
        self.btn_benchmark.setEnabled(False)
        self.btn_benchmark.setText("⏳ Benchmarking...")
        self.list_clips.clear()
        self.txt_result.clear()
        self.progress.setValue(2)
        self.lbl_progress.setText("Khởi động benchmark...")

        worker = Worker(self._run_benchmark_task)
        worker.signals.result.connect(self._on_benchmark_done)
        worker.signals.error.connect(self._on_task_error)
        worker.signals.finished.connect(self._reset_buttons)
        self._threadpool.start(worker)

    # ──────────────── Background Tasks ────────────────

    def _run_detect_task(self) -> list:
        """Phát hiện cảnh thực tế."""
        from src.cutter.scene_detector import PreciseSceneDetector

        # Cập nhật config từ UI
        self._config.scene_detection_precise.content_threshold = self.spn_content_thr.value()
        self._config.scene_detection_precise.adaptive_threshold = self.spn_adaptive_thr.value()
        self._config.scene_detection_precise.min_scene_len = self.spn_min_len.value()

        detector = PreciseSceneDetector(self._config.scene_detection_precise)
        path = self._video_path if self._video_path else None

        if not path:
            return [{"msg": "Không có video — chạy với dữ liệu giả lập (demo)", "mock": True}]

        scenes = detector.detect_scenes(path)
        return [{"t": s.cut_time, "conf": s.confidence, "methods": s.methods} for s in scenes]

    def _run_benchmark_task(self) -> object:
        """Chạy toàn bộ benchmark."""
        from src.cutter.benchmark import run_full_benchmark

        def _progress_cb(pct: float, msg: str) -> None:
            # Gọi update progress thông qua signal (cross-thread safe)
            self._safe_progress(int(pct * 100), msg)

        return run_full_benchmark(
            scene_config=self._config.scene_detection_precise,
            filter_config=self._config.black_flash_filter,
            video_path=self._video_path or None,
            progress_cb=_progress_cb,
        )

    def _safe_progress(self, val: int, msg: str) -> None:
        """Thread-safe progress update."""
        from PySide6.QtCore import QMetaObject, Qt as _Qt
        self.progress.setValue(val)
        self.lbl_progress.setText(msg)

    # ──────────────── Result Handlers ────────────────

    def _on_detect_done(self, scenes: list) -> None:
        self.progress.setValue(100)
        self.list_clips.clear()

        if scenes and scenes[0].get("mock"):
            self.txt_result.append(scenes[0]["msg"])
            return

        self.txt_result.append(f"✅ Phát hiện {len(scenes)} scenes\n")
        for i, s in enumerate(scenes):
            line = (f"  Scene {i+1:02d}:  {s['t']:.3f}s  "
                    f"| Conf: {s['conf']:.2f}  "
                    f"| Methods: {', '.join(s['methods'])}")
            self.list_clips.addItem(line)
            self.txt_result.append(line)

        self._detected_scenes = scenes
        self.btn_cut.setEnabled(bool(scenes) and bool(self._video_path))
        self.lbl_progress.setText(f"✅ {len(scenes)} scenes — Nhấn 'Cắt & Lưu Clips' để xuất.")

    def _on_benchmark_done(self, report: object) -> None:
        from src.cutter.benchmark import BenchmarkReport
        r: BenchmarkReport = report  # type: ignore

        self.progress.setValue(100)
        self.txt_result.clear()

        # In báo cáo đầy đủ
        for line in r.summary:
            self.txt_result.append(line)

        # Thêm màu grade vào status
        grade_colors = {"A+": "#10B981", "A": "#3B82F6", "B": "#F59E0B", "C": "#EF4444"}
        color = grade_colors.get(r.overall_grade, "#94A3B8")
        self.lbl_progress.setText(f"Benchmark hoàn thành — Overall Grade: {r.overall_grade}")
        self.lbl_progress.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")

    def _on_task_error(self, err_tuple: tuple) -> None:
        _, value, tb = err_tuple
        self.txt_result.append(f"\n❌ LỖI: {value}\n\nTraceback:\n{tb}")
        self.progress.setValue(0)
        self.lbl_progress.setText(f"❌ Error: {value}")
        self.lbl_progress.setStyleSheet("color: #EF4444; font-size: 12px;")

    def _reset_buttons(self) -> None:
        self.btn_detect.setEnabled(True)
        self.btn_benchmark.setEnabled(True)
        self.btn_detect.setText("✂️  Detect Scenes")
        self.btn_benchmark.setText("📊  Run Benchmark")
        self.btn_cut.setText("✂️  Cắt & Lưu Clips")

    # ──────────────── Cut & Export Clips ────────────────

    def _on_cut_clips(self) -> None:
        if not self._video_path or not self._detected_scenes:
            return
        import os
        os.makedirs(self._output_dir, exist_ok=True)
        self.btn_cut.setEnabled(False)
        self.btn_cut.setText("⏳ Đang cắt...")
        self.btn_detect.setEnabled(False)
        self.progress.setValue(2)
        self.lbl_progress.setText(f"Đang cắt {len(self._detected_scenes)} clips → {self._output_dir}")

        worker = Worker(self._run_cut_task)
        worker.signals.result.connect(self._on_cut_done)
        worker.signals.error.connect(self._on_task_error)
        worker.signals.finished.connect(self._reset_buttons)
        self._threadpool.start(worker)

    def _run_cut_task(self) -> list:
        """
        Xuất clips chính xác bằng ffmpeg.

        Chi tiết kỹ thuật:
        - Dùng: ffmpeg -i <src> -ss <start> -to <end> -c:v libx264 -preset fast
          (KHÔNG đặt -ss trước -i → tránh lệch keyframe)
        - Sau khi cắt: chạy BlackFlashFilter loại clip xấu
        """
        import subprocess, os
        from src.cutter.black_flash_filter import BlackFlashFilter
        from src.remixer.smart_crop import SmartCropper

        scenes  = self._detected_scenes
        out_dir = self._output_dir
        src     = self._video_path
        base    = os.path.splitext(os.path.basename(src))[0]
        bf      = BlackFlashFilter(self._config.black_flash_filter)
        cropper = SmartCropper(self._config.remixer.smart_crop)
        
        # Tiền xử lý Smart Crop trên video gốc
        crop_filter = ""
        if self._config.remixer.smart_crop.enabled:
            self._safe_progress(2, "Đang tính toán Smart Crop 9:16 (Face Tracking)...")
            crop_filter = cropper.calculate_crop_filter(src)
            logger.info(f"Smart Crop filter: {crop_filter}")

        # Build time ranges từ các điểm cắt
        times = sorted([(s["t"] if isinstance(s, dict) else s.cut_time) for s in scenes])

        cap = cv2.VideoCapture(src)
        total_dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
        cap.release()

        segments: list[tuple[float, float]] = []
        prev = 0.0
        min_len = self._config.scene_detection_precise.min_scene_len
        max_len = self._config.cutter.clipping.max_clip_duration # Lấy 5.0s từ config
        
        for t in times:
            duration = t - prev
            if duration >= min_len:
                # Nếu scene quá dài, chia nhỏ thành các đoạn max_len (5s)
                curr = prev
                while curr < t:
                    next_stop = min(curr + max_len, t)
                    # Chỉ thêm nếu đoạn cuối cùng đủ min_len, nếu không gộp vào đoạn trước
                    if t - next_stop < min_len and next_stop < t:
                        next_stop = t
                    segments.append((curr, next_stop))
                    curr = next_stop
            prev = t
            
        # Xử lý đoạn cuối cùng
        if total_dur - prev >= min_len:
            curr = prev
            while curr < total_dur:
                next_stop = min(curr + max_len, total_dur)
                if total_dur - next_stop < min_len and next_stop < total_dur:
                    next_stop = total_dur
                segments.append((curr, next_stop))
                curr = next_stop

        outputs, skipped = [], []
        total_seg = len(segments)

        for i, (start, end) in enumerate(segments):
            out_path = os.path.join(out_dir, f"{base}_clip{i+1:03d}.mp4")
            tmp_path = out_path + ".tmp.mp4"

            # Cấu hình GPU / Hardware Acceleration
            hw_accel = self._config.remixer.output.hardware_acceleration
            v_codec = "libx264"
            hw_flags = []
            
            if hw_accel == "nvenc":
                v_codec = "h264_nvenc"
                hw_flags = ["-hwaccel", "cuda"]
            elif hw_accel == "qsv":
                v_codec = "h264_qsv"
            elif hw_accel == "videotoolbox":
                v_codec = "h264_videotoolbox"

            # ✔ Đặt -i TRƯỚC -ss: frame-accurate cut, re-encode ngắn
            cmd = ["ffmpeg", "-y"] + hw_flags + [
                "-i", src,
                "-ss", f"{start:.3f}",
                "-to", f"{end:.3f}",
                "-c:v", v_codec,
                "-preset", "fast",
            ]
            
            # NVENC không hỗ trợ -crf theo kiểu chuẩn, nên phải dùng cq
            if hw_accel == "nvenc":
                cmd.extend(["-rc", "vbr", "-cq", "19", "-b:v", "5M", "-maxrate", "5M"])
            else:
                cmd.extend(["-crf", "18"])
                
            if crop_filter:
                cmd.extend(["-vf", crop_filter])

            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                tmp_path,
            ])
            result = subprocess.run(cmd, capture_output=True, timeout=600)

            if result.returncode != 0 or not os.path.exists(tmp_path):
                skipped.append((i+1, "ffmpeg error"))
                self._safe_progress(
                    int((i+1)/total_seg*100),
                    f"❌ Clip {i+1}: ffmpeg thất bại"
                )
                continue

            # ✔ Kiểm tra chất lượng bằng BlackFlashFilter
            quality = bf.check_segment(tmp_path)
            if quality.is_bad:
                reasons = ", ".join(quality.reasons)
                os.remove(tmp_path)
                skipped.append((i+1, reasons))
                self.txt_result.append(
                    f"  ⚠️ Clip {i+1:03d} bị loại: {reasons} "
                    f"(black={quality.black_ratio:.0%}, flash={quality.flash_rate:.1f}/s)"
                )
                self._safe_progress(int((i+1)/total_seg*100), f"⚠️ Clip {i+1} bị loại: {reasons}")
                continue

            # ✔ Clip hợp lệ → đổi tên
            os.rename(tmp_path, out_path)
            outputs.append({"path": out_path, "start": start, "end": end})
            self._safe_progress(
                int((i+1)/total_seg*100),
                f"✅ Clip {i+1}/{total_seg}: {os.path.basename(out_path)} "
                f"({end-start:.1f}s | bright={quality.avg_brightness:.0f})"
            )

        return {"outputs": outputs, "skipped": skipped, "total": total_seg}

    def _on_cut_done(self, result: dict) -> None:
        import os
        self.progress.setValue(100)
        outputs = result["outputs"]
        skipped = result["skipped"]
        total   = result["total"]

        self.txt_result.append(
            f"\n✅ Xuất xong: {len(outputs)}/{total} clips hợp lệ"
            f" | Bị loại: {len(skipped)} | Lưu tại: {self._output_dir}\n"
        )
        for item in outputs:
            p = item["path"]
            start = item["start"]
            end = item["end"]
            fname = os.path.basename(p)
            size_kb = os.path.getsize(p) // 1024
            self.txt_result.append(f"  📄 {fname}  ({size_kb:,} KB)")
            self.list_clips.addItem(f"✅ {fname}")
            
            # Save to Database
            try:
                # Find matching video in DB
                video = self._video_repo.get_by_video_id(os.path.basename(self._video_path))
                db_video_id = str(video["id"]) if video else os.path.splitext(os.path.basename(self._video_path))[0]
                
                self._clip_repo.insert(
                    video_id=db_video_id,
                    file_path=p,
                    start_time=start,
                    end_time=end,
                    duration=end - start,
                    source_folder=self._output_dir
                )
            except Exception as e:
                logger.error(f"Failed to save clip {fname} to DB: {e}")

        if skipped:
            self.txt_result.append(f"\n⚠️ Clips bị loại ({len(skipped)}):")
            for idx, reason in skipped:
                self.txt_result.append(f"  ❌ Clip {idx:03d}: {reason}")

        self.lbl_progress.setText(
            f"✅ {len(outputs)} clips → {self._output_dir}  "
            f"({'Bị loại: ' + str(len(skipped)) if skipped else 'Tất cả hợp lệ'})"
        )
        self.lbl_progress.setStyleSheet(
            f"color: {'#10B981' if not skipped else '#F59E0B'}; "
            "font-weight: bold; font-size: 12px;"
        )
