import subprocess
import os
from pathlib import Path
from src.core.logging import get_logger
from src.core.errors import AppError

logger = get_logger(__name__)

class VideoNormalizer:
    """
    Chuẩn hóa video đầu vào để tiết kiệm dung lượng lưu trữ và chi phí xử lý AI.
    Mục tiêu: 720p, 20fps, bitrate tối ưu.
    """
    
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._nvenc_available = self._check_nvenc()

    def _check_nvenc(self) -> bool:
        """Kiểm tra xem hệ thống có hỗ trợ NVIDIA NVENC không."""
        try:
            res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, timeout=5)
            return "h264_nvenc" in res.stdout
        except:
            return False

    def normalize(self, input_path: str | Path, 
                  resolution: int = 720, 
                  fps: int = 20, 
                  crf: int = 23) -> Path:
        """Nén và chuẩn hóa video bằng FFmpeg (có hỗ trợ NVENC)."""
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        output_filename = f"normalized_{input_path.name}"
        output_path = self.output_dir / output_filename

        use_nvenc = self._nvenc_available
        
        # Base commands
        cmd = ["ffmpeg", "-y", "-i", str(input_path)]
        
        # Video filters
        cmd += ["-vf", f"scale=-2:{resolution},fps={fps}"]
        
        if use_nvenc:
            logger.info(f"🚀 Using Hardware Acceleration (NVENC) for {input_path.name}")
            cmd += ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-b:v", "2M"]
        else:
            logger.info(f"🐌 Using Software Encoding (libx264) for {input_path.name}")
            cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "fast"]
            
        # Audio & Output
        cmd += ["-c:a", "aac", "-b:a", "128k", str(output_path)]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Successfully normalized: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise AppError(f"Failed to normalize video: {e.stderr}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_video_info(self, file_path: str | Path) -> dict:
        """Lấy thông tin video cơ bản dùng ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", str(file_path)
        ]
        try:
            import json
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except Exception as e:
            logger.warning(f"Could not get video info for {file_path}: {e}")
            return {}
