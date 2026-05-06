import subprocess
import os
from pathlib import Path

def create_test_video(output_path: str, duration: int = 5, text: str = "Test Video"):
    """Tạo video giả lập bằng FFmpeg để test pipeline."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s=1280x720:d={duration}",
        "-vf", f"drawtext=text='{text}':fontcolor=white:fontsize=50:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-t", str(duration), "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

if __name__ == "__main__":
    os.makedirs("data/tests", exist_ok=True)
    create_test_video("data/tests/sample_video.mp4")
    print(f"Created sample video at data/tests/sample_video.mp4")
