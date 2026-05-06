"""
Rendering Stress Test — Kiểm tra chất lượng render video cuối cùng.
"""
import os
import sys
import asyncio

# Thêm root vào path
sys.path.append(os.getcwd())

from src.core.config import load_config
from src.remixer.effects import SubtitleRenderer
from src.core.types import CommentaryScript, CommentarySegment

async def test_rendering_quality():
    config = load_config()
    os.makedirs("data/outputs", exist_ok=True)
    
    input_video = "data/segments/TestFolder/clip1.mp4"
    output_video = "data/outputs/audit_test_final.mp4"
    
    if not os.path.exists(input_video):
        print("FAIL: Input video not found")
        return

    # 1. Giả lập kịch bản
    script = CommentaryScript(
        segments=[
            CommentarySegment(
                text="Xin chào, đây là bài kiểm tra chất lượng Render!",
                start_time=0.5,
                duration_estimate=3.0
            )
        ],
        total_segments=1
    )
    
    print("Running render test (Subtitles + FFmpeg)...")
    
    # 2. Render phụ đề bằng bộ render cao cấp
    renderer = SubtitleRenderer(config.remixer.effects.subtitles)
    # Giả lập style CapCut Yellow
    config.remixer.effects.subtitles.preset_style = "capcut_yellow"
    
    result = renderer.apply_subtitles(input_video, script, output_video)
    
    if os.path.exists(result):
        print(f"PASS: Video rendered successfully at {result}")
        print(f"File size: {os.path.getsize(result) / 1024:.1f} KB")
    else:
        print("FAIL: Video rendering failed")

if __name__ == "__main__":
    asyncio.run(test_rendering_quality())
