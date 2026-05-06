"""
Custom Exception Hierarchy.

Tất cả exceptions trong dự án đều kế thừa từ ReupError,
giúp dễ dàng catch và debug.
"""
from __future__ import annotations

from typing import Any, Optional


class ReupError(Exception):
    """Base exception cho toàn bộ dự án."""

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ):
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        base = super().__str__()
        if self.context:
            details = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"[{self.error_code}] {base} ({details})"
        return f"[{self.error_code}] {base}"


# Alias cho ReupError dùng trong các module mới
AppError = ReupError


# ── Download errors ──────────────────────────

class DownloadError(ReupError):
    """Lỗi khi tải video."""
    pass


class ChannelNotFoundError(DownloadError):
    """Không tìm thấy kênh YouTube."""
    pass


class VideoUnavailableError(DownloadError):
    """Video không khả dụng (bị xóa, private, restricted)."""
    pass


class RateLimitError(DownloadError):
    """Bị YouTube rate limit (HTTP 429)."""
    pass


# ── Analysis errors ──────────────────────────

class AnalysisError(ReupError):
    """Lỗi trong quá trình phân tích."""
    pass


class TranscriptionError(AnalysisError):
    """Lỗi Whisper transcription."""
    pass


class LLMError(ReupError):
    """Lỗi liên quan đến LLM."""
    pass


class LLMTimeoutError(LLMError):
    """LLM response timeout."""
    pass


class LLMResponseParseError(LLMError):
    """Không thể parse JSON từ LLM response."""
    pass


class LLMProviderUnavailableError(LLMError):
    """LLM provider không sẵn sàng."""
    pass


# ── Video processing errors ─────────────────

class VideoProcessingError(ReupError):
    """Lỗi xử lý video."""
    pass


class FFmpegError(VideoProcessingError):
    """Lỗi FFmpeg."""
    pass


class SceneDetectionError(VideoProcessingError):
    """Lỗi phát hiện cảnh."""
    pass


class ClipExportError(VideoProcessingError):
    """Lỗi xuất clip."""
    pass


class RenderError(VideoProcessingError):
    """Lỗi render video cuối cùng."""
    pass


# ── Remix errors ─────────────────────────────

class RemixError(ReupError):
    """Lỗi trong quá trình remix."""
    pass


class InsufficientClipsError(RemixError):
    """Không đủ clips để remix."""
    pass


class ScriptGenerationError(RemixError):
    """Lỗi tạo kịch bản remix."""
    pass


# ── External service errors ──────────────────

class ExternalServiceError(ReupError):
    """Lỗi dịch vụ bên ngoài."""
    pass


class ElevenLabsError(ExternalServiceError):
    """Lỗi ElevenLabs API."""
    pass


class ElevenLabsQuotaError(ElevenLabsError):
    """Hết quota ElevenLabs."""
    pass


# ── Storage errors ───────────────────────────

class StorageError(ReupError):
    """Lỗi lưu trữ."""
    pass


class DiskFullError(StorageError):
    """Hết dung lượng ổ đĩa."""
    pass


class FileCorruptError(StorageError):
    """File bị hỏng."""
    pass


# ── Configuration errors ────────────────────

class ConfigError(ReupError):
    """Lỗi cấu hình."""
    pass
