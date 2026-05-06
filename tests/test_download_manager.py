from __future__ import annotations

import inspect

from yt_dlp.postprocessor.ffmpeg import FFmpegVideoConvertorPP

from src.core.config import DownloaderConfig
from src.downloader.download_manager import (
    DownloadErrorCode,
    DownloadManager,
    normalize_quality_selector,
)


def test_video_convertor_postprocessor_uses_installed_ytdlp_keyword():
    manager = DownloadManager(DownloaderConfig(preferred_format="mp4"))

    pp = manager._build_video_convertor_pp()

    params = inspect.signature(FFmpegVideoConvertorPP.__init__).parameters
    expected_key = "preferredformat" if "preferredformat" in params else "preferedformat"
    unexpected_key = "preferedformat" if expected_key == "preferredformat" else "preferredformat"
    assert pp == {"key": "FFmpegVideoConvertor", expected_key: "mp4"}
    assert unexpected_key not in pp


def test_ytdlp_postprocessor_keyword_error_is_classified_as_format_error():
    code, message = DownloadManager._classify_error(
        "FFmpegVideoConvertorPP.__init__() got an unexpected keyword argument 'preferredformat'"
    )

    assert code == DownloadErrorCode.FORMAT_ERROR
    assert message


def test_normalize_quality_selector_prefers_split_streams_with_fallback():
    assert normalize_quality_selector("best[height<=720]") == (
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    )
    assert normalize_quality_selector("bestvideo+bestaudio") == "bestvideo+bestaudio"


def test_build_ydl_opts_can_disable_best_effort_subtitles():
    manager = DownloadManager(DownloaderConfig(preferred_format="mp4"))
    opts = manager._build_ydl_opts(
        "downloads",
        "best[height<=720]",
        lambda _: None,
        include_subtitles=False,
    )

    assert opts["format"] == "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    assert "writesubtitles" not in opts
    assert "writeautomaticsub" not in opts
    assert all(pp["key"] != "FFmpegSubtitlesConvertor" for pp in opts["postprocessors"])


def test_subtitle_download_errors_are_detected_for_retry():
    assert DownloadManager._is_subtitle_download_error(
        "Unable to download video subtitles for 'vi-en': HTTP Error 429"
    )
    assert not DownloadManager._is_subtitle_download_error("Requested format is not available")


def test_final_output_path_prefers_merged_requested_download():
    assert DownloadManager._final_output_path(
        {
            "_filename": "temp.webm",
            "requested_downloads": [
                {"filepath": "video.f278.webm"},
                {"filepath": "video.mp4"},
            ],
        }
    ) == "video.mp4"
