"""
Voiceover Engine — Chuyển kịch bản bình luận thành âm thanh.
Hỗ trợ ElevenLabs (Premium) và Edge-TTS (Free).
"""
import os
import asyncio
from typing import Optional

from src.core.config import VoiceoverConfig
from src.core.logging import get_logger, log_duration
from src.core.types import CommentaryScript, CommentarySegment

logger = get_logger(__name__)


EDGE_TTS_VOICES = {
    "vi": "vi-VN-HoaiMyNeural",
    "en": "en-US-EmmaNeural",
    "en-US": "en-US-EmmaNeural",
    "en-GB": "en-GB-SoniaNeural",
    "fr": "fr-FR-DeniseNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "de-DE": "de-DE-KatjaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "pt": "pt-BR-FranciscaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "es": "es-ES-ElviraNeural",
}


class VoiceoverEngine:
    """Công cụ tạo giọng nói AI từ kịch bản."""

    def __init__(self, config: VoiceoverConfig) -> None:
        self._config = config
        self._elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")

    @log_duration(msg_template="Voiceover processing {func_name}")
    async def process_script(
        self, 
        script: CommentaryScript, 
        output_dir: str,
        language_code: str = "vi"
    ) -> CommentaryScript:
        """
        Tạo file âm thanh cho tất cả các đoạn trong kịch bản.
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Xử lý Intro
        if script.intro:
            script.intro.audio_path = await self.generate_audio(
                script.intro.text, 
                os.path.join(output_dir, "intro.mp3"),
                language_code
            )

        # 2. Xử lý Segments
        tasks = []
        for i, seg in enumerate(script.segments):
            path = os.path.join(output_dir, f"segment_{i+1:03d}.mp3")
            tasks.append(self.generate_audio(seg.text, path, language_code))
        
        audio_paths = await asyncio.gather(*tasks)
        for seg, path in zip(script.segments, audio_paths):
            seg.audio_path = path

        # 3. Xử lý Outro
        if script.outro:
            script.outro.audio_path = await self.generate_audio(
                script.outro.text, 
                os.path.join(output_dir, "outro.mp3"),
                language_code
            )

        return script

    async def generate_audio(
        self, 
        text: str, 
        output_path: str, 
        language_code: str
    ) -> Optional[str]:
        """Tạo audio từ text dùng provider được cấu hình."""
        if not text:
            return None

        try:
            if self._config.provider == "elevenlabs" and self._elevenlabs_api_key:
                return await self._generate_elevenlabs(text, output_path)
            else:
                # Fallback to Edge-TTS (Free & Robust)
                return await self._generate_edge_tts(text, output_path, language_code)
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

    async def _generate_elevenlabs(self, text: str, output_path: str) -> str:
        """Tạo audio dùng ElevenLabs API."""
        from elevenlabs.client import AsyncElevenLabs
        
        client = AsyncElevenLabs(api_key=self._elevenlabs_api_key)
        
        # Lấy voice từ config hoặc dùng mặc định
        voice_id = self._config.elevenlabs.default_voice or "Rachel" # default
        
        audio_generator = await client.generate(
            text=text,
            voice=voice_id,
            model=self._config.elevenlabs.model,
            voice_settings={
                "stability": self._config.elevenlabs.stability,
                "similarity_boost": self._config.elevenlabs.similarity_boost,
                "style": self._config.elevenlabs.style,
            }
        )
        
        # Save audio generator to file
        with open(output_path, "wb") as f:
            async for chunk in audio_generator:
                f.write(chunk)
                
        return output_path

    async def _generate_edge_tts(self, text: str, output_path: str, lang: str) -> str:
        """Tạo audio dùng Edge-TTS (Microsoft Azure Free API)."""
        import edge_tts
        
        # Bản đồ ngôn ngữ sang giọng nói Edge-TTS mặc định
        voice = EDGE_TTS_VOICES.get(lang, EDGE_TTS_VOICES["vi"])
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        
        return output_path
