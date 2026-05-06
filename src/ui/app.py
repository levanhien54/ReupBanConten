"""
Application Bootstrapper.
Thiết lập PySide6, Theme, Event Loop.
"""
from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import qdarktheme

from src.core.config import AppConfig
from src.core.logging import get_logger
from src.ui.main_window import MainWindow

logger = get_logger(__name__)


class ReupBanContenApp:
    """Class chính quản lý toàn bộ vòng đời của UI."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._app: Optional[QApplication] = None
        self._main_window: Optional[MainWindow] = None

    def run(self) -> int:
        """Khởi chạy ứng dụng."""
        logger.info("Khởi động UI Application...")
        
        # 1. High DPI Support (Windows)
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        # 2. Khởi tạo QApplication
        self._app = QApplication(sys.argv)
        self._app.setApplicationName(self._config.name)
        self._app.setApplicationVersion(self._config.version)
        
        # 3. Áp dụng Modern Theme (Dark Mode)
        try:
            self._app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
        except Exception as e:
            logger.warning(f"Could not load dark theme: {e}")
        
        # 4. Khởi tạo Main Window
        self._main_window = MainWindow(self._config)
        self._main_window.show()
        
        # 5. Chạy Event Loop
        logger.info("UI Ready. Đang chờ tương tác người dùng.")
        return self._app.exec()


def launch_ui(config: AppConfig) -> None:
    """Hàm wrapper để gọi từ CLI."""
    app = ReupBanContenApp(config)
    sys.exit(app.run())
