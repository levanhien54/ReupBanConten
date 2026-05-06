"""
Settings Page — API Keys, Proxy, LLM, ElevenLabs.
"""
from __future__ import annotations

import os
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFormLayout, QGroupBox,
    QComboBox, QScrollArea, QCheckBox, QFrame
)

from src.core.config import AppConfig
from src.ui.utils import Worker

_FIELD_STYLE = """
    QLineEdit, QComboBox {
        padding: 8px 10px;
        border: 1px solid #334155;
        border-radius: 4px;
        background-color: #0F172A;
        color: #F8FAFC;
        font-size: 13px;
    }
    QLineEdit:focus { border-color: #3B82F6; }
    QCheckBox { color: #94A3B8; spacing: 6px; }
"""

_GRP_STYLE = """
    QGroupBox {
        color: #3B82F6; font-weight: bold; font-size: 13px;
        border: 1px solid #334155; border-radius: 8px;
        margin-top: 10px; padding: 14px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 12px; }
    QLabel { color: #94A3B8; }
""" + _FIELD_STYLE


class SettingsPage(QWidget):
    """Trang cài đặt cấu hình hệ thống."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._threadpool = QThreadPool()
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(self._build_youtube_api_group())
        layout.addWidget(self._build_gemini_group())
        layout.addWidget(self._build_twelve_labs_group())
        layout.addWidget(self._build_proxy_group())
        layout.addWidget(self._build_llm_group())
        layout.addWidget(self._build_database_hardware_group())
        layout.addWidget(self._build_elevenlabs_group())
        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        main_layout.addWidget(self._build_action_bar())

    # ──────────── Nhóm YouTube API ────────────────────────────

    def _build_youtube_api_group(self) -> QGroupBox:
        grp = QGroupBox("📺 YouTube Data API v3")
        grp.setStyleSheet(_GRP_STYLE)
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.chk_api_enabled = QCheckBox("Dùng YouTube API v3 (chính xác hơn, cần API key)")
        self.chk_api_enabled.setChecked(self._config.downloader.youtube_api.enabled)
        form.addRow(self.chk_api_enabled)

        self.txt_yt_api_key = QLineEdit(
            self._config.downloader.youtube_api.api_key
            or os.getenv("YOUTUBE_API_KEY", "")
        )
        self.txt_yt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_yt_api_key.setPlaceholderText("AIza... (lấy tại console.developers.google.com)")

        self.btn_show_key = QPushButton("👁")
        self.btn_show_key.setFixedSize(32, 32)
        self.btn_show_key.setCheckable(True)
        self.btn_show_key.setStyleSheet(
            "background: #1E293B; color: white; border-radius: 4px;"
        )
        self.btn_show_key.toggled.connect(
            lambda on: self.txt_yt_api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )

        key_row = QHBoxLayout()
        key_row.addWidget(self.txt_yt_api_key, stretch=1)
        key_row.addWidget(self.btn_show_key)
        form.addRow("API Key:", key_row)

        # Test button
        self.btn_test_api = QPushButton("🔌 Test Kết Nối API")
        self.btn_test_api.setStyleSheet(
            "background: #1E40AF; color: white; padding: 8px 16px; "
            "border-radius: 4px; font-weight: bold;"
        )
        self.btn_test_api.clicked.connect(self._test_youtube_api)
        self.lbl_api_status = QLabel("")
        self.lbl_api_status.setStyleSheet("font-size: 12px;")

        test_row = QHBoxLayout()
        test_row.addWidget(self.btn_test_api)
        test_row.addWidget(self.lbl_api_status, stretch=1)
        form.addRow(test_row)

        # Guide
        lbl_help = QLabel(
            "💡 Tạo API key: "
            "console.developers.google.com → Enable YouTube Data API v3 → Credentials"
        )
        lbl_help.setStyleSheet("color: #64748B; font-size: 11px;")
        lbl_help.setWordWrap(True)
        form.addRow(lbl_help)

        return grp

    # ──────────── Nhóm Gemini API ────────────────────────────

    def _build_gemini_group(self) -> QGroupBox:
        grp = QGroupBox("♊ Google Gemini API")
        grp.setStyleSheet(_GRP_STYLE)
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.txt_gemini_key = self._password_field("GOOGLE_API_KEY")
        self.cmb_gemini_model = QComboBox()
        self.cmb_gemini_model.addItems(["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"])
        self.cmb_gemini_model.setCurrentText("gemini-1.5-flash")

        form.addRow("API Key:", self.txt_gemini_key)
        form.addRow("Model:", self.cmb_gemini_model)
        return grp

    # ──────────── Nhóm Twelve Labs ────────────────────────────

    def _build_twelve_labs_group(self) -> QGroupBox:
        grp = QGroupBox("🚀 Twelve Labs (Video Search)")
        grp.setStyleSheet(_GRP_STYLE)
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.txt_tl_key = self._password_field("TWELVELABS_API_KEY")
        self.txt_tl_index = QLineEdit(self._config.analyzer.twelve_labs.index_name)
        
        form.addRow("API Key:", self.txt_tl_key)
        form.addRow("Index Name:", self.txt_tl_index)
        return grp

    # ──────────── Nhóm Proxy ──────────────────────────────────

    def _build_proxy_group(self) -> QGroupBox:
        grp = QGroupBox("🌐 Proxy")
        grp.setStyleSheet(_GRP_STYLE)
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.chk_proxy_enabled = QCheckBox("Bật proxy (để tránh bị YouTube chặn)")
        self.chk_proxy_enabled.setChecked(self._config.downloader.proxy.enabled)
        form.addRow(self.chk_proxy_enabled)

        self.txt_proxy = QLineEdit(self._config.downloader.proxy.url or "")
        self.txt_proxy.setPlaceholderText("http://user:pass@host:port  hoặc  socks5://host:port")
        form.addRow("Proxy URL:", self.txt_proxy)

        # Test proxy
        self.btn_test_proxy = QPushButton("🔌 Test Proxy")
        self.btn_test_proxy.setStyleSheet(
            "background: #1E40AF; color: white; padding: 8px 16px; "
            "border-radius: 4px; font-weight: bold;"
        )
        self.btn_test_proxy.clicked.connect(self._test_proxy)
        self.lbl_proxy_status = QLabel("")
        self.lbl_proxy_status.setStyleSheet("font-size: 12px;")
        self.lbl_proxy_status.setWordWrap(True)

        test_row = QHBoxLayout()
        test_row.addWidget(self.btn_test_proxy)
        test_row.addWidget(self.lbl_proxy_status, stretch=1)
        form.addRow(test_row)

        # Hướng dẫn lỗi phổ biến
        lbl_help = QLabel(
            "⚠️ Nếu YouTube báo lỗi 429 hoặc yêu cầu xác minh → bật proxy.\n"
            "Proxy miễn phí thường không ổn định. Nên dùng proxy trả phí (Bright Data, Oxylabs...)."
        )
        lbl_help.setStyleSheet("color: #64748B; font-size: 11px;")
        lbl_help.setWordWrap(True)
        form.addRow(lbl_help)

        return grp

    # ──────────── Nhóm LLM ───────────────────────────────────

    def _build_llm_group(self) -> QGroupBox:
        grp = QGroupBox("🧠 Mô Hình Ngôn Ngữ (LLM)")
        grp.setStyleSheet(_GRP_STYLE)
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.cmb_provider = QComboBox()
        self.cmb_provider.addItems(["ollama", "openai", "anthropic", "gemini"])
        self.cmb_provider.setCurrentText(self._config.analyzer.llm.provider)

        self.txt_llm_model = QLineEdit(self._config.analyzer.llm.model)
        self.txt_openai_key = self._password_field("OPENAI_API_KEY")
        self.txt_anthropic_key = self._password_field("ANTHROPIC_API_KEY")

        form.addRow("Provider:", self.cmb_provider)
        form.addRow("Model (Ollama):", self.txt_llm_model)
        form.addRow("OpenAI API Key:", self.txt_openai_key)
        form.addRow("Anthropic API Key:", self.txt_anthropic_key)
        return grp

    # ──────────── Nhóm Database & Hardware ───────────────────

    def _build_database_hardware_group(self) -> QGroupBox:
        grp = QGroupBox("💾 Database & Hardware")
        grp.setStyleSheet(_GRP_STYLE)
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.cmb_db_provider = QComboBox()
        self.cmb_db_provider.addItems(["sqlite", "postgresql"])
        self.cmb_db_provider.setCurrentText("sqlite")

        self.cmb_gpu_accel = QComboBox()
        self.cmb_gpu_accel.addItems(["auto", "nvenc (NVIDIA)", "qsv (Intel)", "cpu (Software)"])
        self.cmb_gpu_accel.setCurrentText(self._config.remixer.output.hardware_acceleration)

        form.addRow("Database:", self.cmb_db_provider)
        form.addRow("GPU Accel:", self.cmb_gpu_accel)
        return grp

    # ──────────── Nhóm ElevenLabs ────────────────────────────

    def _build_elevenlabs_group(self) -> QGroupBox:
        grp = QGroupBox("🎙️ Voiceover (ElevenLabs)")
        grp.setStyleSheet(_GRP_STYLE)
        form = QFormLayout(grp)
        form.setSpacing(10)

        self.txt_eleven_key = self._password_field("ELEVENLABS_API_KEY")
        self.txt_eleven_voice = QLineEdit(
            self._config.voiceover.elevenlabs.default_voice or "Rachel"
        )
        form.addRow("API Key:", self.txt_eleven_key)
        form.addRow("Default Voice:", self.txt_eleven_voice)
        return grp

    # ──────────── Action Bar ──────────────────────────────────

    def _build_action_bar(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #0F172A; border-top: 1px solid #334155; }"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 10, 16, 10)

        self.btn_save = QPushButton("💾  Save All Settings")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: white;
                font-weight: bold; padding: 10px 24px;
                border-radius: 4px; font-size: 14px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_save.clicked.connect(self._save_all)

        self.lbl_save_status = QLabel("")
        self.lbl_save_status.setStyleSheet("color: #10B981; font-weight: bold;")

        row.addWidget(self.btn_save)
        row.addWidget(self.lbl_save_status)
        row.addStretch()
        return frame

    # ──────────── Helpers ─────────────────────────────────────

    def _password_field(self, env_key: str) -> QLineEdit:
        field = QLineEdit(os.getenv(env_key, ""))
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(f"{env_key}...")
        return field

    def _set_label_result(self, lbl: QLabel, ok: bool, msg: str) -> None:
        lbl.setText(("✅ " if ok else "❌ ") + msg)
        lbl.setStyleSheet(
            f"color: {'#10B981' if ok else '#EF4444'}; font-size: 12px;"
        )

    # ──────────── Test Actions ────────────────────────────────

    def _test_youtube_api(self) -> None:
        self.btn_test_api.setEnabled(False)
        self.lbl_api_status.setText("⏳ Đang kiểm tra...")
        self.lbl_api_status.setStyleSheet("color: #3B82F6; font-size: 12px;")

        key = self.txt_yt_api_key.text().strip()
        worker = Worker(self._task_test_api, key)
        worker.signals.result.connect(
            lambda res: self._set_label_result(self.lbl_api_status, res[0], res[1])
        )
        worker.signals.finished.connect(lambda: self.btn_test_api.setEnabled(True))
        self._threadpool.start(worker)

    def _task_test_api(self, key: str) -> tuple:
        from src.downloader.youtube_api import YoutubeApiClient
        from src.core.config import YoutubeApiConfig
        cfg = YoutubeApiConfig(api_key=key, enabled=True)
        client = YoutubeApiClient(cfg)
        return client.test_connection()

    def _test_proxy(self) -> None:
        proxy_url = self.txt_proxy.text().strip()
        if not proxy_url:
            self._set_label_result(self.lbl_proxy_status, False, "Chưa nhập proxy URL.")
            return

        self.btn_test_proxy.setEnabled(False)
        self.lbl_proxy_status.setText("⏳ Đang test proxy...")
        self.lbl_proxy_status.setStyleSheet("color: #3B82F6; font-size: 12px;")

        worker = Worker(self._task_test_proxy, proxy_url)
        worker.signals.result.connect(
            lambda res: self._set_label_result(self.lbl_proxy_status, res[0], res[1])
        )
        worker.signals.finished.connect(lambda: self.btn_test_proxy.setEnabled(True))
        self._threadpool.start(worker)

    def _task_test_proxy(self, proxy_url: str) -> tuple:
        from src.downloader.download_manager import DownloadManager
        mgr = DownloadManager(self._config.downloader)
        return mgr.test_proxy(proxy_url)

    # ──────────── Save ────────────────────────────────────────

    def _save_all(self) -> None:
        # YouTube API
        self._config.downloader.youtube_api.enabled = self.chk_api_enabled.isChecked()
        self._config.downloader.youtube_api.api_key = self.txt_yt_api_key.text().strip()
        os.environ["YOUTUBE_API_KEY"] = self._config.downloader.youtube_api.api_key

        # Proxy
        self._config.downloader.proxy.enabled = self.chk_proxy_enabled.isChecked()
        self._config.downloader.proxy.url = self.txt_proxy.text().strip() or None
        if self._config.downloader.proxy.enabled and self._config.downloader.proxy.url:
            self._config.downloader.ytdlp.proxy = self._config.downloader.proxy.url

        # LLM
        self._config.analyzer.llm.provider = self.cmb_provider.currentText()
        self._config.analyzer.llm.model = self.txt_llm_model.text()
        os.environ["OPENAI_API_KEY"] = self.txt_openai_key.text()
        os.environ["ANTHROPIC_API_KEY"] = self.txt_anthropic_key.text()

        # ElevenLabs
        os.environ["ELEVENLABS_API_KEY"] = self.txt_eleven_key.text()
        self._config.voiceover.elevenlabs.default_voice = self.txt_eleven_voice.text()

        # Gemini
        os.environ["GOOGLE_API_KEY"] = self.txt_gemini_key.text()
        
        # Twelve Labs
        os.environ["TWELVELABS_API_KEY"] = self.txt_tl_key.text()
        self._config.analyzer.twelve_labs.index_name = self.txt_tl_index.text()

        # Database & Hardware
        self._config.remixer.output.hardware_acceleration = self.cmb_gpu_accel.currentText().split(" ")[0]

        # Cập nhật file .env để lưu vĩnh viễn các API Keys
        self._update_dotenv()

        self.lbl_save_status.setText("✅ Đã lưu tất cả cài đặt.")

    def _update_dotenv(self) -> None:
        """Cập nhật các biến môi trường vào file .env."""
        env_path = ".env"
        env_data = {}
        
        # Đọc .env hiện tại nếu có
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        env_data[key.strip()] = val.strip()

        # Cập nhật các keys từ UI
        env_data["YOUTUBE_API_KEY"] = self.txt_yt_api_key.text().strip()
        env_data["OPENAI_API_KEY"] = self.txt_openai_key.text().strip()
        env_data["ANTHROPIC_API_KEY"] = self.txt_anthropic_key.text().strip()
        env_data["GOOGLE_API_KEY"] = self.txt_gemini_key.text().strip()
        env_data["TWELVELABS_API_KEY"] = self.txt_tl_key.text().strip()
        env_data["ELEVENLABS_API_KEY"] = self.txt_eleven_key.text().strip()

        # Ghi lại file .env
        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in env_data.items():
                if v:  # Chỉ lưu các key có giá trị
                    f.write(f"{k}={v}\n")
