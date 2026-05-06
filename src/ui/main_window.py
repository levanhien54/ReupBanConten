"""
Main Window Layout.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QPushButton, QLabel, QFrame, QSplitter
)

from src.core.config import AppConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Giao diện chính của ứng dụng ReupBanConten."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        
        self.setWindowTitle(f"{config.name} v{config.version} - AI Video Remix Engine")
        self.setMinimumSize(1200, 800)
        
        # Style chung cho Window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F172A;
            }
        """)

        self._setup_ui()
        logger.info("Main window initialized.")

    def _setup_ui(self) -> None:
        # Widget trung tâm
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar (Trái)
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        # 2. Main Content Area (Phải)
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # Header (Top bar)
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("Dashboard")
        self.lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #F8FAFC;")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        content_layout.addLayout(header_layout)

        # Splitter cho Content và Log Console
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Stacked Widget chứa các trang
        self.stacked_widget = QStackedWidget()
        self._setup_pages()
        splitter.addWidget(self.stacked_widget)
        
        # Log Console (Bottom)
        self.log_console = self._create_log_console()
        splitter.addWidget(self.log_console)
        
        # Set tỷ lệ Splitter: 75% nội dung, 25% log
        splitter.setSizes([750, 250])
        
        content_layout.addWidget(splitter)
        main_layout.addWidget(content_wrapper)
        
        # Tỷ lệ Layout chính
        main_layout.setStretchFactor(self.sidebar, 1)
        main_layout.setStretchFactor(content_wrapper, 5)

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border-right: 1px solid #334155;
            }
            QPushButton {
                text-align: left;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                color: #94A3B8;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #F8FAFC;
            }
            QPushButton:checked {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(10)
        
        # Logo / Tên App
        lbl_logo = QLabel(f"🎬 {self._config.name}")
        lbl_logo.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: 900; padding-bottom: 20px;")
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_logo)
        
        # Menu Items
        self.nav_buttons = []
        menus = [
            ("📊 Dashboard", 0),
            ("🔍 Scanner", 1),
            ("✂️ Cutter", 2),
            ("🧠 Analyzer", 3),
            ("🎬 Remixer", 4),
            ("⚙️ Settings", 5)
        ]
        
        for text, index in menus:
            btn = QPushButton(text)
            btn.setCheckable(True)
            if index == 0:
                btn.setChecked(True)
            
            # Kết nối event
            btn.clicked.connect(lambda checked, idx=index, b=btn, t=text: self._on_nav_clicked(idx, b, t))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
            
        layout.addStretch()
        return sidebar

    def _setup_pages(self) -> None:
        """Khởi tạo và gán các trang vào Stacked Widget."""
        from src.ui.pages.dashboard import DashboardPage
        from src.ui.pages.scanner import ScannerPage

        # Page 0: Dashboard
        self.page_dashboard = DashboardPage(self._config)
        self.stacked_widget.addWidget(self.page_dashboard)

        # Page 1: Scanner
        self.page_scanner = ScannerPage(self._config)
        self.stacked_widget.addWidget(self.page_scanner)

        # Page 2: Cutter  ← đã chuyển lên trước Analyzer
        from src.ui.pages.cutter import CutterPage
        self.page_cutter = CutterPage(self._config)
        self.stacked_widget.addWidget(self.page_cutter)

        # Page 3: Analyzer
        from src.ui.pages.analyzer import AnalyzerPage
        self.page_analyzer = AnalyzerPage(self._config)
        self.stacked_widget.addWidget(self.page_analyzer)

        # Page 4: Remixer
        from src.ui.pages.remixer import RemixerPage
        self.page_remixer = RemixerPage(self._config)
        self.stacked_widget.addWidget(self.page_remixer)

        # Page 5: Settings
        from src.ui.pages.settings import SettingsPage
        self.page_settings = SettingsPage(self._config)
        self.stacked_widget.addWidget(self.page_settings)

    def _create_log_console(self) -> QWidget:
        console = QFrame()
        console.setStyleSheet("""
            QFrame {
                background-color: #020617;
                border-radius: 8px;
                border: 1px solid #1E293B;
            }
        """)
        layout = QVBoxLayout(console)
        
        title = QLabel("Terminal Logs")
        title.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 12px;")
        layout.addWidget(title)
        
        # Dùng QTextEdit cho log
        from PySide6.QtWidgets import QTextEdit
        from src.ui.utils import QLogHandler
        import logging

        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #10B981; 
                font-family: Consolas, monospace;
                border: none;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.txt_logs)
        
        # Setup log handler
        self._log_handler = QLogHandler()
        self._log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S'))
        self._log_handler.log_signal.connect(self._on_log_message)
        self._log_handler.setLevel(logging.INFO)
        logging.getLogger("src").addHandler(self._log_handler)
        
        return console

    def _on_log_message(self, msg: str) -> None:
        """Thêm log mới vào console."""
        self.txt_logs.append(msg)
        # Tự cuộn xuống dưới cùng
        scrollbar = self.txt_logs.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_nav_clicked(self, index: int, clicked_btn: QPushButton, title_text: str) -> None:
        """Chuyển trang khi click menu."""
        # Uncheck các nút khác
        for btn in self.nav_buttons:
            if btn != clicked_btn:
                btn.setChecked(False)
        
        # Đảm bảo nút hiện tại luôn checked
        clicked_btn.setChecked(True)
        
        # Chuyển trang
        self.stacked_widget.setCurrentIndex(index)
        
        # Cập nhật title (Bỏ emoji)
        clean_title = title_text.split(" ", 1)[-1]
        self.lbl_title.setText(clean_title)
