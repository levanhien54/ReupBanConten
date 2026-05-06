"""
Dashboard Page.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QListWidget, QListWidgetItem
)

from src.core.config import AppConfig
from src.ui.utils import Worker


class DashboardPage(QWidget):
    """Trang tổng quan hệ thống."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._threadpool = QThreadPool()
        import os
        from src.core.database import get_database, VideoRepository, ClipRepository
        db = get_database()
        self._video_repo = VideoRepository(db)
        self._clip_repo = ClipRepository(db)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # ── Banner trạng thái yt-dlp ──────────────────────────────
        self.update_banner = QFrame()
        self.update_banner.setFixedHeight(46)
        self._set_banner("checking")
        banner_layout = QHBoxLayout(self.update_banner)
        banner_layout.setContentsMargins(16, 0, 16, 0)

        self.lbl_update_icon = QLabel("🔄")
        self.lbl_update_icon.setStyleSheet("font-size: 18px;")

        self.lbl_update_status = QLabel("Đang kiểm tra cập nhật yt-dlp...")
        self.lbl_update_status.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: bold;")

        banner_layout.addWidget(self.lbl_update_icon)
        banner_layout.addWidget(self.lbl_update_status)
        banner_layout.addStretch()

        layout.addWidget(self.update_banner)

        # ── Hàng thống kê ────────────────────────────────────────
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)

        self.card_videos = self._create_stat_card("Total Videos", "0", "📥")
        self.card_clips  = self._create_stat_card("Clips Extracted", "0", "✂️")
        self.card_remixes = self._create_stat_card("Remixes Output", "0", "🎬")

        stats_layout.addWidget(self.card_videos)
        stats_layout.addWidget(self.card_clips)
        stats_layout.addWidget(self.card_remixes)
        layout.addLayout(stats_layout)

        # ── Activity area ─────────────────────────────────────────
        activity_frame = QFrame()
        activity_frame.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border-radius: 10px;
                border: 1px solid #334155;
            }
        """)
        activity_layout = QVBoxLayout(activity_frame)
        lbl_activity = QLabel("Recent Activities")
        lbl_activity.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 14px;")
        activity_layout.addWidget(lbl_activity)
        
        self.list_activity = QListWidget()
        self.list_activity.setStyleSheet("""
            QListWidget { background: transparent; border: none; color: #F8FAFC; font-size: 13px; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #334155; }
        """)
        activity_layout.addWidget(self.list_activity)

        layout.addWidget(activity_frame)

        layout.addWidget(activity_frame)

        layout.setStretchFactor(stats_layout, 1)
        layout.setStretchFactor(activity_frame, 3)

        # Cập nhật số liệu thực tế
        self._refresh_stats()
        self._refresh_activities()
        
        # Chạy update ngầm ngay khi Dashboard mở
        self._start_ytdlp_update()

    def _refresh_stats(self) -> None:
        """Cập nhật số liệu từ database."""
        try:
            import os
            v_count = len(self._video_repo.list_all(limit=10000))
            c_count = len(self._clip_repo.list_all(limit=50000))
            # Remix count giả định từ folder output
            r_count = 0 
            if os.path.exists(self._config.storage.outputs):
                r_count = len([f for f in os.listdir(self._config.storage.outputs) if f.endswith(".mp4")])
            
            self._update_card_value(self.card_videos, str(v_count))
            self._update_card_value(self.card_clips, str(c_count))
            self._update_card_value(self.card_remixes, str(r_count))
        except Exception as e:
            from src.core.logging import get_logger
            get_logger(__name__).error(f"Error refreshing stats: {e}")

    def _update_card_value(self, card: QFrame, value: str) -> None:
        """Helper để cập nhật giá trị trong stat card."""
        for label in card.findChildren(QLabel):
            if "font-size: 42px" in label.styleSheet():
                label.setText(value)
                break

    def _refresh_activities(self) -> None:
        """Lấy hoạt động gần đây từ DB."""
        try:
            self.list_activity.clear()
            # Lấy 5 video mới nhất
            videos = self._video_repo.list_all(limit=5)
            for v in videos:
                item = QListWidgetItem(f"📥 Download: {v['title'][:60]}...")
                self.list_activity.addItem(item)
                
            # Lấy 5 clips mới nhất
            clips = self._clip_repo.list_all(limit=5)
            for c in clips:
                fname = os.path.basename(c['file_path'])
                item = QListWidgetItem(f"✂️ Extracted: {fname}")
                self.list_activity.addItem(item)
                
            if self.list_activity.count() == 0:
                self.list_activity.addItem("Chưa có hoạt động nào.")
        except Exception as e:
            from src.core.logging import get_logger
            get_logger(__name__).error(f"Error refreshing activities: {e}")

    # ── Helpers ───────────────────────────────────────────────────

    def _set_banner(self, state: str) -> None:
        colors = {
            "checking": "#1E40AF",   # xanh đậm
            "ok":       "#064E3B",   # xanh lá đậm
            "updated":  "#065F46",   # lá sáng hơn
            "error":    "#7F1D1D",   # đỏ
        }
        color = colors.get(state, "#1E293B")
        self.update_banner.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
        """)

    def _start_ytdlp_update(self) -> None:
        from src.core.updater import update_ytdlp
        worker = Worker(update_ytdlp)
        worker.signals.result.connect(self._on_update_done)
        worker.signals.error.connect(self._on_update_error)
        self._threadpool.start(worker)

    def _on_update_done(self, result: object) -> None:
        from src.core.updater import UpdateResult
        r: UpdateResult = result  # type: ignore[assignment]

        if r.success:
            if r.updated:
                self._set_banner("updated")
                self.lbl_update_icon.setText("⬆️")
                self.lbl_update_status.setText(
                    f"yt-dlp đã được cập nhật: {r.old_version} → {r.new_version}"
                )
            else:
                self._set_banner("ok")
                self.lbl_update_icon.setText("✅")
                self.lbl_update_status.setText(
                    f"yt-dlp {r.new_version} — đang dùng bản mới nhất"
                )
        else:
            self._on_update_error(None)

    def _on_update_error(self, _err: object) -> None:
        self._set_banner("error")
        self.lbl_update_icon.setText("⚠️")
        self.lbl_update_status.setText(
            "Không thể cập nhật yt-dlp. Ứng dụng vẫn hoạt động bình thường."
        )

    # ── Stat card ─────────────────────────────────────────────────

    def _create_stat_card(self, title: str, value: str, icon: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border-radius: 10px;
                border: 1px solid #334155;
            }
            QFrame:hover { border: 1px solid #3B82F6; }
        """)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 20, 20, 20)

        top = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 16px; color: #94A3B8; font-weight: bold;")
        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 24px;")

        top.addWidget(lbl_title)
        top.addStretch()
        top.addWidget(lbl_icon)
        vbox.addLayout(top)
        vbox.addSpacing(10)

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet("font-size: 42px; font-weight: 900; color: #F8FAFC;")
        vbox.addWidget(lbl_val)

        return card
