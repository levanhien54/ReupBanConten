"""
Scanner Page — Smart URL: tự phân tích kênh vs video đơn lẻ.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QCheckBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QAbstractItemView, QProgressBar, QFileDialog, QStackedWidget,
)
from PySide6.QtGui import QColor

from src.core.config import AppConfig
from src.ui.utils import Worker

_SORT_OPTIONS = {
    "📅 Mới nhất":        "newest",
    "🔥 Nhiều view nhất": "most_viewed",
    "⭐ Đánh giá cao":    "rating",
}
_QUALITY_OPTIONS = [
    "best[height<=1080]", "best[height<=720]",
    "best[height<=480]",  "bestvideo+bestaudio",
]
_ERR_COLORS = {
    "BLOCKED": "#EF4444", "PROXY_FAIL": "#F97316",
    "RATE_LIMIT": "#EAB308", "GEO_BLOCK": "#A855F7",
    "UNAVAILABLE": "#64748B", "NO_KEY": "#3B82F6",
    "DEFAULT": "#EF4444",
}


class ScannerPage(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._pool = QThreadPool()
        self._scan_results: list = []
        self._out_dir: str = str(config.storage.downloads)
        self._url_info = None
        from src.core.database import get_database, VideoRepository
        self._video_repo = VideoRepository(get_database())
        self._setup_ui()

    # ── Setup ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addWidget(self._build_input_bar())
        root.addWidget(self._build_type_badge())
        root.addWidget(self._build_options_stack())
        root.addWidget(self._build_error_banner())
        root.addWidget(self._build_table())
        root.addWidget(self._build_footer())

    # ── Input bar (URL + nút Go) ──────────────────────────────

    def _build_input_bar(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet("""
            QFrame { background:#1E293B; border-radius:8px; }
            QLineEdit {
                padding:10px; border:1px solid #334155; border-radius:4px;
                background:#0F172A; color:#F8FAFC; font-size:14px;
            }
            QPushButton {
                background:#3B82F6; color:white; font-weight:bold;
                padding:10px 22px; border-radius:4px; font-size:14px;
            }
            QPushButton:hover { background:#2563EB; }
            QPushButton:disabled { background:#334155; color:#64748B; }
        """)
        row = QHBoxLayout(f)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(10)

        lbl = QLabel("URL:")
        lbl.setStyleSheet("color:#94A3B8; font-weight:bold;")

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText(
            "Dán link kênh hoặc video: youtube.com/@name  ·  youtu.be/xxx  ·  tiktok.com/@user/video/..."
        )
        self.txt_url.returnPressed.connect(self._on_go)
        # Auto-detect khi người dùng gõ (debounce 600ms)
        self._detect_timer = QTimer()
        self._detect_timer.setSingleShot(True)
        self._detect_timer.setInterval(600)
        self._detect_timer.timeout.connect(self._auto_detect)
        self.txt_url.textChanged.connect(lambda: self._detect_timer.start())

        self.btn_go = QPushButton("▶  Phân Tích")
        self.btn_go.clicked.connect(self._on_go)

        row.addWidget(lbl)
        row.addWidget(self.txt_url, 1)
        row.addWidget(self.btn_go)
        return f

    # ── Type badge ────────────────────────────────────────────

    def _build_type_badge(self) -> QFrame:
        self.badge_frame = QFrame()
        self.badge_frame.setFixedHeight(40)
        self.badge_frame.setStyleSheet(
            "QFrame { background:#1E293B; border-radius:6px; }"
        )
        row = QHBoxLayout(self.badge_frame)
        row.setContentsMargins(14, 0, 14, 0)

        self.lbl_badge = QLabel("Nhập URL để bắt đầu...")
        self.lbl_badge.setStyleSheet("color:#64748B; font-size:13px;")

        self.lbl_mode = QLabel("")
        self.lbl_mode.setStyleSheet(
            "font-weight:bold; font-size:12px; color:#F8FAFC;"
            "background:#1E40AF; border-radius:10px; padding:3px 14px;"
        )

        row.addWidget(self.lbl_badge)
        row.addStretch()
        row.addWidget(self.lbl_mode)
        return self.badge_frame

    # ── Options stack (channel vs single) ────────────────────

    def _build_options_stack(self) -> QStackedWidget:
        self.opts_stack = QStackedWidget()
        self.opts_stack.setFixedHeight(52)
        self.opts_stack.addWidget(self._build_channel_opts())   # idx 0
        self.opts_stack.addWidget(self._build_single_opts())    # idx 1
        return self.opts_stack

    def _build_channel_opts(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet("""
            QFrame { background:#1E293B; border-radius:8px; }
            QSpinBox, QComboBox {
                padding:5px 8px; background:#0F172A; color:#F8FAFC;
                border:1px solid #334155; border-radius:4px;
            }
            QCheckBox { color:#94A3B8; spacing:6px; }
            QLabel { color:#94A3B8; font-weight:bold; }
        """)
        row = QHBoxLayout(f)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(14)

        self.cmb_source = QComboBox()
        self.cmb_source.addItems(["🌐 YouTube API v3", "🔧 yt-dlp"])
        self.cmb_source.setFixedWidth(160)

        self.spn_scan = QSpinBox()
        self.spn_scan.setRange(1, 500)
        self.spn_scan.setValue(self._config.downloader.max_videos_per_channel)

        self.spn_dl = QSpinBox()
        self.spn_dl.setRange(1, 200)
        self.spn_dl.setValue(10)

        self.cmb_sort = QComboBox()
        for lbl in _SORT_OPTIONS: self.cmb_sort.addItem(lbl)
        self.cmb_sort.setFixedWidth(180)

        self.chk_shorts = QCheckBox("Shorts (<60s)")
        self.chk_shorts.setChecked(self._config.downloader.filter_shorts_only)

        for w, lbl in [
            (self.cmb_source, "Nguồn:"),
            (self.spn_scan,   "Quét:"),
            (self.spn_dl,     "Tải:"),
            (self.cmb_sort,   "Sắp xếp:"),
        ]:
            row.addWidget(QLabel(lbl))
            row.addWidget(w)
        row.addWidget(self.chk_shorts)
        
        self.chk_auto_pipeline = QCheckBox("🚀 Auto-Pipeline (Norm + PreCut)")
        self.chk_auto_pipeline.setChecked(True)
        self.chk_auto_pipeline.setStyleSheet("color:#10B981; font-weight:bold;")
        row.addWidget(self.chk_auto_pipeline)
        
        row.addStretch()
        return f

    def _build_single_opts(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet("""
            QFrame { background:#1E293B; border-radius:8px; }
            QComboBox {
                padding:5px 8px; background:#0F172A; color:#F8FAFC;
                border:1px solid #334155; border-radius:4px;
            }
            QLabel { color:#94A3B8; font-weight:bold; }
        """)
        row = QHBoxLayout(f)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(14)

        row.addWidget(QLabel("Chất lượng:"))
        self.cmb_quality = QComboBox()
        self.cmb_quality.addItems(_QUALITY_OPTIONS)
        self.cmb_quality.setCurrentIndex(1)
        self.cmb_quality.setFixedWidth(220)
        row.addWidget(self.cmb_quality)

        tip = QLabel("✅ Hỗ trợ 1000+ trang  |  📄 Phụ đề .SRT tự động tải kèm để phân tích AI")
        tip.setStyleSheet("color:#64748B; font-size:12px;")
        row.addWidget(tip)
        row.addStretch()
        return f

    # ── Error banner ──────────────────────────────────────────

    def _build_error_banner(self) -> QFrame:
        self.err_banner = QFrame()
        self.err_banner.setVisible(False)
        self.err_banner.setFixedHeight(44)
        self.err_banner.setStyleSheet(
            "QFrame { background:#7F1D1D; border-radius:7px; }"
        )
        row = QHBoxLayout(self.err_banner)
        row.setContentsMargins(14, 0, 14, 0)
        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet("color:#FCA5A5; font-size:13px; font-weight:bold;")
        self.lbl_err.setWordWrap(True)
        btn_x = QPushButton("✕")
        btn_x.setFixedSize(22, 22)
        btn_x.setStyleSheet("background:transparent; color:#FCA5A5; border:none;")
        btn_x.clicked.connect(lambda: self.err_banner.setVisible(False))
        row.addWidget(QLabel("⚠️"))
        row.addWidget(self.lbl_err, 1)
        row.addWidget(btn_x)
        return self.err_banner

    # ── Results table ─────────────────────────────────────────

    def _build_table(self) -> QTableWidget:
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["#", "ID / Platform", "Tiêu đề", "Thời lượng", "Lượt xem", "Trạng thái"]
        )
        h = self.table.horizontalHeader()
        for i, m in enumerate([
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
        ]):
            h.setSectionResizeMode(i, m)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background:#1E293B; alternate-background-color:#162032;
                border:1px solid #334155; border-radius:8px;
                color:#F8FAFC; gridline-color:#1E293B;
            }
            QTableWidget::item:selected { background:#3B82F6; }
            QHeaderView::section {
                background:#0F172A; color:#64A4FB;
                padding:6px; border:none; font-weight:bold; font-size:13px;
            }
        """)
        return self.table

    # ── Footer (dir + progress + action btn) ─────────────────

    def _build_footer(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        # Row 1: dir + progress + btn
        row1 = QFrame()
        row1.setStyleSheet("QFrame { background:#1E293B; border-radius:8px; }")
        r = QHBoxLayout(row1)
        r.setContentsMargins(14, 10, 14, 10)
        r.setSpacing(10)

        lbl_d = QLabel("Lưu:")
        lbl_d.setStyleSheet("color:#94A3B8; font-weight:bold;")
        self.lbl_dir = QLabel(self._out_dir)
        self.lbl_dir.setStyleSheet(
            "color:#10B981; font-size:12px; border:1px solid #334155;"
            "border-radius:4px; padding:3px 8px;"
        )
        btn_dir = QPushButton("📁")
        btn_dir.setFixedSize(30, 30)
        btn_dir.setStyleSheet("background:#334155; color:white; border-radius:4px;")
        btn_dir.clicked.connect(self._choose_dir)

        self.main_progress = QProgressBar()
        self.main_progress.setRange(0, 100)
        self.main_progress.setValue(0)
        self.main_progress.setFixedHeight(10)
        self.main_progress.setStyleSheet("""
            QProgressBar { background:#0F172A; border:1px solid #334155; border-radius:4px; }
            QProgressBar::chunk { background:#10B981; border-radius:4px; }
        """)

        self.btn_action = QPushButton("▶  Bắt Đầu")
        self.btn_action.setEnabled(False)
        self.btn_action.setMinimumWidth(160)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background:#10B981; color:white; font-weight:bold;
                padding:10px 18px; border-radius:4px; font-size:13px;
            }
            QPushButton:hover { background:#059669; }
            QPushButton:disabled { background:#334155; color:#64748B; }
        """)
        self.btn_action.clicked.connect(self._on_action)

        r.addWidget(lbl_d)
        r.addWidget(self.lbl_dir, 1)
        r.addWidget(btn_dir)
        r.addWidget(self.main_progress, 2)
        r.addWidget(self.btn_action)
        col.addWidget(row1)

        # Row 2: status line
        self.lbl_status = QLabel("Nhập URL bất kỳ — hệ thống tự phân tích.")
        self.lbl_status.setStyleSheet("color:#64748B; font-size:13px;")
        col.addWidget(self.lbl_status)
        return w

    # ── Auto-detect ───────────────────────────────────────────

    def _auto_detect(self) -> None:
        from src.downloader.url_analyzer import analyze_url, UrlType
        url = self.txt_url.text().strip()
        if not url:
            self.lbl_badge.setText("💡 Nhập URL kênh hoặc link video bất kỳ — hệ thống tự phân tích")
            self.lbl_badge.setStyleSheet("color:#64748B; font-size:13px;")
            self.lbl_mode.setText("")
            self.btn_action.setEnabled(False)
            return

        info = analyze_url(url)
        self._url_info = info

        if info.url_type.value in ("single_video", "playlist"):
            self.opts_stack.setCurrentIndex(1)
            mode_txt = f"{info.icon} {info.label} — Tải ngay"
            self.btn_action.setText("⬇️  Tải Video")
            self.btn_action.setStyleSheet(self.btn_action.styleSheet().replace(
                "#10B981", "#1D4ED8"
            ))
        else:  # channel / unknown → channel flow
            self.opts_stack.setCurrentIndex(0)
            mode_txt = f"{info.icon} {info.label} — Quét kênh"
            self.btn_action.setText("🔍 Quét & Tải")
            self.btn_action.setStyleSheet(self.btn_action.styleSheet().replace(
                "#1D4ED8", "#10B981"
            ))

        self.lbl_badge.setText(f"Đã nhận diện: {info.platform.upper()}")
        self.lbl_badge.setStyleSheet("color:#94A3B8; font-size:13px;")
        self.lbl_mode.setText(mode_txt)
        self.btn_action.setEnabled(True)

    # ── Master action ─────────────────────────────────────────

    def _on_go(self) -> None:
        self._auto_detect()
        if self._url_info:
            self._on_action()

    def _on_action(self) -> None:
        from src.downloader.url_analyzer import UrlType
        if not self._url_info:
            return
        url = self.txt_url.text().strip()
        if self._url_info.url_type in (UrlType.SINGLE_VIDEO, UrlType.PLAYLIST):
            self._start_single_download(url)
        else:
            self._start_channel_scan(url)

    # ── Channel flow ──────────────────────────────────────────

    def _start_channel_scan(self, url: str) -> None:
        self.btn_action.setEnabled(False)
        self.btn_go.setEnabled(False)
        self.table.setRowCount(0)
        self._scan_results = []
        self.main_progress.setValue(5)
        self._set_status(f"Đang quét kênh: {url[:60]}...", "info")
        self.err_banner.setVisible(False)

        use_api = self.cmb_source.currentIndex() == 0
        sort_key = _SORT_OPTIONS[self.cmb_sort.currentText()]
        max_vid = self.spn_scan.value()
        shorts  = self.chk_shorts.isChecked()

        worker = Worker(self._task_scan, url, max_vid, sort_key, shorts, use_api)
        worker.signals.result.connect(self._on_scan_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(self._reset_buttons)
        self._pool.start(worker)

    def _task_scan(self, url, max_vid, sort_key, shorts, use_api):
        if use_api and self._config.downloader.youtube_api.enabled:
            from src.downloader.youtube_api import (
                YoutubeApiClient, SortOrder,
                QuotaExceededError, ApiBlockedError, InvalidApiKeyError, NetworkError,
            )
            order_map = {"newest": SortOrder.NEWEST, "most_viewed": SortOrder.MOST_VIEWED,
                         "rating": SortOrder.RATING}
            client = YoutubeApiClient(
                self._config.downloader.youtube_api,
                self._config.downloader.proxy,
            )
            try:
                r = client.get_channel_videos(
                    url, max_count=max_vid,
                    sort_by=order_map.get(sort_key, SortOrder.NEWEST),
                    shorts_only=shorts,
                    min_duration_s=self._config.downloader.min_video_duration,
                    max_duration_s=self._config.downloader.max_video_duration,
                )
            except (QuotaExceededError, ApiBlockedError, InvalidApiKeyError, NetworkError) as e:
                code = getattr(e, "error_code", "DEFAULT")
                raise RuntimeError(f"__CODE__{code}__{e}") from e
            if not r.success:
                raise RuntimeError(f"__CODE__{r.error_code}__{r.error}")
            return [{"video_id": v.video_id, "title": v.title, "duration": v.duration_s,
                     "views": v.view_count, "url": v.url} for v in r.videos]
        else:
            from src.downloader.channel_scanner import ChannelScanner
            scanner = ChannelScanner(self._config.downloader)
            vids = scanner.scan(url, max_count=max_vid, shorts_only=shorts, sort_by=sort_key)
            return [{"video_id": v.video_id, "title": v.title or "Untitled",
                     "duration": v.duration, "views": v.view_count or 0, "url": v.url}
                    for v in vids]

    def _on_scan_done(self, videos: list) -> None:
        self._scan_results = videos
        dl_lim = self.spn_dl.value()
        self.table.setRowCount(len(videos))
        for row, v in enumerate(videos):
            will_dl = row < dl_lim
            items = [
                QTableWidgetItem(str(row + 1)),
                QTableWidgetItem(v["video_id"]),
                QTableWidgetItem(v["title"]),
                QTableWidgetItem(f"{v['duration']}s" if v.get("duration") else "?"),
                QTableWidgetItem(f"{v['views']:,}" if v.get("views") else "0"),
                QTableWidgetItem("⬇️ Queue" if will_dl else "—"),
            ]
            for col, it in enumerate(items):
                it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if will_dl:
                    it.setForeground(QColor("#67E8F9"))
                self.table.setItem(row, col, it)

        queued = min(dl_lim, len(videos))
        self._set_status(
            f"✅ {len(videos)} video | Sẽ tải: {queued} | "
            f"Sắp xếp: {self.cmb_sort.currentText()}", "success"
        )
        self.main_progress.setValue(50)

        if videos:
            self.btn_action.setText("⬇️  Tải Ngay")
            self.btn_action.setEnabled(True)
            self._url_info = None   # next click → download mode

    # ── Single download flow ──────────────────────────────────

    def _start_single_download(self, url: str) -> None:
        # Nếu đã có kết quả scan, tải batch đó
        if self._scan_results:
            urls = [v["url"] for v in self._scan_results[:self.spn_dl.value()]]
        else:
            urls = [url]

        self.btn_action.setEnabled(False)
        self.btn_go.setEnabled(False)
        self.main_progress.setValue(3)
        self._set_status(f"Đang tải {len(urls)} video...", "info")
        self.err_banner.setVisible(False)

        quality = self.cmb_quality.currentText()
        worker = Worker(self._task_download, urls, quality)
        worker.signals.result.connect(self._on_download_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(self._reset_buttons)
        self._pool.start(worker)

    def _task_download(self, urls: list[str], quality: str):
        from src.downloader.download_manager import DownloadManager
        total = len(urls)
        done = [0]

        def _prog(p) -> None:
            if p.status in ("done", "error"):
                done[0] += 1
                self.main_progress.setValue(int(done[0] / total * 100))
            # update table
            self._update_table_row(p)
            # if single video, show progress %
            if total == 1 and p.status == "downloading":
                self._set_status(
                    f"⬇️  {p.title[:50]}  {p.percent:.0f}%  {p.speed_kbps:.0f} KB/s", "info"
                )

        mgr = DownloadManager(self._config.downloader)
        return mgr.download_batch(urls, self._out_dir, on_progress=_prog, quality=quality)

    def _update_table_row(self, p) -> None:
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 1)
            if it and it.text() == p.video_id:
                st = self.table.item(row, 5)
                if st:
                    if p.status == "done":
                        st.setText("✅ Done")
                        st.setForeground(QColor("#10B981"))
                    elif p.status == "error":
                        code = p.error_code.value if p.error_code else "ERR"
                        st.setText(f"❌ {code}")
                        st.setForeground(QColor("#EF4444"))
                break

    def _on_download_done(self, result) -> None:
        from src.downloader.download_manager import DownloadResult
        r: DownloadResult = result
        self.main_progress.setValue(100)
        if r.failed > 0:
            err = r.errors[0]
            code = (err.error_code.value if err.error_code else "DEFAULT")
            self._show_error(err.error_msg or "Lỗi tải video", code)
        self._set_status(
            f"✅ Hoàn tất: {r.success}/{r.total}  ({r.failed} lỗi)  →  {self._out_dir}",
            "success" if r.failed == 0 else "warning"
        )
        
        # Auto-Pipeline
        if self.chk_auto_pipeline.isChecked() and r.success > 0:
            success_files = [res.file_path for res in r.results if res.status == "done"]
            if success_files:
                self._set_status(f"🚀 Đang chạy Auto-Pipeline cho {len(success_files)} video...", "info")
                worker = Worker(self._run_auto_pipeline, success_files)
                worker.signals.result.connect(lambda msg: self._set_status(f"✨ {msg}", "success"))
                self._pool.start(worker)

    # ── Error handler ─────────────────────────────────────────

    def _on_error(self, err_tuple: tuple) -> None:
        import re
        _, value, _ = err_tuple
        msg = str(value)
        code = "DEFAULT"
        m = re.match(r"__CODE__(\w+)__(.*)", msg, re.DOTALL)
        if m:
            code = m.group(1)
            msg  = m.group(2)
        friendly = {
            "QUOTA":       "Hết quota YouTube API hôm nay. Thử lại sau 24h.",
            "BLOCKED":     "YouTube chặn. Thêm cookies hoặc dùng proxy (Settings).",
            "INVALID_KEY": "API Key không hợp lệ. Vào Settings → YouTube API.",
            "NO_KEY":      "Chưa có API Key. Vào Settings → YouTube API hoặc chọn nguồn yt-dlp.",
            "PROXY_FAIL":  "Proxy không hoạt động. Kiểm tra Settings → Proxy.",
            "RATE_LIMIT":  "Quá nhiều request (429). Chờ vài phút hoặc đổi proxy.",
            "GEO_BLOCK":   "Video bị chặn theo khu vực. Dùng proxy nước ngoài.",
            "UNAVAILABLE": "Video không khả dụng (private / đã xóa).",
        }
        self._show_error(friendly.get(code, msg[:250]), code)
        self._set_status(f"❌ Lỗi: {code}", "error")

    def _show_error(self, msg: str, code: str = "DEFAULT") -> None:
        color = _ERR_COLORS.get(code, _ERR_COLORS["DEFAULT"])
        self.err_banner.setStyleSheet(
            f"QFrame {{ background:{color}40; border:1px solid {color}; border-radius:7px; }}"
        )
        self.lbl_err.setText(msg)
        self.err_banner.setVisible(True)

    # ── Helpers ───────────────────────────────────────────────

    def _reset_buttons(self) -> None:
        self.btn_go.setEnabled(True)
        self.btn_action.setEnabled(True)
        if self._scan_results:
            self.btn_action.setText("⬇️  Tải Ngay")
        else:
            self.btn_action.setText("▶  Go")

    def _choose_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu")
        if path:
            self._out_dir = path
            self.lbl_dir.setText(path)

    def _run_auto_pipeline(self, file_paths: list[str]) -> str:
        """Chạy Normalize + PreCut ngầm."""
        from src.preprocessor.normalizer import VideoNormalizer
        from src.preprocessor.pre_cutter import PreCutter
        
        norm = VideoNormalizer(self._config.remixer.output)
        cutter = PreCutter(self._config.cutter)
        
        count = 0
        for path in file_paths:
            try:
                # 1. Normalize
                norm_path = norm.normalize(path)
                # 2. PreCut
                cutter.process(norm_path)
                count += 1
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).error(f"Auto-Pipeline failed for {path}: {e}")
                
        return f"Pipeline hoàn tất cho {count}/{len(file_paths)} video."

    def _set_status(self, text: str, level: str = "info") -> None:
        colors = {"success": "#10B981", "info": "#3B82F6",
                  "warning": "#F59E0B", "error": "#EF4444"}
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(
            f"color:{colors.get(level, '#64748B')}; font-size:13px;"
        )
