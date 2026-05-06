from typing import List, Dict
import random
from src.core.vector_store import VectorStore
from src.analyzer.twelve_labs_client import TwelveLabsClient
from src.core.logging import get_logger
from src.core.types import RemixScript, RemixStep
from src.core.database import ClipRepository, VideoRepository

logger = get_logger(__name__)

class ClipSelector:
    """
    Kết nối kịch bản AI với kho clip vật lý thông qua Vector Search.
    """
    
    def __init__(self, vector_store: VectorStore, tl_client: TwelveLabsClient, 
                 clip_repo: ClipRepository = None,
                 video_repo: VideoRepository = None,
                 index_name: str = "reup_ban_conten_v2"):
        self.vector_store = vector_store
        self.tl = tl_client
        self.clip_repo = clip_repo
        self.video_repo = video_repo
        self.index_name = index_name

    async def select_clips_for_script(self, script: RemixScript) -> RemixScript:
        """Tìm kiếm clips thực tế cho từng bước trong kịch bản."""
        video_usage = {} # video_id -> count
        selected_clip_ids = set() # Tránh dùng trùng clip_id
        MAX_PER_VIDEO = 2
        MAX_TOTAL_USAGE = 3 # Phạt nếu clip được dùng quá 3 lần tổng cộng
        
        for step in script.sequence:
            if not step.visual_description:
                continue
                
            logger.info(f"Searching clips for: {step.visual_description}")
            
            # 1. Thử Twelve Labs Semantic Search (Marengo)
            search_results = []
            if self.tl.is_available():
                search_results = await self.tl.search(self.index_name, step.visual_description)
            
            # 2. Fallback sang local VectorStore nếu TL không có kết quả
            if not search_results:
                logger.info(f"  Fallback to local VectorStore for: {step.visual_description}")
                search_results = self.vector_store.search_clips(
                    query_embedding=[0.1]*1024, # Dummy embedding
                    limit=10,
                    filters={"visual_description": {"$contains": step.visual_description.split()[0]}} if step.visual_description else None
                )
            
            # 3. Lọc kết quả dựa trên luật:
            # - Không lấy trùng clip_id
            # - Không lấy quá 2 đoạn từ cùng 1 video gốc (trong 1 dự án)
            # - Phạt/Bỏ qua nếu tần suất sử dụng quá cao (Database check)
            selected_clip = None
            for match in search_results:
                clip_id = match.get("id") or match.get("video_id")
                metadata = match.get("metadata") or {}
                if metadata.get("id"):
                    clip_id = metadata["id"]
                elif metadata.get("clip_id"):
                    clip_id = metadata["clip_id"]
                
                # Xác định video gốc (source video)
                vid_id = match.get("video_id") or metadata.get("video_id") or match.get("id")
                
                # 3a. Kiểm tra trùng clip trong dự án hiện tại
                if clip_id in selected_clip_ids:
                    continue

                # 3b. Kiểm tra giới hạn video gốc TRONG DỰ ÁN (Max 2 segments per video)
                count = video_usage.get(vid_id, 0)
                if count >= MAX_PER_VIDEO:
                    logger.debug(f"  Skipping video {vid_id} (Project quota full)")
                    continue

                # 3c. Kiểm tra tần suất sử dụng lịch sử của CLIP từ Database
                if self.clip_repo and isinstance(clip_id, (int, str)) and str(clip_id).isdigit():
                    db_usage = self.clip_repo.get_usage_count(int(clip_id))
                    if db_usage >= MAX_TOTAL_USAGE:
                        logger.info(f"  Penalizing clip {clip_id}: High total usage ({db_usage})")
                        continue

                # 3d. Kiểm tra tần suất sử dụng lịch sử của VIDEO GỐC từ Database
                if self.video_repo:
                    global_vid_usage = self.video_repo.get_usage_count(str(vid_id))
                    if global_vid_usage >= 10: # Giả định giới hạn 10 lần dùng video gốc
                        logger.info(f"  Penalizing source video {vid_id}: High global usage ({global_vid_usage})")
                        continue

                # Nếu đạt mọi tiêu chuẩn
                selected_clip = match
                video_usage[vid_id] = count + 1
                selected_clip_ids.add(clip_id)
                logger.info(f"  Selected clip {clip_id} from video {vid_id}")
                break

            if selected_clip:
                metadata = selected_clip.get("metadata") or {}
                selected_id = (
                    metadata.get("clip_id")
                    or metadata.get("id")
                    or selected_clip.get("clip_id")
                    or selected_clip.get("id")
                    or selected_clip.get("video_id")
                )
                if selected_id is not None:
                    step.clip_id = int(selected_id) if str(selected_id).isdigit() else selected_id

                # --- UNICITY UPGRADE: Temporal Jitter & Visual Params ---
                if "start" in selected_clip:
                    # Thêm độ lệch ngẫu nhiên +/- 0.3s để tránh Content ID nhận diện mốc thời gian cũ
                    jitter = random.uniform(-0.3, 0.3)
                    step.start_time = max(0, selected_clip['start'] + jitter)
                    step.end_time = selected_clip['end'] + jitter
                    step.notes = f"TL Match (Jitter: {jitter:.2f}s)"
                
                # Tham số biến đổi hình ảnh ngẫu nhiên
                step.zoom_factor = random.uniform(1.0, 1.05) # Zoom nhẹ 0-5%
                step.brightness_factor = random.uniform(0.95, 1.05) # Sáng/Tối nhẹ
                step.contrast_factor = random.uniform(0.98, 1.02) # Tương phản nhẹ
                step.mirror = random.choice([True, False]) if random.random() < 0.2 else False # 20% lật ngang
                
                logger.info(f"  Final selection with Uniqueness Params: {step.clip_id}")
            else:
                logger.warning(f"  No available clips found for: {step.visual_description}")
                
        return script
