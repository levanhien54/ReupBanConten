"""
Auto Updater Module.
Đảm bảo các thư viện cốt lõi (như yt-dlp) luôn ở phiên bản mới nhất.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class UpdateResult:
    """Kết quả của quá trình cập nhật."""

    def __init__(
        self,
        success: bool,
        updated: bool,
        old_version: Optional[str],
        new_version: Optional[str],
        error: Optional[str] = None,
    ) -> None:
        self.success = success
        self.updated = updated       # True nếu thực sự có phiên bản mới
        self.old_version = old_version
        self.new_version = new_version
        self.error = error

    @property
    def status_text(self) -> str:
        if not self.success:
            return f"Lỗi cập nhật yt-dlp: {self.error}"
        if self.updated:
            return f"yt-dlp: {self.old_version} → {self.new_version} ✅"
        return f"yt-dlp {self.new_version} (đang dùng bản mới nhất) ✅"


def _get_ytdlp_version() -> Optional[str]:
    """Lấy phiên bản yt-dlp hiện tại."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def update_ytdlp() -> UpdateResult:
    """
    Tự động cập nhật yt-dlp qua pip.
    Trả về UpdateResult với đầy đủ thông tin.
    """
    logger.info("Đang kiểm tra phiên bản yt-dlp...")

    old_version = _get_ytdlp_version()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

        new_version = _get_ytdlp_version()
        was_updated = (old_version != new_version) if old_version else True

        if was_updated:
            logger.info(f"yt-dlp cập nhật: {old_version} → {new_version}")
        else:
            logger.info(f"yt-dlp đã ở phiên bản mới nhất: {new_version}")

        return UpdateResult(
            success=True,
            updated=was_updated,
            old_version=old_version,
            new_version=new_version,
        )

    except subprocess.TimeoutExpired:
        logger.warning("Cập nhật yt-dlp timeout (60s). Bỏ qua.")
        return UpdateResult(
            success=False, updated=False,
            old_version=old_version, new_version=old_version,
            error="Timeout"
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi pip khi cập nhật yt-dlp: {e.stderr}")
        return UpdateResult(
            success=False, updated=False,
            old_version=old_version, new_version=old_version,
            error=e.stderr[:200]
        )
    except Exception as e:
        logger.error(f"Lỗi hệ thống khi cập nhật yt-dlp: {e}")
        return UpdateResult(
            success=False, updated=False,
            old_version=old_version, new_version=old_version,
            error=str(e)
        )
