import asyncio
import os
import sqlite3
from unittest.mock import patch, MagicMock, AsyncMock

from src.core.config import AppConfig
from src.core.database import get_database, ClipRepository, VideoRepository
from src.remixer.orchestrator_v2 import RemixOrchestratorV2
from src.core.types import RemixScript, RemixStep

# Create a dummy mp4 for testing
DUMMY_MP4 = "tests/dummy_v2.mp4"
OUTPUT_MP4 = "data/outputs/v2_test_remix.mp4"

async def run_test():
    print("Setting up E2E Test for V2 Pipeline...")
    
    # 1. Ensure dummy video exists
    if not os.path.exists(DUMMY_MP4):
        os.makedirs("tests", exist_ok=True)
        import subprocess
        print("Generating dummy mp4 using FFmpeg...")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=10:size=1280x720:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=10",
            "-c:v", "libx264", "-c:a", "aac", DUMMY_MP4
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    config = AppConfig()
    config.storage.outputs = "data/outputs"
    os.makedirs(config.storage.outputs, exist_ok=True)
    
    # Enable voiceover and subtitles
    config.voiceover.enabled = True
    config.remixer.effects.subtitles.enabled = True
    config.remixer.effects.subtitles.preset_style = "modern_white"

    db = get_database()
    video_repo = VideoRepository(db)
    
    # Insert dummy video into DB
    try:
        db.execute(
            "INSERT INTO videos (video_id, url, file_path) VALUES (?, ?, ?)",
            ("dummy_v2_id", "http://dummy", DUMMY_MP4)
        )
        db._get_connection().commit()
    except sqlite3.IntegrityError:
        pass # Already exists

    orchestrator = RemixOrchestratorV2(config)
    
    # Mock ScriptEngine to return a fixed script
    mock_script = RemixScript(
        title="Test V2",
        sequence=[
            RemixStep(
                visual_description="A test scene",
                commentary_text="Xin chào các bạn, đây là video thử nghiệm hệ thống.",
                duration=5.0
            )
        ]
    )
    orchestrator.script_engine.generate_viral_script = AsyncMock(return_value=mock_script)
    
    # Mock ClipSelector to return the dummy clip
    async def mock_select(script):
        script.sequence[0].clip_id = "dummy_v2_id"
        script.sequence[0].start_time = 0.0
        script.sequence[0].end_time = 5.0
        return script

    orchestrator.clip_selector.select_clips_for_script = AsyncMock(side_effect=mock_select)
    
    print("Running Orchestrator create_remix()...")
    final_path = await orchestrator.create_remix("Test Topic", "v2_test_remix.mp4")
    
    if final_path and os.path.exists(final_path):
        print(f"SUCCESS! Final video generated at: {final_path}")
        print("Mở file để kiểm tra xem có lồng tiếng và phụ đề hay không.")
    else:
        print("FAILED to generate video.")

if __name__ == "__main__":
    asyncio.run(run_test())

