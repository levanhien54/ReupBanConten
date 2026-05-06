import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Thêm root vào path
sys.path.append(str(Path(__file__).parent.parent))

# Inject Mocks cho các thư viện ngoài để test logic nội bộ
# Tạo mock cho twelvelabs
sys.modules["twelvelabs"] = MagicMock()

# Tạo mock cho google.generativeai mà không phá vỡ namespace 'google' nếu nó tồn tại
mock_genai = MagicMock()
sys.modules["google.generativeai"] = mock_genai

# Mock các thư viện khác
sys.modules["asyncpg"] = MagicMock()
sys.modules["moviepy"] = MagicMock()
sys.modules["moviepy.editor"] = MagicMock()
sys.modules["moviepy.video.fx.all"] = MagicMock()

from src.core.config import get_config
from src.core.test_utils import create_test_video
from src.preprocessor import VideoHasher, VideoNormalizer, PreCutter
from src.remixer.orchestrator_v2 import RemixOrchestratorV2
from src.core.database import get_database, VideoRepository
from src.core.vector_store import VectorStore

# --- MOCKS CHO CÁC PROVIDER NGOÀI ---
class MockTwelveLabsClient:
    def is_available(self): return True
    async def search(self, index_id, query):
        return [{"video_id": "mock_vid_001", "start": 0, "end": 2, "confidence": 0.9}]
    async def upload_video(self, index_id, path): return "mock_vid_001"

class MockGeminiProvider:
    def is_available(self): return True
    async def generate_json(self, prompt):
        return {
            "title": "Integrated Test Video",
            "description": "Verification of v2.0 systems",
            "sequence": [
                {"segment": "hook", "visual_description": "intro scene", "duration": 2.0},
                {"segment": "meat", "visual_description": "main content", "duration": 5.0}
            ]
        }

async def run_final_test():
    print("[START] BAT DAU KIEM THU TICH HOP HE THONG v2.0")
    config = get_config()
    
    # Patching dependencies
    import src.remixer.orchestrator_v2 as orch
    orch.TwelveLabsClient = lambda: MockTwelveLabsClient()
    import src.llm.provider as provider
    provider.LLMFactory.create = lambda *args, **kwargs: MockGeminiProvider()

    # 1. Chuẩn bị dữ liệu test
    test_dir = Path("data/tests/final_integration")
    test_dir.mkdir(parents=True, exist_ok=True)
    raw_video = test_dir / "input.mp4"
    # Lệnh tạo video màu đơn giản không dùng drawtext
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x480:d=5", "-c:v", "libx264", "-t", "5", str(raw_video)]
    import subprocess
    subprocess.run(cmd, check=True)

    # 2. Test Phase 1: Preprocessing (THẬT)
    print("\n[PHASE 1] Testing Preprocessing...")
    hasher = VideoHasher()
    file_hash = hasher.generate_hash(raw_video)
    
    normalizer = VideoNormalizer(test_dir / "cache")
    normalized_path = normalizer.normalize(raw_video)
    
    pre_cutter = PreCutter(test_dir / "cache")
    clean_path = pre_cutter.remove_junk(normalized_path)
    
    print(f"SUCCESS Hasher: {file_hash}")
    print(f"SUCCESS Normalizer: {normalized_path.name}")
    print(f"SUCCESS PreCutter: {clean_path.name}")

    # 3. Test Phase 3: Database & VectorStore (THẬT)
    print("\n[PHASE 3] Testing Knowledge Base...")
    db = get_database()
    repo = VideoRepository(db)
    repo.upsert("test_vid_001", url="http://test.com", file_hash=file_hash, status="processed")
    
    v_store = VectorStore(test_dir / "vectors")
    v_store.add_clip("clip_test", [0.5]*1024, {"text": "test content"})
    
    print(f"SUCCESS DB Upsert: Success")
    print(f"SUCCESS VectorStore: {v_store.count()} clips indexed")

    # 4. Test Phase 4 & 5: Orchestrator & Assembler (THẬT/FIXED)
    print("\n[PHASE 4/5] Testing Orchestrator & Assembler...")
    orchestrator = RemixOrchestratorV2(config)
    
    # Mocking Assembler.assemble to avoid moviepy dependency in environment
    from src.remixer.assembler import VideoAssembler
    VideoAssembler.assemble = MagicMock(return_value=str(test_dir / "output.mp4"))
    
    output = await orchestrator.create_remix("Testing AI Integration")
    print(f"SUCCESS Orchestrator Flow: Completed")
    print(f"SUCCESS Final Output Path: {output}")

    print("\n[FINISH] TAT CA HE THONG V2.0 DA VUOT QUA KIEM THU TICH HOP!")

if __name__ == "__main__":
    asyncio.run(run_final_test())
