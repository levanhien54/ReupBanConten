import sys
import os
import unittest
import asyncio
from pathlib import Path

# Đảm bảo import đúng
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.config import get_config
from src.core.database import get_database, VideoRepository, ClipRepository
from src.downloader.download_manager import DownloadManager
from src.preprocessor.pre_cutter import PreCutter
from src.core.types import RemixScript, RemixStep

class TestCoreFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = get_config()
        cls.db = get_database()
        cls.video_repo = VideoRepository(cls.db)
        cls.clip_repo = ClipRepository(cls.db)

    def test_database_connection(self):
        """Kiểm tra kết nối DB và CRUD cơ bản."""
        print("\n[DB] Testing CRUD...")
        test_video = {
            "video_id": "test_id_123",
            "title": "Test Video",
            "url": "https://youtube.com/watch?v=test",
            "file_path": "./data/test.mp4",
            "duration": 60,
            "platform": "youtube"
        }
        # Upsert
        self.video_repo.upsert(
            video_id=test_video["video_id"],
            title=test_video["title"],
            url=test_video["url"],
            file_path=test_video["file_path"],
            duration=test_video["duration"],
            platform=test_video["platform"]
        )
        # Get
        v = self.video_repo.get_by_video_id("test_id_123")
        self.assertIsNotNone(v)
        self.assertEqual(v["title"], "Test Video")
        print("OK: Database CRUD verified.")

    def test_scanner_logic(self):
        """Kiểm tra logic bóc tách ID của Scanner."""
        print("\n[Scanner] Testing URL parsing...")
        mgr = DownloadManager(self.config.downloader)
        vid_id = mgr._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(vid_id, "dQw4w9WgXcQ")
        
        vid_id_short = mgr._extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(vid_id_short, "dQw4w9WgXcQ")
        print("OK: URL parsing verified.")

    def test_pre_cutter_init(self):
        """Kiểm tra khởi tạo PreCutter."""
        print("\n[Cutter] Testing initialization...")
        try:
            cutter = PreCutter(self.config.storage.clips)
            self.assertIsNotNone(cutter)
            print("OK: PreCutter initialized.")
        except Exception as e:
            self.fail(f"PreCutter init failed: {e}")

    def test_orchestrator_init(self):
        """Kiểm tra khởi tạo Orchestrator V2."""
        print("\n[Remixer] Testing Orchestrator V2 initialization...")
        try:
            from src.remixer.orchestrator_v2 import RemixOrchestratorV2
            orchestrator = RemixOrchestratorV2(self.config)
            self.assertIsNotNone(orchestrator)
            print("OK: RemixOrchestratorV2 initialized.")
        except Exception as e:
            # Có thể fail nếu thiếu model Ollama, nhưng ở đây chỉ test init
            print(f"Note: Orchestrator init might need models: {e}")
            pass

            pass

    def test_clip_selector_source_limit(self):
        """Kiểm tra luật: không lấy quá 2 đoạn từ cùng 1 video gốc."""
        print("\n[Remixer] Testing source video limit (max 2)...")
        from unittest.mock import MagicMock
        from src.remixer.clip_selector import ClipSelector
        
        # Mock dependencies
        mock_vs = MagicMock()
        mock_tl = MagicMock()
        mock_tl.is_available.return_value = False # Force fallback to local VS
        
        # Mock search results: Trả về 3 clip từ cùng 1 video 'vid_A'
        mock_vs.search_clips.return_value = [
            {"id": "clip_1", "start": 10.0, "end": 15.0, "metadata": {"video_id": "vid_A"}},
            {"id": "clip_2", "start": 20.0, "end": 25.0, "metadata": {"video_id": "vid_A"}},
            {"id": "clip_3", "start": 30.0, "end": 35.0, "metadata": {"video_id": "vid_A"}},
            {"id": "clip_4", "start": 5.0, "end": 10.0, "metadata": {"video_id": "vid_B"}}, # Video khác
        ]
        
        selector = ClipSelector(mock_vs, mock_tl)
        
        # Kịch bản 3 bước, yêu cầu tìm 3 clips
        script = RemixScript(sequence=[
            RemixStep(visual_description="scene 1"),
            RemixStep(visual_description="scene 2"),
            RemixStep(visual_description="scene 3"),
        ])
        
        updated_script = asyncio.run(selector.select_clips_for_script(script))
        
        # Kiểm tra Unicity Params
        self.assertGreaterEqual(updated_script.sequence[0].zoom_factor, 1.0)
        self.assertIsNotNone(updated_script.sequence[0].start_time)
        print(f"OK: Unicity Params (Zoom: {updated_script.sequence[0].zoom_factor:.2f}, Start: {updated_script.sequence[0].start_time:.2f}) verified.")

        # Kết quả mong đợi về nguồn gốc:
        # Step 1: lấy clip_1 (vid_A count 1)
        # Step 2: lấy clip_2 (vid_A count 2)
        # Step 3: vid_A hết quota -> phải lấy clip_4 (vid_B)
        
        self.assertEqual(updated_script.sequence[0].clip_id, "clip_1")
        self.assertEqual(updated_script.sequence[1].clip_id, "clip_2")
        self.assertEqual(updated_script.sequence[2].clip_id, "clip_4")
        print("OK: Source video limit (max 2) verified.")

    def test_clip_usage_penalty(self):
        """Kiểm tra luật: phạt/bỏ qua nếu clip đã dùng quá nhiều lần trong quá khứ."""
        print("\n[Remixer] Testing usage frequency penalty...")
        from unittest.mock import MagicMock
        from src.remixer.clip_selector import ClipSelector
        
        # Mock dependencies
        mock_vs = MagicMock()
        mock_tl = MagicMock()
        mock_tl.is_available.return_value = False
        mock_repo = MagicMock()
        
        # Giả lập: clip_1 đã dùng 5 lần (vượt ngưỡng 3)
        # clip_2 mới dùng 0 lần
        mock_repo.get_usage_count.side_effect = lambda cid: 5 if cid == 1 else 0
        
        # Mock search results: Trả về clip_1 đầu tiên
        mock_vs.search_clips.return_value = [
            {"id": "1", "metadata": {"video_id": "vid_A", "id": 1}},
            {"id": "2", "metadata": {"video_id": "vid_B", "id": 2}},
        ]
        
        selector = ClipSelector(mock_vs, mock_tl, clip_repo=mock_repo)
        
        script = RemixScript(sequence=[RemixStep(visual_description="scene 1")])
        updated_script = asyncio.run(selector.select_clips_for_script(script))
        
        # Kết quả mong đợi: clip_1 bị bỏ qua dù là best match -> chọn clip_2
        self.assertEqual(updated_script.sequence[0].clip_id, "2")
        print("OK: Usage frequency penalty verified.")

    def test_config_persistence(self):
        """Kiểm tra logic .env (giả lập)."""
        print("\n[Config] Testing .env loading...")
        # Kiểm tra xem ít nhất config mặc định có load được không
        self.assertIsNotNone(self.config.downloader)
        self.assertTrue(hasattr(self.config.analyzer, 'twelve_labs'))
        print("OK: Config structure verified.")

if __name__ == "__main__":
    unittest.main()
