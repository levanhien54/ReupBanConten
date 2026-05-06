"""
Channel Scanner — Quét kênh YouTube lấy danh sách video.

Sử dụng yt-dlp extract_info với flat_playlist mode
để lấy metadata nhanh mà không cần tải video.
"""
from __future__ import annotations

import re
from typing import Optional

import yt_dlp

from src.core.config import DownloaderConfig
from src.core.errors import ChannelNotFoundError, DownloadError
from src.core.logging import get_logger, log_duration
from src.core.types import VideoInfo, ChannelInfo
from src.core.events import get_event_bus, EventType
from src.core.database import get_database, VideoRepository

logger = get_logger(__name__)


class ChannelScanner:
    """Quét kênh YouTube lấy danh sách video."""

    def __init__(self, config: DownloaderConfig) -> None:
        self._config = config
        self._event_bus = get_event_bus()

    @log_duration(msg_template="Channel scan {func_name}")
    def scan(
        self,
        channel_url: str,
        *,
        max_count: int = 20,
        shorts_only: bool = True,
        sort_by: str = "newest",   # "newest" | "most_viewed"
    ) -> list[VideoInfo]:
        """
        Quét kênh và trả về danh sách video.

        Args:
            channel_url: URL kênh YouTube (handle, /channel/, /c/)
            max_count: Số video tối đa
            shorts_only: Chỉ lấy video ngắn (< 60s)
            sort_by: Sắp xếp theo: "newest" hoặc "most_viewed"

        Returns:
            Danh sách VideoInfo đã lọc và sắp xếp

        Raises:
            ChannelNotFoundError: Kênh không tồn tại
            DownloadError: Lỗi khác
        """
        url = self._normalize_channel_url(channel_url)
        logger.info(
            f"Scanning channel: {url} (sort={sort_by}, max={max_count})",
            extra={"channel": url},
        )

        # Kết nạp nhiều hơn nếu cần sắp xếp ("most_viewed" cần tải đủ để sort)
        fetch_limit = max_count * 5 if sort_by == "most_viewed" else max_count * 2

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "playlistend": fetch_limit,
        }

        if self._config.ytdlp.cookies_file:
            ydl_opts["cookiefile"] = self._config.ytdlp.cookies_file
        if self._config.ytdlp.proxy:
            ydl_opts["proxy"] = self._config.ytdlp.proxy

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "not found" in error_msg.lower() or "404" in error_msg:
                raise ChannelNotFoundError(
                    f"Channel not found: {channel_url}",
                    context={"url": channel_url},
                ) from e
            raise DownloadError(
                f"Error scanning channel: {error_msg}",
                context={"url": channel_url},
            ) from e

        if not result:
            raise ChannelNotFoundError(
                f"No results for channel: {channel_url}",
                context={"url": channel_url},
            )

        # Parse entries
        entries = result.get("entries", [])
        if not entries:
            logger.warning(f"No videos found in channel: {channel_url}")
            return []

        # Map to VideoInfo & filter
        videos: list[VideoInfo] = []
        for entry in entries:
            if entry is None:
                continue

            video = VideoInfo(
                video_id=entry.get("id", ""),
                url=entry.get("url", f"https://youtube.com/watch?v={entry.get('id', '')}"),
                title=entry.get("title", "Untitled"),
                duration=entry.get("duration"),
                view_count=entry.get("view_count", 0),
                upload_date=entry.get("upload_date"),
            )

            # Apply filters
            if not self._passes_filters(video, shorts_only=shorts_only):
                continue

            videos.append(video)

            if len(videos) >= max_count:
                break

        # Sắp xếp theo yêu cầu
        if sort_by == "most_viewed":
            videos.sort(key=lambda v: v.view_count or 0, reverse=True)
            logger.info(f"Sorted by most views. Top view: {videos[0].view_count if videos else 0}")
        # "newest": giữ nguyên thứ tự tự nhiên của playlist (YouTube sắp xếp mới nhất lên trước)

        # Cắt đúnh số lượng yêu cầu
        videos = videos[:max_count]

        # Save to database
        self._save_to_db(channel_url, result, videos)

        logger.info(
            f"Scan complete: {len(videos)} videos (sort={sort_by})",
            extra={"channel": channel_url, "video_count": len(videos)},
        )

        return videos

    def _passes_filters(self, video: VideoInfo, *, shorts_only: bool) -> bool:
        """Kiểm tra video có qua filters không."""
        duration = video.duration or 0

        # Duration filter
        if duration > 0:
            if duration > self._config.max_video_duration:
                return False
            if duration < self._config.min_video_duration:
                return False
            if shorts_only and duration > 60:
                return False

        return True

    def _normalize_channel_url(self, url: str) -> str:
        """Chuẩn hóa URL kênh → dạng /videos."""
        url = url.strip().rstrip("/")

        # Handle @handle format
        if "/@" in url or url.startswith("@"):
            if url.startswith("@"):
                url = f"https://youtube.com/{url}"
            if not url.endswith("/videos"):
                url += "/videos"
            return url

        # Handle /channel/ or /c/ format
        if "/channel/" in url or "/c/" in url:
            if not url.endswith("/videos"):
                url += "/videos"
            return url

        # Raw URL, try appending /videos
        if "youtube.com" in url:
            if not url.endswith("/videos"):
                url += "/videos"
            return url

        # Assume it's a handle
        return f"https://youtube.com/@{url}/videos"

    def _save_to_db(
        self,
        channel_url: str,
        yt_result: dict,
        videos: list[VideoInfo],
    ) -> None:
        """Lưu kết quả scan vào database."""
        try:
            db = get_database()

            # Save channel
            db.execute(
                "INSERT OR REPLACE INTO channels (url, name, channel_id) "
                "VALUES (?, ?, ?)",
                (
                    channel_url,
                    yt_result.get("channel", yt_result.get("uploader", "")),
                    yt_result.get("channel_id", ""),
                ),
            )
            db._get_connection().commit()

            # Save videos
            repo = VideoRepository(db)
            for v in videos:
                repo.upsert(
                    v.video_id,
                    url=v.url,
                    title=v.title or "",
                    duration=v.duration or 0,
                    view_count=v.view_count or 0,
                    upload_date=v.upload_date or "",
                    status="pending",
                )

        except Exception as e:
            logger.warning(f"Failed to save scan results to DB: {e}")
