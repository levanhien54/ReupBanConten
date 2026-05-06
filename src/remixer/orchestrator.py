"""
Remix Orchestrator — Nhạc trưởng điều phối toàn bộ quy trình Remix.
Kết nối ScriptGenerator, VoiceoverEngine, Assembler và Effects.
"""
import os
import asyncio
from typing import Optional, List

from src.core.config import AppConfig
from src.core.logging import get_logger, log_duration
from src.core.types import VideoFolder, RemixScript, CommentaryScript
from src.remixer.script_generator import ScriptGenerator
from src.remixer.voiceover_engine import VoiceoverEngine
from src.remixer.assembler import VideoAssembler
from src.remixer.effects import EffectsManager, VoiceoverMixer, SubtitleRenderer
from src.llm.provider import LLMFactory

logger = get_logger(__name__)


class RemixOrchestrator:
    """Điều phối quy trình tạo video từ nhiều nguồn."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        
        # Initialize components
        llm_config = config.analyzer.llm
        llm = LLMFactory.create_with_fallback(
            primary=llm_config.provider,
            fallbacks=llm_config.fallback,
            model=llm_config.model,
        )
        
        self.script_gen = ScriptGenerator(config.remixer, config.cross_folder_remix, llm)
        self.vo_engine = VoiceoverEngine(config.voiceover)
        self.assembler = VideoAssembler(config.remixer.output)
        self.meme_mgr = EffectsManager(config.meme_effects)
        self.vo_mixer = VoiceoverMixer(config.voiceover)
        self.sub_renderer = SubtitleRenderer(config.remixer.effects.subtitles)

    @log_duration(msg_template="Full Remix Workflow {func_name}")
    async def run_remix(
        self,
        folders: list[VideoFolder],
        target_duration: float = 60.0,
        output_name: str = "remix_final.mp4",
        language: str = "vi"
    ) -> str:
        """Thực hiện quy trình remix đầy đủ."""
        
        # 1. Tạo thư mục làm việc tạm thời
        temp_dir = os.path.join(self._config.storage.cache, "remix_work")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 2. Sinh kịch bản (LLM)
        logger.info("Step 1: Generating Remix Script...")
        remix_script = await self.script_gen.generate_cross_folder_script(folders, target_duration)
        
        # 3. Sinh kịch bản bình luận (LLM)
        commentary_script = None
        if self._config.voiceover.enabled:
            logger.info(f"Step 2: Generating AI Commentary ({language})...")
            commentary_script = await self.script_gen.generate_commentary_script(remix_script, language)
            
            # 4. Chuyển text sang giọng nói (TTS)
            logger.info("Step 3: Generating Voiceover Audio...")
            vo_dir = os.path.join(temp_dir, "voiceover")
            await self.vo_engine.process_script(commentary_script, vo_dir, language)

        # 5. Lắp ghép video thô
        logger.info("Step 4: Assembling video segments...")
        raw_video_path = os.path.join(temp_dir, "raw_assembly.mp4")
        
        # Cần map clip_id/segment sang đường dẫn thực tế
        clip_paths = {}
        for folder in folders:
            for seg in folder.segments:
                clip_paths[seg.file_name] = seg.file_path

        self.assembler.assemble(remix_script, clip_paths, raw_video_path)

        # 6. Trộn Voiceover
        final_video_path = os.path.join(self._config.storage.outputs, output_name)
        current_video = raw_video_path

        if commentary_script:
            logger.info("Step 5: Mixing Voiceover and Ducking...")
            vo_video_path = os.path.join(temp_dir, "video_with_vo.mp4")
            current_video = self.vo_mixer.mix_voiceover(current_video, commentary_script, vo_video_path)
            
            # 6. Thêm phụ đề AI (CapCut Style)
            if self._config.remixer.effects.subtitles.enabled:
                logger.info("Step 6: Rendering Premium Subtitles...")
                sub_video_path = os.path.join(temp_dir, "video_with_sub.mp4")
                current_video = self.sub_renderer.apply_subtitles(current_video, commentary_script, sub_video_path)

        # 7. Áp dụng Memes (AI Driven)
        if self._config.meme_effects.enabled:
            logger.info("Step 7: AI Meme Placement & Effects...")
            meme_placements = await self.script_gen.generate_meme_script(
                remix_script, 
                self._config.meme_effects.assets_dir
            )
            
            if meme_placements:
                # Chuyển đổi MemePlacement list sang format dict mà EffectsManager yêu cầu
                placements_dict = []
                for p in meme_placements:
                    d = {
                        "time": p.time,
                        "sound_path": p.sound_path,
                        "image_path": p.image_path,
                        "position": p.position,
                        "duration": p.duration,
                        "volume": p.volume,
                        "size_ratio": p.size_ratio
                    }
                    placements_dict.append(d)

                meme_video_path = os.path.join(temp_dir, "video_with_memes.mp4")
                current_video = self.meme_mgr.apply_memes(current_video, placements_dict, meme_video_path)

        # 8. Di chuyển kết quả cuối cùng
        if current_video != final_video_path:
            import shutil
            shutil.copy2(current_video, final_video_path)
            
        logger.info(f"✅ Remix Complete! Saved to: {final_video_path}")
        return final_video_path
