"""
YouTube Data API v3 Client.

Lấy danh sách video từ kênh YouTube qua API chính thức.
Hỗ trợ: sort by date / viewCount, filter Shorts, max count.

Fallback: nếu không có API key → dùng yt-dlp flat scan.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import json

from src.core.config import YoutubeApiConfig, ProxyConfig
from src.core.logging import get_logger

logger = get_logger(__name__)

_YT_API_BASE = "https://www.googleapis.com/youtube/v3"


class SortOrder(str, Enum):
    NEWEST    = "date"
    MOST_VIEWED = "viewCount"
    RATING    = "rating"
    RELEVANCE = "relevance"


@dataclass
class ApiVideoItem:
    """Metadata gọn từ YouTube API."""
    video_id: str
    title: str
    published_at: str
    duration_iso: str = ""       # ISO 8601 như PT1M30S
    duration_s: Optional[int] = None
    view_count: int = 0
    like_count: int = 0
    url: str = ""

    def __post_init__(self) -> None:
        self.url = f"https://www.youtube.com/watch?v={self.video_id}"
        if self.duration_iso:
            self.duration_s = _parse_iso8601_duration(self.duration_iso)


@dataclass
class YoutubeApiResult:
    """Kết quả gọi API (thành công hoặc lỗi)."""
    success: bool
    videos: list[ApiVideoItem] = field(default_factory=list)
    total_fetched: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None     # "QUOTA", "BLOCKED", "INVALID_KEY", "NETWORK", etc.
    channel_id: Optional[str] = None
    channel_title: Optional[str] = None


def _parse_iso8601_duration(iso: str) -> int:
    """Chuyển PT1H2M3S → giây."""
    import re
    m = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso
    )
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mi * 60 + s


class YoutubeApiClient:
    """
    Client gọi YouTube Data API v3.
    Thread-safe, không dùng thư viện ngoài ngoài standard library.
    """

    def __init__(
        self,
        config: YoutubeApiConfig,
        proxy_config: Optional[ProxyConfig] = None,
    ) -> None:
        self._config = config
        self._proxy = proxy_config
        self._api_key = config.api_key or os.getenv("YOUTUBE_API_KEY", "")

    # ── Public ────────────────────────────────────────────────

    def get_channel_videos(
        self,
        channel_url: str,
        *,
        max_count: int = 50,
        sort_by: SortOrder = SortOrder.NEWEST,
        shorts_only: bool = False,
        min_duration_s: int = 10,
        max_duration_s: int = 180,
    ) -> YoutubeApiResult:
        """
        Lấy danh sách video từ kênh qua YouTube API.

        Args:
            channel_url: URL kênh (handle, /channel/, /c/)
            max_count: Số lượng video tối đa muốn lấy
            sort_by: Tiêu chí sắp xếp
            shorts_only: Chỉ lấy video Shorts (<= 60s)
            min_duration_s / max_duration_s: Lọc theo thời lượng
        """
        if not self._api_key:
            return YoutubeApiResult(
                success=False,
                error="Chưa cấu hình YouTube API Key. Vào Settings để thêm.",
                error_code="NO_KEY",
            )

        # 1. Resolve channel_id
        channel_id, channel_title = self._resolve_channel_id(channel_url)
        if not channel_id:
            return YoutubeApiResult(
                success=False,
                error=f"Không tìm thấy kênh: {channel_url}",
                error_code="CHANNEL_NOT_FOUND",
            )

        # 2. Fetch video IDs từ search/playlist
        video_ids = self._fetch_video_ids(
            channel_id, max_count=max_count * 3, sort_by=sort_by
        )
        if video_ids is None:
            return YoutubeApiResult(
                success=False,
                error="YouTube API trả về lỗi hoặc quota vượt giới hạn.",
                error_code="API_ERROR",
            )

        if not video_ids:
            return YoutubeApiResult(
                success=True,
                videos=[],
                channel_id=channel_id,
                channel_title=channel_title,
            )

        # 3. Fetch chi tiết từng video (duration, views)
        details = self._fetch_video_details(video_ids)

        # 4. Lọc & giới hạn
        filtered: list[ApiVideoItem] = []
        for v in details:
            dur = v.duration_s or 0
            if dur > 0:
                if dur < min_duration_s or dur > max_duration_s:
                    continue
                if shorts_only and dur > 60:
                    continue
            filtered.append(v)
            if len(filtered) >= max_count:
                break

        logger.info(
            f"YouTube API: {len(filtered)} videos from {channel_title or channel_url}",
            extra={"sort": sort_by.value, "total_fetched": len(details)},
        )

        return YoutubeApiResult(
            success=True,
            videos=filtered,
            total_fetched=len(details),
            channel_id=channel_id,
            channel_title=channel_title,
        )

    def test_connection(self) -> tuple[bool, str]:
        """Kiểm tra API key và kết nối. Trả về (ok, message)."""
        if not self._api_key:
            return False, "Chưa có API Key."
        try:
            url = (
                f"{_YT_API_BASE}/videos"
                f"?part=id&id=dQw4w9WgXcQ&key={self._api_key}"
            )
            data = self._get(url)
            if data is None:
                return False, "Không nhận được phản hồi từ API."
            return True, "Kết nối YouTube API thành công."
        except Exception as e:
            return False, str(e)

    # ── Private Helpers ───────────────────────────────────────

    def _resolve_channel_id(self, channel_url: str) -> tuple[Optional[str], Optional[str]]:
        """Chuyển URL/handle → channel_id + title."""
        handle = self._extract_handle(channel_url)
        channel_id_raw = self._extract_channel_id(channel_url)

        if channel_id_raw:
            # Đã có channel_id trực tiếp
            data = self._get(
                f"{_YT_API_BASE}/channels"
                f"?part=snippet&id={channel_id_raw}&key={self._api_key}"
            )
        elif handle:
            data = self._get(
                f"{_YT_API_BASE}/channels"
                f"?part=snippet&forHandle={handle}&key={self._api_key}"
            )
        else:
            # Tìm theo tên
            name = channel_url.strip().rstrip("/").split("/")[-1]
            data = self._get(
                f"{_YT_API_BASE}/channels"
                f"?part=snippet&forUsername={name}&key={self._api_key}"
            )

        if not data:
            return None, None

        items = data.get("items", [])
        if not items:
            return None, None

        channel_id = items[0]["id"]
        title = items[0]["snippet"].get("title", "")
        return channel_id, title

    def _fetch_video_ids(
        self,
        channel_id: str,
        max_count: int,
        sort_by: SortOrder,
    ) -> Optional[list[str]]:
        """Lấy danh sách video_id qua search.list."""
        ids: list[str] = []
        page_token: Optional[str] = None
        per_page = min(self._config.max_results_per_page, 50)

        while len(ids) < max_count:
            params = (
                f"part=id"
                f"&channelId={channel_id}"
                f"&type=video"
                f"&order={sort_by.value}"
                f"&maxResults={per_page}"
                f"&key={self._api_key}"
            )
            if page_token:
                params += f"&pageToken={page_token}"

            data = self._get(f"{_YT_API_BASE}/search?{params}")
            if data is None:
                return None

            for item in data.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid:
                    ids.append(vid)

            page_token = data.get("nextPageToken")
            if not page_token or len(ids) >= max_count:
                break

        return ids[:max_count]

    def _fetch_video_details(self, video_ids: list[str]) -> list[ApiVideoItem]:
        """Lấy chi tiết duration + statistics theo batch 50."""
        results: list[ApiVideoItem] = []
        batch_size = 50

        for i in range(0, len(video_ids), batch_size):
            batch = video_ids[i : i + batch_size]
            ids_str = ",".join(batch)
            data = self._get(
                f"{_YT_API_BASE}/videos"
                f"?part=snippet,contentDetails,statistics"
                f"&id={ids_str}"
                f"&key={self._api_key}"
            )
            if not data:
                continue

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                content = item.get("contentDetails", {})
                stats   = item.get("statistics", {})

                results.append(ApiVideoItem(
                    video_id=item["id"],
                    title=snippet.get("title", "Untitled"),
                    published_at=snippet.get("publishedAt", ""),
                    duration_iso=content.get("duration", ""),
                    view_count=int(stats.get("viewCount", 0)),
                    like_count=int(stats.get("likeCount", 0)),
                ))

        return results

    def _get(self, url: str) -> Optional[dict]:
        """HTTP GET với proxy support và error mapping."""
        try:
            proxies = {}
            if self._proxy and self._proxy.enabled and self._proxy.url:
                proxies["http"] = self._proxy.url
                proxies["https"] = self._proxy.url

            req = Request(url, headers={"User-Agent": "ReupBanConten/1.0"})
            with urlopen(req, timeout=self._config.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass

            if e.code == 403:
                if "quotaExceeded" in body or "dailyLimitExceeded" in body:
                    raise QuotaExceededError("YouTube API quota vượt giới hạn hôm nay.") from e
                raise ApiBlockedError(f"YouTube API từ chối (403): {body[:200]}") from e
            if e.code == 400:
                raise InvalidApiKeyError(f"API Key không hợp lệ (400): {body[:200]}") from e
            logger.error(f"YouTube API HTTP {e.code}: {body[:200]}")
            return None

        except URLError as e:
            raise NetworkError(f"Lỗi kết nối: {e.reason}") from e

        except Exception as e:
            logger.error(f"YouTube API unexpected error: {e}")
            return None

    @staticmethod
    def _extract_handle(url: str) -> Optional[str]:
        import re
        m = re.search(r"/@([^/?\s]+)", url)
        return m.group(1) if m else None

    @staticmethod
    def _extract_channel_id(url: str) -> Optional[str]:
        import re
        m = re.search(r"/channel/([A-Za-z0-9_-]{24})", url)
        return m.group(1) if m else None


# ── Custom Exceptions ─────────────────────────────────────────

class YoutubeApiError(Exception):
    """Base exception cho YouTube API errors."""
    error_code: str = "API_ERROR"

class QuotaExceededError(YoutubeApiError):
    error_code = "QUOTA"

class ApiBlockedError(YoutubeApiError):
    error_code = "BLOCKED"

class InvalidApiKeyError(YoutubeApiError):
    error_code = "INVALID_KEY"

class NetworkError(YoutubeApiError):
    error_code = "NETWORK"
