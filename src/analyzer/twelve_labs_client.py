from __future__ import annotations
import os
import asyncio
from pathlib import Path
from typing import Optional, Any
from src.core.logging import get_logger
from src.core.errors import AppError

logger = get_logger(__name__)

class TwelveLabsClient:
    """
    Client tích hợp Twelve Labs API để phân tích video sâu (embeddings, Marengo, Pegasus).
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TWELVELABS_API_KEY")
        if not self.api_key:
            logger.warning("TWELVELABS_API_KEY không được tìm thấy. Twelve Labs features sẽ bị vô hiệu hóa.")
            self.client = None
        else:
            try:
                from twelvelabs import TwelveLabs
                self.client = TwelveLabs(api_key=self.api_key)
            except ImportError:
                logger.warning("twelvelabs package is not installed. Twelve Labs features disabled.")
                self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    async def create_index(self, index_name: str, engines: list[dict] = None) -> str:
        """Tạo một index mới để lưu trữ và tìm kiếm video."""
        if not self.is_available():
            raise AppError("Twelve Labs client is not initialized.")
            
        if engines is None:
            engines = [
                {"engine_name": "marengo2.6", "engine_options": ["visual", "conversation", "text_in_video", "logo"]},
                {"engine_name": "pegasus1", "engine_options": ["visual", "conversation"]}
            ]
            
        try:
            index = await asyncio.to_thread(
                self.client.index.create,
                name=index_name,
                engines=engines,
                addon_options=["thumbnail"]
            )
            logger.info(f"Created Twelve Labs Index: {index.name} (ID: {index.id})")
            return index.id
        except Exception as e:
            logger.error(f"Lỗi khi tạo Twelve Labs Index: {e}")
            raise AppError(f"Twelve Labs Index creation failed: {e}")

    async def upload_video(self, index_id: str, video_path: str | Path) -> str:
        """Upload và index video."""
        if not self.is_available():
            raise AppError("Twelve Labs client is not initialized.")
            
        video_path = Path(video_path)
        try:
            task = await asyncio.to_thread(
                self.client.task.create,
                index_id=index_id, file=str(video_path)
            )
            logger.info(f"Uploading video {video_path.name} (Task ID: {task.id})")
            
            # Đợi hoàn thành (polling) trong thread để không block event loop
            def on_status_change(status):
                logger.info(f"  Task {task.id} status: {status}")

            await asyncio.to_thread(task.wait_for_done, callback=on_status_change)
            
            if task.status != "ready":
                raise AppError(f"Task failed with status: {task.status}")
                
            logger.info(f"Video {video_path.name} is ready in Twelve Labs index.")
            return task.video_id
        except Exception as e:
            logger.error(f"Lỗi khi upload video lên Twelve Labs: {e}")
            raise AppError(f"Twelve Labs upload failed: {e}")

    async def generate_summary(self, video_id: str) -> str:
        """Sử dụng Pegasus engine để tạo tóm tắt video."""
        if not self.is_available():
            return "Twelve Labs not available."
            
        try:
            res = await asyncio.to_thread(
                self.client.generate.summarize,
                video_id=video_id, type="summary"
            )
            return res.summary
        except Exception as e:
            logger.error(f"Lỗi khi tạo tóm tắt Pegasus: {e}")
            return ""

    async def search(self, index_id: str, query: str) -> list[dict]:
        """Semantic search trong video index."""
        if not self.is_available():
            return []
            
        try:
            search_results = await asyncio.to_thread(
                self.client.search.query,
                index_id=index_id,
                query_text=query,
                options=["visual", "conversation"]
            )
            
            results = []
            for res in search_results.data:
                results.append({
                    "video_id": res.video_id,
                    "start": res.start,
                    "end": res.end,
                    "confidence": res.confidence,
                    "metadata": res.metadata
                })
            return results
        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm Twelve Labs: {e}")
            return []
