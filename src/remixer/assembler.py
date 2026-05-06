"""
Video Assembler — Nối các clips dựa trên RemixScript.
Sử dụng moviepy cho chuyển cảnh hoặc FFmpeg concat cho cắt nhanh.
"""
from __future__ import annotations

import os

from src.core.config import OutputConfig
from src.core.errors import RenderError
from src.core.logging import get_logger, log_duration
from src.core.types import RemixScript

logger = get_logger(__name__)


class VideoAssembler:
    """Nối clips thành video hoàn chỉnh."""

    def __init__(self, config: OutputConfig) -> None:
        self._config = config
        from src.remixer.audio_engine import AudioEngine
        from src.remixer.color_grading import ColorGrader
        self.audio_engine = AudioEngine()
        self.color_grader = ColorGrader()

    @log_duration(msg_template="Video assembly {func_name}")
    def assemble(
        self,
        script: RemixScript,
        clip_paths: dict[str, str], # id or filename -> path
        output_path: str,
        apply_color_grading: bool = True
    ) -> str:
        """Nối video dựa trên script với hiệu ứng chuyên nghiệp."""
        logger.info(f"Assembling video v2.0: {script.title}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            from moviepy import VideoFileClip, concatenate_videoclips
            from moviepy.video.fx import MultiplySpeed, Resize, MirrorX, LumContrast, CrossFadeIn
        except ImportError:
            raise RenderError("moviepy components not found.")

        clips = []
        try:
            for i, step in enumerate(script.sequence):
                path = clip_paths.get(step.segment) if step.segment else clip_paths.get(str(step.clip_id))
                if not path or not os.path.exists(path):
                    continue
                
                v_clip = VideoFileClip(path)
                
                # 1. Temporal Jitter (Subclip)
                if step.start_time is not None and step.end_time is not None:
                    # Đảm bảo không vượt quá thời lượng video
                    start = min(step.start_time, v_clip.duration - 0.5)
                    end = min(step.end_time, v_clip.duration)
                    if end > start:
                        v_clip = v_clip.subclipped(start, end)

                # 2. Speed factor
                if step.speed_factor != 1.0:
                    v_clip = v_clip.with_effects([MultiplySpeed(factor=step.speed_factor)])
                
                # 3. UNICITY UPGRADE: Visual Randomization
                # Zoom/Crop
                if step.zoom_factor != 1.0:
                    v_clip = v_clip.resized(step.zoom_factor)
                
                # Mirror
                if step.mirror:
                    v_clip = v_clip.with_effects([MirrorX()])
                
                # Brightness/Contrast
                if step.brightness_factor != 1.0 or step.contrast_factor != 1.0:
                    # Mapping our factors to moviepy params (approximate)
                    lum = (step.brightness_factor - 1.0) * 100
                    con = (step.contrast_factor - 1.0) * 100
                    v_clip = v_clip.with_effects([LumContrast(lum=lum, contrast=con)])

                # 4. Voiceover Audio Integration
                if getattr(step, 'audio_path', None) and os.path.exists(step.audio_path):
                    from moviepy.audio.io.AudioFileClip import AudioFileClip
                    from moviepy.audio.AudioClip import CompositeAudioClip
                    try:
                        voice_clip = AudioFileClip(step.audio_path)
                        # Đảm bảo voice_clip không dài hơn video clip
                        if voice_clip.duration > v_clip.duration:
                            voice_clip = voice_clip.subclipped(0, v_clip.duration)
                            
                        if v_clip.audio:
                            # Mix âm thanh: Giảm âm lượng gốc (0.3), lồng tiếng (1.0)
                            v_audio = v_clip.audio.with_volume_scaled(0.3)
                            final_audio = CompositeAudioClip([v_audio, voice_clip.with_start(0)])
                            v_clip = v_clip.with_audio(final_audio)
                        else:
                            v_clip = v_clip.with_audio(voice_clip)
                    except Exception as e:
                        logger.warning(f"Could not attach audio to clip: {e}")

                # 5. Transitions (Crossfade)
                if i > 0 and step.transition_duration > 0:
                    v_clip = v_clip.with_effects([CrossFadeIn(duration=step.transition_duration)])
                    
                clips.append(v_clip)

            if not clips:
                raise RenderError("No valid clips found.")

            # 3. Assemble
            final_video = concatenate_videoclips(clips, method="compose")
            
            # 4. Final Render
            temp_output = output_path + ".tmp.mp4"
            final_video.write_videofile(
                temp_output,
                codec=self._config.codec,
                audio_codec=self._config.audio_codec,
                fps=self._config.fps,
                logger=None
            )
            
            # 5. Color Grading (Post-process)
            if apply_color_grading:
                output_path = self.color_grader.apply_lut(temp_output, output_path)
            else:
                import shutil
                shutil.move(temp_output, output_path)

            # Cleanup
            final_video.close()
            for c in clips:
                c.close()
                
            return output_path

        except Exception as e:
            raise RenderError(f"Assembly failed: {e}") from e
