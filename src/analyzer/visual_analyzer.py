"""
Visual Analyzer — Sử dụng mô hình thị giác (LLaVA) để mô tả nội dung video.
Giúp LLM "thấy" được clips để lựa chọn chính xác theo ngữ cảnh.
"""
import os
import base64
import cv2
import ollama
from typing import Optional

from src.core.logging import get_logger, log_duration
from src.core.types import SegmentFile

logger = get_logger(__name__)

class VisualAnalyzer:
    """Phân tích nội dung hình ảnh của clips."""

    def __init__(self, model: str = "llava:7b") -> None:
        self._model = model

    @log_duration(msg_template="Visual analysis {func_name}")
    async def analyze_segment(self, segment: SegmentFile) -> str:
        """Trích xuất 1 khung hình và nhờ AI mô tả nội dung."""
        if not os.path.exists(segment.file_path):
            return ""

        # 1. Trích xuất khung hình giữa (keyframe)
        frame_path = self._extract_keyframe(segment.file_path)
        if not frame_path:
            return ""

        try:
            # 2. Đọc ảnh và encode base64
            with open(frame_path, "rb") as img_file:
                img_data = base64.b64encode(img_file.read()).decode('utf-8')

            # 3. Gọi Ollama LLaVA
            response = ollama.generate(
                model=self._model,
                prompt="Describe this video frame briefly (max 20 words). Focus on main subjects, actions and mood.",
                images=[img_data],
                stream=False
            )
            
            description = response.get('response', '').strip()
            logger.info(f"Visual Description for {segment.file_name}: {description}")
            
            # Dọn dẹp ảnh tạm
            if os.path.exists(frame_path):
                os.remove(frame_path)
                
            return description

        except Exception as e:
            logger.error(f"Visual analysis failed for {segment.file_name}: {e}")
            return ""

    def _extract_keyframe(self, video_path: str) -> Optional[str]:
        """Lấy 1 khung hình từ giữa video."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        mid_frame = total_frames // 2
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        
        if not ret:
            cap.release()
            return None
            
        temp_path = video_path + ".jpg"
        cv2.imwrite(temp_path, frame)
        cap.release()
        return temp_path
