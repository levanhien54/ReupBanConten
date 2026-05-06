from typing import Optional, List, Dict
from src.llm.provider import LLMProvider
from src.core.logging import get_logger
from src.core.types import RemixScript, RemixStrategy

logger = get_logger(__name__)

class ScriptEngine:
    """
    Đạo diễn AI: Chịu trách nhiệm viết kịch bản remix dựa trên kho clip có sẵn.
    Sử dụng chiến thuật Viral Shorts: Hook (5s) -> Meat (45s) -> CTA (10s).
    """
    
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def generate_viral_script(self, 
                                    topic: str, 
                                    target_duration: float = 60.0) -> RemixScript:
        """
        Tạo kịch bản remix sử dụng Gemini 1.5 Flash.
        """
        prompt = f"""
        Bạn là một chuyên gia sáng tạo nội dung viral trên TikTok/Shorts.
        Hãy viết kịch bản remix cho video về chủ đề: "{topic}".
        
        Yêu cầu cấu trúc:
        1. HOOK (0-5s): Thu hút sự chú ý ngay lập tức bằng hình ảnh hoặc câu nói gây sốc/tò mò.
        2. MEAT (5-55s): Triển khai nội dung chính, giữ nhịp độ nhanh (mỗi clip < 3s).
        3. CTA (55-60s): Kêu gọi hành động (Subscribe/Like).
        
        Hãy mô tả chi tiết yêu cầu hình ảnh cho từng phân đoạn để tôi có thể tìm kiếm trong kho clip.
        Đồng thời, viết câu bình luận (voiceover) thật cuốn hút cho từng phân cảnh vào trường "commentary_text".
        
        Trả về định dạng JSON:
        {{
            "title": "Tiêu đề video",
            "description": "Mô tả ngắn",
            "sequence": [
                {{
                    "segment": "hook",
                    "visual_description": "mô tả hình ảnh cần tìm",
                    "commentary_text": "Câu nói voiceover cho cảnh này",
                    "duration": 2.0,
                    "notes": "lý do chọn"
                }},
                ...
            ]
        }}
        """
        
        logger.info(f"Generating viral script for topic: {topic}")
        try:
            script_data = await self.llm.generate_json(prompt)
            return RemixScript.model_validate(script_data)
        except Exception as e:
            logger.error(f"Lỗi khi tạo kịch bản AI: {e}")
            raise
