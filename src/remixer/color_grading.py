import subprocess
from pathlib import Path
from src.core.logging import get_logger
import moviepy.video.fx as vfx

logger = get_logger(__name__)

class ColorGrader:
    """
    Nâng cấp thẩm mỹ video bằng LUTs và hiệu chỉnh màu sắc.
    """
    
    def __init__(self, lut_dir: str | Path = "./data/luts"):
        self.lut_dir = Path(lut_dir)
        self.lut_dir.mkdir(parents=True, exist_ok=True)

    def apply_lut(self, input_path: str | Path, output_path: str | Path, lut_name: str = "vibrant.cube"):
        """
        Áp dụng LUT (Look Up Table) vào video dùng FFmpeg.
        """
        lut_file = self.lut_dir / lut_name
        if not lut_file.exists():
            logger.warning(f"LUT file {lut_name} không tồn tại. Bỏ qua color grading.")
            return input_path

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"lut3d={str(lut_file)}",
            "-c:v", "libx264",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Color grading applied: {lut_name}")
            return output_path
        except Exception as e:
            logger.error(f"Lỗi khi áp dụng LUT: {e}")
            return input_path
            
    def adjust_vibrance(self, video_clip):
        """Tăng độ rực rỡ màu sắc dùng MoviePy/FFmpeg filters."""
        # Tương đương filter 'eq=saturation=1.2'
        return video_clip.fx(vfx.colorx, 1.2)
