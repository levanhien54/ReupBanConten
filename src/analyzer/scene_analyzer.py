from __future__ import annotations
from typing import List, Dict
from src.analyzer.twelve_labs_client import TwelveLabsClient
from src.core.logging import get_logger
from src.core.types import KeyMoment

logger = get_logger(__name__)

class SceneAnalyzer:
    """
    Sử dụng Twelve Labs để phân tích sâu từng cảnh trong video.
    """
    
    def __init__(self, tl_client: TwelveLabsClient):
        self.tl = tl_client

    async def analyze_scenes(self, video_id: str) -> list[KeyMoment]:
        """
        Phân tích và trả về danh sách các cảnh (Key Moments) từ Twelve Labs.
        """
        if not self.tl.is_available():
            return []
            
        try:
            # Sử dụng tính năng Generate Chapter hoặc Moments nếu có, 
            # hoặc parse từ search results với prompt cụ thể.
            # Ở đây giả định dùng Pegasus Summarize cho video_id
            
            summary = await self.tl.generate_summary(video_id)
            logger.info(f"Video Summary (Pegasus): {summary[:100]}...")
            
            # TODO: Twelve Labs v1.2 có API cho video moments/chapters chuyên dụng.
            # Chúng ta sẽ sử dụng search với query "highlights" hoặc "main events"
            highlights = await self.tl.search(self.tl.index_name, "highlights and key moments in this video")
            
            moments = []
            for h in highlights:
                moments.append(KeyMoment(
                    start_time=h["start"],
                    end_time=h["end"],
                    description=h.get("metadata", {}).get("text", "Highlight"),
                    energy_score=h.get("confidence", 0.5)
                ))
            
            return moments
        except Exception as e:
            logger.error(f"Lỗi khi phân tích cảnh Twelve Labs: {e}")
            return []
