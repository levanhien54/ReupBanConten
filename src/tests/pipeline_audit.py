"""
Pipeline Audit Tool — Kiểm tra chất lượng và tính ổn định của từng giai đoạn.
"""
import os
import sys
import asyncio
import subprocess
from typing import Dict, List

# Thêm root vào path
sys.path.append(os.getcwd())

from src.core.config import load_config
from src.core.logging import setup_logging, get_logger
from src.remixer.ass_generator import ASSGenerator
from src.remixer.effects import SubtitleRenderer, VoiceoverMixer
from src.core.types import CommentaryScript, CommentarySegment, RemixScript, RemixStep

logger = get_logger("Audit")

async def test_stage_1_system():
    """Kiểm tra các công cụ hệ thống."""
    results = {}
    
    # FFmpeg
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        results["FFmpeg"] = "PASS" if res.returncode == 0 else "FAIL"
    except:
        results["FFmpeg"] = "MISSING"

    # ImageMagick (Cho MoviePy)
    try:
        # MoviePy thường dùng 'magick' hoặc 'convert'
        res = subprocess.run(["magick", "-version"], capture_output=True, text=True)
        results["ImageMagick"] = "PASS" if res.returncode == 0 else "FAIL"
    except:
        results["ImageMagick"] = "MISSING"

    return results

async def test_stage_2_ai():
    """Kiểm tra kết nối AI."""
    config = load_config()
    results = {}
    
    # Test OpenAI/Anthropic keys (chỉ check xem có trong env không)
    results["OpenAI_Key"] = "SET" if os.getenv("OPENAI_API_KEY") else "NOT_SET"
    results["ElevenLabs_Key"] = "SET" if os.getenv("ELEVENLABS_API_KEY") else "NOT_SET"
    
    # Test Ollama
    try:
        import ollama
        # Thử list models
        models = ollama.list()
        results["Ollama"] = f"PASS ({len(models.get('models', []))} models)"
    except Exception as e:
        results["Ollama"] = f"FAIL ({str(e)})"
        
    return results

async def test_stage_3_rendering():
    """Kiểm tra logic render phụ đề và audio."""
    config = load_config()
    results = {}
    
    # 1. Test ASS Generation
    try:
        ass_gen = ASSGenerator(config.remixer.effects.subtitles)
        mock_script = CommentaryScript(
            segments=[CommentarySegment(text="Test Subtitle", start_time=0.0, duration_estimate=2.0)],
            total_segments=1
        )
        test_ass = "data/cache/test_audit.ass"
        os.makedirs("data/cache", exist_ok=True)
        ass_gen.generate(mock_script, test_ass)
        results["ASS_Generator"] = "PASS" if os.path.exists(test_ass) else "FAIL"
    except Exception as e:
        results["ASS_Generator"] = f"ERROR ({str(e)})"

    return results

async def run_full_audit():
    setup_logging()
    print("\n" + "="*50)
    print("REUPBANCONTEN - FULL PIPELINE AUDIT")
    print("="*50)
    
    print("\n[Stage 1] Checking System Tools...")
    sys_res = await test_stage_1_system()
    for k, v in sys_res.items(): print(f"  - {k:15}: {v}")
    
    print("\n[Stage 2] Checking AI Connectivity...")
    ai_res = await test_stage_2_ai()
    for k, v in ai_res.items(): print(f"  - {k:15}: {v}")
    
    print("\n[Stage 3] Checking Component Logic...")
    logic_res = await test_stage_3_rendering()
    for k, v in logic_res.items(): print(f"  - {k:15}: {v}")
    
    print("\n" + "="*50)
    print("Audit Complete.")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(run_full_audit())
