from __future__ import annotations

import inspect

from yt_dlp.postprocessor.ffmpeg import FFmpegVideoConvertorPP

from src.core.config import DownloaderConfig
from src.downloader.download_manager import DownloadErrorCode, DownloadManager


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
