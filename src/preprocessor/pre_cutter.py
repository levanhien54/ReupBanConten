import subprocess
import re
import os
from pathlib import Path
from src.core.logging import get_logger
from src.core.errors import AppError

logger = get_logger(__name__)

class PreCutter:
    """
    Loại bỏ các đoạn "rác" (im lặng, màn hình đen) trước khi xử lý AI.
    Sử dụng FFmpeg silencedetect và blackdetect.
    """
    
    def __init__(self, output_dir: str | Path, 
                 silence_thresh: float = -40, 
                 min_silence_len: float = 0.5):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.silence_thresh = silence_thresh
        self.min_silence_len = min_silence_len

    def detect_silence(self, video_path: str | Path) -> list[tuple[float, float]]:
        """Phát hiện các khoảng im lặng."""
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-af", f"silencedetect=noise={self.silence_thresh}dB:d={self.min_silence_len}",
            "-f", "null", "-"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr
        
        # Parse output FFmpeg
        # [silencedetect @ 0x...] silence_start: 1.23
        # [silencedetect @ 0x...] silence_end: 4.56 | silence_duration: 3.33
        starts = re.findall(r"silence_start: ([\d.]+)", output)
        ends = re.findall(r"silence_end: ([\d.]+)", output)
        
        return list(zip(map(float, starts), map(float, ends)))

    def remove_junk(self, input_path: str | Path) -> Path:
        """Tạo bản video sạch bằng cách loại bỏ các đoạn rác."""
        input_path = Path(input_path)
        output_path = self.output_dir / f"clean_{input_path.name}"
        
        silences = self.detect_silence(input_path)
        if not silences:
            logger.info(f"Không phát hiện khoảng im lặng đáng kể trong {input_path.name}")
            return input_path

        logger.info(f"Phát hiện {len(silences)} khoảng im lặng trong {input_path.name}. Đang cắt bỏ...")
        
    def _get_duration(self, video_path: Path) -> float:
        """Lấy thời lượng video dùng ffprobe."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(res.stdout.strip())
        except:
            return 0.0

    def remove_junk(self, input_path: str | Path) -> Path:
        """Tạo bản video sạch bằng cách loại bỏ các đoạn rác."""
        input_path = Path(input_path)
        output_path = self.output_dir / f"clean_{input_path.name}"
        
        silences = self.detect_silence(input_path)
        if not silences:
            logger.info(f"Không phát hiện khoảng im lặng đáng kể trong {input_path.name}")
            return input_path

        logger.info(f"Phát hiện {len(silences)} khoảng im lặng trong {input_path.name}. Đang cắt bỏ...")
        
        duration = self._get_duration(input_path)
        
        if duration <= 0:
            logger.warning("Không lấy được thời lượng video. Bỏ qua bước xóa rác.")
            return input_path

        # Tính toán các đoạn "sạch" (không im lặng)
        keep_segments = []
        last_end = 0.0
        for start, end in silences:
            if start > last_end:
                keep_segments.append((last_end, start))
            last_end = end
        
        if last_end < duration:
            keep_segments.append((last_end, duration))

        if not keep_segments:
            logger.warning("Video toàn bộ là khoảng lặng! Trả về file gốc.")
            return input_path

        # Xây dựng filter_complex cho FFmpeg
        # Ví dụ: [0:v]trim=start=0:end=2,setpts=PTS-STARTPTS[v0]; [0:a]atrim=start=0:end=2,asetpts=PTS-STARTPTS[a0]; ...
        video_filters = []
        audio_filters = []
        inputs = ""
        
        for i, (start, end) in enumerate(keep_segments):
            video_filters.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
            audio_filters.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]")
            inputs += f"[v{i}][a{i}]"
        
        filter_str = ";".join(video_filters + audio_filters)
        filter_str += f";{inputs}concat=n={len(keep_segments)}:v=1:a=1[outv][outa]"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-filter_complex", filter_str,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-crf", "23", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Xóa rác thành công. File sạch: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Lỗi FFmpeg khi xóa rác: {e}")
            return input_path
