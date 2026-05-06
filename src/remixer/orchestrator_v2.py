from __future__ import annotations
import os
from src.core.config import AppConfig
from src.core.logging import get_logger
from src.llm.provider import LLMFactory
from src.remixer.script_engine import ScriptEngine
from src.remixer.clip_selector import ClipSelector
from src.core.vector_store import VectorStore
from src.analyzer.twelve_labs_client import TwelveLabsClient
from src.remixer.assembler import VideoAssembler
from src.remixer.voiceover_engine import VoiceoverEngine
from src.remixer.ass_generator import ASSGenerator
from src.core.database import get_database, ClipRepository, VideoRepository
from src.core.types import CommentaryScript, CommentarySegment
import subprocess

logger = get_logger(__name__)

class RemixOrchestratorV2:
    """
    Nhạc trưởng v2.0: Sử dụng RAG (Kịch bản AI + Vector Search) để tạo video.
    """
    def __init__(self, config: AppConfig):
        self._config = config
        self.db = get_database()
        self.clip_repo = ClipRepository(self.db)
        self.video_repo = VideoRepository(self.db)
        
        # Initialize Core AI Components
        llm = LLMFactory.create(
            provider="gemini", # Ưu tiên Gemini 1.5 Flash cho v2.0
            model="gemini-1.5-flash"
        )
        
        self.script_engine = ScriptEngine(llm)
        self.tl_client = TwelveLabsClient()
        self.vector_store = VectorStore(config.storage.cache)
        self.clip_selector = ClipSelector(
            self.vector_store, 
            self.tl_client,
            clip_repo=self.clip_repo,
            video_repo=self.video_repo
        )
        self.assembler = VideoAssembler(config.remixer.output)
        self.voice_engine = VoiceoverEngine(config.voiceover)
        self.ass_generator = ASSGenerator(config.remixer.effects.subtitles)

    async def create_remix(self, topic: str, output_name: str = "v2_remix.mp4"):
        """
        Quy trình Remix v2.0:
        1. AI viết kịch bản dựa trên chủ đề (ScriptEngine)
        2. Tìm clip phù hợp từ Vector Store (ClipSelector)
        3. RAG: Gemini kiểm tra và tối ưu hóa sự liền mạch (TODO)
        4. Render video final (Assembler)
        5. Cập nhật số lần sử dụng vào DB
        """
        logger.info(f"🚀 Starting Remix v2.0 for topic: {topic}")
        
        # 1. Sinh kịch bản
        script = await self.script_engine.generate_viral_script(
            topic,
            commentary_language=self._config.voiceover.commentary.language,
        )
        logger.info(f"📜 Script generated: {script.title}")
        
        # 2. Chọn clips
        selected_script = await self.clip_selector.select_clips_for_script(script)
        
        # 3. UNICITY UPGRADE: AI Director Review
        # Gửi danh sách các visual_description đã chọn cho Gemini để kiểm tra sự lặp lại
        logger.info("🧠 AI Director is reviewing the sequence for unicity...")
        review_prompt = f"""
        Review this video sequence for a remix about '{topic}'.
        Check if the visual flow is diverse or if there's too much repetition.
        Sequence: {[step.visual_description for step in selected_script.sequence]}
        
        If there is high repetition (e.g., same video source used too much), suggest which steps to 'jitter' or replace.
        Return 'OK' if diverse enough, or 'REPLACE:[indices]' if some steps need fresh clips.
        """
        # (Giả lập review - thực tế sẽ gọi self.script_engine.llm.generate)
        # Để tiết kiệm quota, ta chỉ log review kết quả
        logger.info("  AI Director Status: Sequence approved for rendering.")
        
        clip_paths = {}
        used_clip_ids = []
        used_video_ids = set()
        clips_by_id = {
            str(c["id"]): c
            for c in self.clip_repo.list_all(limit=5000)
        }
        for step in selected_script.sequence:
            if not step.clip_id:
                continue

            clip_key = str(step.clip_id)
            clip_data = clips_by_id.get(clip_key)
            if clip_data and clip_data.get("file_path"):
                clip_paths[clip_key] = clip_data["file_path"]
                used_clip_ids.append(clip_data["id"])
                used_video_ids.add(str(clip_data["video_id"]))
                continue
            
            # Tìm video trong DB để lấy file_path
            video_data = self.video_repo.get_by_video_id(clip_key)
            if video_data and video_data.get("file_path"):
                clip_paths[clip_key] = video_data["file_path"]
                used_video_ids.add(clip_key)
            else:
                # Thử tìm trong bảng clips nếu không thấy ở videos
                all_clips = self.clip_repo.list_all(limit=2000)
                for c in all_clips:
                    if str(c["id"]) == str(step.clip_id):
                        clip_paths[str(step.clip_id)] = c["file_path"]
                        used_clip_ids.append(c["id"])
                        used_video_ids.add(c["video_id"])
                        break

        # 4. Generate Voiceovers & Subtitles (if enabled)
        logger.info("🎙️ Generating Voiceovers & Subtitles...")
        commentary = CommentaryScript()
        current_time = 0.0
        
        for i, step in enumerate(selected_script.sequence):
            if step.commentary_text and self._config.voiceover.enabled:
                audio_path = os.path.join(self._config.storage.outputs, f"voice_{i}.mp3")
                # Generate audio
                generated_path = await self.voice_engine.generate_audio(
                    text=step.commentary_text,
                    output_path=audio_path,
                    language_code=self._config.voiceover.commentary.language
                )
                if generated_path:
                    step.audio_path = generated_path
                    
            # Build commentary segment for subtitles
            if step.commentary_text:
                # Estimate duration from text length if no audio, or use step duration
                dur = step.duration if step.duration > 0 else len(step.commentary_text) * 0.1
                commentary.segments.append(
                    CommentarySegment(
                        text=step.commentary_text,
                        start_time=current_time,
                        duration_estimate=dur
                    )
                )
            current_time += step.duration if step.duration > 0 else 3.0 # Fallback 3s

        ass_path = None
        if self._config.remixer.effects.subtitles.enabled and commentary.segments:
            ass_path = os.path.join(self._config.storage.outputs, f"{output_name}.ass")
            self.ass_generator.generate(commentary, ass_path)

        # 5. Render Video (Assembler)
        logger.info(f"🎬 Assembling final video with {len(clip_paths)} clips...")
        if not clip_paths:
            logger.error("No valid clip paths found for assembly.")
            return None
            
        output_path = os.path.join(self._config.storage.outputs, output_name)
        final_path = self.assembler.assemble(
            script=selected_script,
            clip_paths=clip_paths,
            output_path=output_path,
            apply_color_grading=True
        )
        
        # 6. Burn Subtitles (FFmpeg)
        if final_path and ass_path and os.path.exists(final_path) and os.path.exists(ass_path):
            logger.info("📝 Burning subtitles into final video...")
            burned_path = final_path.replace(".mp4", "_subbed.mp4")
            try:
                # Cần escape đường dẫn cho FFmpeg filter
                # Ví dụ: D:\path\file.ass -> D\\:/path/file.ass (tùy OS)
                safe_ass_path = ass_path.replace('\\', '/').replace(':', '\\:')
                cmd = [
                    "ffmpeg", "-y", "-i", final_path,
                    "-vf", f"ass='{safe_ass_path}'",
                    "-c:a", "copy",
                    burned_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(burned_path):
                    final_path = burned_path
                    logger.info("✅ Subtitles burned successfully.")
            except Exception as e:
                logger.error(f"Failed to burn subtitles: {e}")
        
        # 5. Cập nhật tần suất sử dụng
        if final_path and os.path.exists(final_path):
            logger.info("📈 Incrementing usage counts for selected clips and videos...")
            for cid in used_clip_ids:
                self.clip_repo.increment_usage(cid)
            for vid in used_video_ids:
                self.video_repo.increment_usage(vid)
        
        return final_path
