from __future__ import annotations

from src.remixer.vertical_video import build_blur_background_filter


def test_blur_background_filter_outputs_mapped_vertical_stream():
    video_filter = build_blur_background_filter(width=1080, height=1920, blur_sigma=30)

    assert "scale=1080:1920:force_original_aspect_ratio=increase" in video_filter
    assert "crop=1080:1920" in video_filter
    assert "gblur=sigma=30" in video_filter
    assert "scale=1080:1920:force_original_aspect_ratio=decrease" in video_filter
    assert "overlay=(W-w)/2:(H-h)/2" in video_filter
    assert video_filter.endswith("format=yuv420p[v]")
