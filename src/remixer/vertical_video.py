"""FFmpeg filters for vertical short-form video exports."""
from __future__ import annotations


def build_blur_background_filter(width: int = 1080, height: int = 1920, blur_sigma: int = 35) -> str:
    """Return a 9:16 filter graph with blurred background and centered foreground."""
    return (
        "[0:v]split=2[bgsrc][fgsrc];"
        f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma={blur_sigma}[bg];"
        f"[fgsrc]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]"
    )
