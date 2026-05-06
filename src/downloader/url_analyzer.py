"""
Smart URL Analyzer — phân loại URL đầu vào tự động.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class UrlType(str, Enum):
    SINGLE_VIDEO = "single_video"
    CHANNEL      = "channel"
    PLAYLIST     = "playlist"
    UNKNOWN      = "unknown"


@dataclass
class UrlInfo:
    url_type: UrlType
    platform: str          # "youtube", "tiktok", "facebook", ...
    raw_url: str
    label: str             # mô tả ngắn cho UI
    icon: str


_RULES: list[tuple[re.Pattern, UrlType, str, str, str]] = [
    # (pattern, type, platform, label, icon)

    # ── YouTube single video ──
    (re.compile(r"youtube\.com/watch\?v=|youtu\.be/[A-Za-z0-9_-]{11}"),
     UrlType.SINGLE_VIDEO, "youtube", "YouTube Video", "🎬"),

    # ── YouTube Shorts ──
    (re.compile(r"youtube\.com/shorts/"),
     UrlType.SINGLE_VIDEO, "youtube", "YouTube Shorts", "⚡"),

    # ── YouTube playlist ──
    (re.compile(r"youtube\.com/playlist\?list="),
     UrlType.PLAYLIST, "youtube", "YouTube Playlist", "📋"),

    # ── YouTube channel ──
    (re.compile(r"youtube\.com/(@[^/?\s]+|channel/[A-Za-z0-9_-]+|c/[^/?\s]+)"),
     UrlType.CHANNEL, "youtube", "YouTube Channel", "📺"),

    # ── TikTok video ──
    (re.compile(r"tiktok\.com/@[^/]+/video/\d+"),
     UrlType.SINGLE_VIDEO, "tiktok", "TikTok Video", "🎵"),

    # ── TikTok profile ──
    (re.compile(r"tiktok\.com/@[^/?\s]+/?$"),
     UrlType.CHANNEL, "tiktok", "TikTok Profile", "🎵"),

    # ── Facebook video ──
    (re.compile(r"facebook\.com/.+/videos/|fb\.watch/"),
     UrlType.SINGLE_VIDEO, "facebook", "Facebook Video", "👥"),

    # ── Instagram reel / post ──
    (re.compile(r"instagram\.com/(reel|p)/"),
     UrlType.SINGLE_VIDEO, "instagram", "Instagram Reel", "📸"),

    # ── Twitter/X ──
    (re.compile(r"(twitter|x)\.com/\w+/status/"),
     UrlType.SINGLE_VIDEO, "twitter", "Twitter/X Video", "🐦"),

    # ── Bilibili ──
    (re.compile(r"bilibili\.com/video/"),
     UrlType.SINGLE_VIDEO, "bilibili", "Bilibili Video", "📺"),
]


def analyze_url(url: str) -> UrlInfo:
    """
    Phân tích URL → UrlInfo.
    Tự động nhận diện: video đơn lẻ / kênh / playlist / unknown.
    """
    url = url.strip()

    for pattern, url_type, platform, label, icon in _RULES:
        if pattern.search(url):
            return UrlInfo(
                url_type=url_type,
                platform=platform,
                raw_url=url,
                label=label,
                icon=icon,
            )

    # Handle @handle without domain
    if url.startswith("@"):
        return UrlInfo(
            url_type=UrlType.CHANNEL,
            platform="youtube",
            raw_url=f"https://youtube.com/{url}",
            label="YouTube Channel (handle)",
            icon="📺",
        )

    # Bare channel name
    if url and not url.startswith("http") and "/" not in url:
        return UrlInfo(
            url_type=UrlType.CHANNEL,
            platform="youtube",
            raw_url=f"https://youtube.com/@{url}",
            label="YouTube Channel (name)",
            icon="📺",
        )

    return UrlInfo(
        url_type=UrlType.UNKNOWN,
        platform="unknown",
        raw_url=url,
        label="Unknown URL",
        icon="❓",
    )
