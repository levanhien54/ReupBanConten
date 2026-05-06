"""
Download Manager — yt-dlp wrapper với proxy + error detection.

Flow:
  1. Nhận list URL từ YouTube API client.
  2. Tải từng video bằng yt-dlp với retry logic.
  3. Phát hiện và phân loại lỗi: blocked, proxy fail, rate limit, v.v.
  4. Emit progress callback cho UI.
"""
from __future__ import annotations

import os
import re
import time
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import yt_dlp

from src.core.config import DownloaderConfig
from src.core.types import DownloadedVideo, VideoMetadata
from src.core.logging import get_logger

logger = get_logger(__name__)


# ── Error codes ───────────────────────────────────────────────

class DownloadErrorCode(str, Enum):
    BLOCKED        = "BLOCKED"        # YouTube chặn IP / bot detection
    PROXY_FAIL     = "PROXY_FAIL"     # Proxy không hoạt động
    RATE_LIMIT     = "RATE_LIMIT"     # 429 Too Many Requests
    GEO_BLOCK      = "GEO_BLOCK"      # Bị chặn theo vùng địa lý
    UNAVAILABLE    = "UNAVAILABLE"    # Video đã xóa / private
    FORMAT_ERROR   = "FORMAT_ERROR"   # Không tìm được định dạng phù hợp
    NETWORK_ERROR  = "NETWORK_ERROR"  # Lỗi mạng chung
    UNKNOWN        = "UNKNOWN"


@dataclass
class DownloadProgress:
    video_id: str
    title: str
    status: str          # "downloading", "done", "error", "skipped"
    percent: float = 0.0
    speed_kbps: float = 0.0
    eta_s: int = 0
    error_code: Optional[DownloadErrorCode] = None
    error_msg: Optional[str] = None
    output_path: Optional[str] = None


@dataclass
class DownloadResult:
    """Kết quả tổng hợp sau khi tải batch."""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    outputs: list[str] = field(default_factory=list)
    errors: list[DownloadProgress] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.success / max(self.total, 1)


ProgressCallback = Callable[[DownloadProgress], None]


