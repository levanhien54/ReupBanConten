from pathlib import Path
from typing import List, Optional
from moviepy.editor import VideoFileClip
from src.core.logging import get_logger
from src.core.types import TranscriptResult

logger = get_logger(__name__)

class ClipLibrary:
    """
    Quản lý việc chia nhỏ video thành các đơn vị clip 2 giây (Atomic Clips).
    Đảm bảo không cắt giữa câu thoại bằng cách dựa vào Transcript.
    """
    
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_atomic_clips(self, 
                              video_path: str | Path, 
                              transcript: TranscriptResult,
                              target_duration: float = 2.0) -> List[dict]:
        """
        Chia nhỏ video thành các clips ngắn ≈ 2s.
        """
        video_path = Path(video_path)
        video = VideoFileClip(str(video_path))
        duration = video.duration
        
        clips_metadata = []
        current_start = 0.0
        
        while current_start < duration:
            current_end = min(current_start + target_duration, duration)
            
            # Điều chỉnh điểm cắt dựa trên transcript (tránh cắt giữa câu)
            current_end = self._adjust_cut_point(current_end, transcript)
            
            clip_duration = current_end - current_start
            if clip_duration < 0.5: # Bỏ qua clip quá ngắn
                current_start = current_end
                continue
                
            clip_filename = f"{video_path.stem}_clip_{len(clips_metadata):03d}.mp4"
            clip_path = self.output_dir / clip_filename
            
            # Export clip (chỉ ghi metadata trong bước này để tối ưu)
            # Thực tế sẽ dùng ffmpeg để cắt nhanh mà không cần re-encode.
            
            clips_metadata.append({
                "source_video": str(video_path),
                "file_path": str(clip_path),
                "start_time": current_start,
                "end_time": current_end,
                "duration": clip_duration,
                "text": self._get_text_for_range(current_start, current_end, transcript)
            })
            
            current_start = current_end
            
        video.close()
        return clips_metadata

    def _adjust_cut_point(self, cut_time: float, transcript: TranscriptResult) -> float:
        """Tìm khoảng lặng gần nhất để cắt, tránh cắt giữa từ."""
        # Duyệt các segments để tìm điểm kết thúc của segment gần cut_time nhất
        for segment in transcript.segments:
            if segment.start < cut_time < segment.end:
                # Nếu rơi vào giữa một câu, ưu tiên cắt ở cuối câu đó
                return segment.end
        return cut_time

    def _get_text_for_range(self, start: float, end: float, transcript: TranscriptResult) -> str:
        """Lấy phần văn bản tương ứng với khoảng thời gian."""
        texts = []
        for segment in transcript.segments:
            if (segment.start >= start and segment.start < end) or \
               (segment.end > start and segment.end <= end):
                texts.append(segment.text)
        return " ".join(texts)