class DownloadManager:
    """
    Quản lý tải video từ YouTube bằng yt-dlp.
    Thread-safe, hỗ trợ proxy, retry và error mapping chi tiết.
    """

    def __init__(self, config: DownloaderConfig) -> None:
        self._config = config

    # ── Public API ────────────────────────────────────────────

    def download_batch(
        self,
        urls: list[str],
        output_dir: str,
        *,
        on_progress: Optional[ProgressCallback] = None,
        quality: str = "best[height<=720]",
    ) -> DownloadResult:
        """
        Tải nhiều video từ danh sách URL.

        Args:
            urls: Danh sách URL YouTube
            output_dir: Thư mục lưu video
            on_progress: Callback cập nhật tiến độ (gọi từ thread)
            quality: Format string cho yt-dlp
        """
        os.makedirs(output_dir, exist_ok=True)
        result = DownloadResult(total=len(urls))

        for i, url in enumerate(urls):
            vid_id = self._extract_video_id(url)
            prog = DownloadProgress(
                video_id=vid_id,
                title=f"Video {i+1}/{len(urls)}",
                status="downloading",
            )

            logger.info(f"Downloading [{i+1}/{len(urls)}]: {url}")

            try:
                out_path = self._download_single(
                    url, output_dir, quality=quality,
                    progress=prog, on_progress=on_progress
                )
                prog.status = "done"
                prog.output_path = out_path
                prog.percent = 100.0
                result.success += 1
                result.outputs.append(out_path)

            except yt_dlp.utils.DownloadError as e:
                prog.status = "error"
                prog.error_code, prog.error_msg = self._classify_error(str(e))
                result.failed += 1
                result.errors.append(prog)
                logger.error(
                    f"Download failed [{prog.error_code}]: {url} — {prog.error_msg}"
                )

            except Exception as e:
                prog.status = "error"
                prog.error_code = DownloadErrorCode.UNKNOWN
                prog.error_msg = str(e)
                result.failed += 1
                result.errors.append(prog)
                logger.error(f"Unexpected error downloading {url}: {e}")

            finally:
                if on_progress:
                    on_progress(prog)

                # Nghỉ giữa các lần tải để tránh rate limit
                if i < len(urls) - 1:
                    time.sleep(self._config.ytdlp.sleep_interval)

        logger.info(
            f"Batch download done: {result.success}/{result.total} success "
            f"({result.failed} failed)"
        )
        return result

    def download_video(
        self,
        url: str,
        output_dir: str,
        *,
        on_progress: Optional[ProgressCallback] = None,
        quality: str = "best[height<=720]",
    ) -> Optional[DownloadedVideo]:
        """Download one video and return the domain model used by CLI/UI."""
        result = self.download_batch(
            [url],
            output_dir,
            on_progress=on_progress,
            quality=quality,
        )
        if result.success == 0 or not result.outputs:
            return None

        output_path = result.outputs[0]
        video_id = self._extract_video_id(url)
        title = os.path.splitext(os.path.basename(output_path))[0]
        return DownloadedVideo(
            video_id=video_id,
            file_path=output_path,
            metadata=VideoMetadata(
                video_id=video_id,
                title=title,
            ),
        )

    def test_proxy(self, proxy_url: str) -> tuple[bool, str]:
        """
        Kiểm tra proxy bằng cách gọi YouTube.
        Trả về (ok, message).
        """
        logger.info(f"Testing proxy: {proxy_url}")
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "proxy": proxy_url,
            "socket_timeout": 10,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Thử lấy info video nổi tiếng, không tải
                info = ydl.extract_info(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    download=False,
                )
                if info:
                    return True, f"Proxy hoạt động. IP: {proxy_url}"
                return False, "Proxy kết nối được nhưng không nhận dữ liệu."
        except Exception as e:
            err_str = str(e)
            if "ProxyError" in err_str or "Cannot connect" in err_str:
                return False, f"Proxy không kết nối được: {err_str[:150]}"
            if "429" in err_str:
                return False, "Proxy bị YouTube rate-limit (429). Thử proxy khác."
            return False, f"Lỗi proxy: {err_str[:200]}"

    # ── Private ───────────────────────────────────────────────

    def _build_ydl_opts(
        self,
        output_dir: str,
        quality: str,
        progress_hook: Callable,
    ) -> dict:
        proxy_url: Optional[str] = None
        if self._config.proxy.enabled and self._config.proxy.url:
            proxy_url = self._config.proxy.url
        elif self._config.ytdlp.proxy:
            proxy_url = self._config.ytdlp.proxy

        # Ngon ngu phu de tu config (vi, en mac dinh)
        sub_langs = list(self._config.metadata.subtitle_languages) or ["vi", "en"]
        sub_langs_ext = sub_langs + [f"{l}.*" for l in sub_langs]

        opts: dict = {
            "format": quality,
            "outtmpl": os.path.join(output_dir, "%(id)s_%(title).60s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "retries": self._config.ytdlp.retries,
            "progress_hooks": [progress_hook],
            "merge_output_format": "mp4",
            # ── Subtitle / SRT (phuc vu LLM phan tich) ──────
            "writesubtitles": True,          # phu de thu cong
            "writeautomaticsub": True,       # phu de tu dong YouTube
            "subtitleslangs": sub_langs_ext, # ["vi","en","vi.*","en.*"]
            "subtitlesformat": "srt",        # dinh dang SRT
            "embedsubtitles": False,         # luu file .srt rieng
            # ────────────────────────────────────────────────
            "postprocessors": [
                self._build_video_convertor_pp(),
                {
                    # Convert phu de sang SRT neu can
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                    "when": "before_dl",
                },
            ],
        }

        if proxy_url:
            opts["proxy"] = proxy_url
            logger.debug(f"Using proxy: {proxy_url}")

        if self._config.ytdlp.cookies_file and os.path.exists(self._config.ytdlp.cookies_file):
            opts["cookiefile"] = self._config.ytdlp.cookies_file

        if self._config.ytdlp.rate_limit:
            opts["ratelimit"] = self._config.ytdlp.rate_limit

        return opts

    def _build_video_convertor_pp(self) -> dict:
        """Build FFmpegVideoConvertor options for old and new yt-dlp releases."""
        pp = {"key": "FFmpegVideoConvertor"}
        try:
            from yt_dlp.postprocessor.ffmpeg import FFmpegVideoConvertorPP

            params = inspect.signature(FFmpegVideoConvertorPP.__init__).parameters
            format_arg = "preferredformat" if "preferredformat" in params else "preferedformat"
        except Exception:
            format_arg = "preferedformat"
        pp[format_arg] = self._config.preferred_format
        return pp

    def _download_single(
        self,
        url: str,
        output_dir: str,
        quality: str,
        progress: DownloadProgress,
        on_progress: Optional[ProgressCallback],
    ) -> str:
        output_path_holder: list[str] = []

        def _hook(d: dict) -> None:
            if d["status"] == "downloading":
                progress.percent = float(
                    re.sub(r"[^\d.]", "", d.get("_percent_str", "0") or "0") or 0
                )
                speed = d.get("speed") or 0
                progress.speed_kbps = round(speed / 1024, 1) if speed else 0
                progress.eta_s = d.get("eta") or 0
                if on_progress:
                    on_progress(progress)
            elif d["status"] == "finished":
                output_path_holder.append(d.get("filename", ""))

        opts = self._build_ydl_opts(output_dir, quality, _hook)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                progress.title = info.get("title", progress.title)

        return output_path_holder[0] if output_path_holder else ""

    @staticmethod
    def _classify_error(error_msg: str) -> tuple[DownloadErrorCode, str]:
        """
        Phân loại lỗi yt-dlp thành error code có ý nghĩa.
        Cho phép UI hiển thị thông báo rõ ràng cho người dùng.
        """
        msg_lower = error_msg.lower()

        if any(k in msg_lower for k in ["429", "too many requests", "rate limit"]):
            return (
                DownloadErrorCode.RATE_LIMIT,
                "YouTube đang chặn do quá nhiều yêu cầu (429). "
                "Hãy dùng proxy hoặc chờ vài giờ."
            )

        if any(k in msg_lower for k in ["sign in", "bot", "confirm you're not a bot",
                                         "inappropriate", "blocked"]):
            return (
                DownloadErrorCode.BLOCKED,
                "YouTube phát hiện bot và yêu cầu xác minh. "
                "Hãy thêm cookies hoặc đổi proxy."
            )

        if any(k in msg_lower for k in ["proxy", "proxyerror", "cannot connect to proxy"]):
            return (
                DownloadErrorCode.PROXY_FAIL,
                "Proxy không hoạt động hoặc bị từ chối. "
                "Kiểm tra lại cài đặt proxy trong Settings."
            )

        if any(k in msg_lower for k in ["not available in your country", "geo",
                                         "blocked in your region"]):
            return (
                DownloadErrorCode.GEO_BLOCK,
                "Video bị chặn theo khu vực địa lý. "
                "Dùng proxy ở quốc gia khác."
            )

        if any(k in msg_lower for k in ["video unavailable", "private video",
                                         "has been removed", "not exist"]):
            return (
                DownloadErrorCode.UNAVAILABLE,
                "Video không khả dụng (đã xóa, private, hoặc bị hạn chế tuổi)."
            )

        if any(k in msg_lower for k in ["requested format", "no video formats",
                                         "format not available", "preferredformat",
                                         "preferedformat"]):
            return (
                DownloadErrorCode.FORMAT_ERROR,
                "Không tìm được định dạng video phù hợp."
            )

        if any(k in msg_lower for k in ["network", "connection", "timeout", "ssl"]):
            return (
                DownloadErrorCode.NETWORK_ERROR,
                "Lỗi kết nối mạng. Kiểm tra internet hoặc proxy."
            )

        return DownloadErrorCode.UNKNOWN, f"Lỗi không xác định: {error_msg[:200]}"

    @staticmethod
    def _extract_video_id(url: str) -> str:
        m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        return m.group(1) if m else url[-11:]
