from src.core.config import MemeEffectsConfig, VoiceoverConfig, SubtitleConfig
from src.core.logging import get_logger, log_duration
from src.core.types import CommentaryScript
from src.remixer.ass_generator import ASSGenerator
import os
import subprocess
from typing import Any, Optional, List, Dict

logger = get_logger(__name__)


class SubtitleRenderer:
    """Tạo phụ đề cao cấp (CapCut style) cho video."""

    def __init__(self, config: SubtitleConfig) -> None:
        self._config = config
        self._ass_gen = ASSGenerator(config)

    @log_duration(msg_template="Subtitle rendering {func_name}")
    def apply_subtitles(
        self,
        video_path: str,
        script: CommentaryScript,
        output_path: str,
    ) -> str:
        """Thêm phụ đề được thiết kế cao cấp vào video."""
        if not self._config.enabled or not script.segments:
            return video_path

        # Ưu tiên dùng FFmpeg + ASS vì chất lượng cao hơn và hiệu ứng mượt hơn
        try:
            return self.render_ass_with_ffmpeg(video_path, script, output_path)
        except Exception as e:
            logger.warning(f"FFmpeg ASS rendering failed, falling back to MoviePy: {e}")
            return self.render_with_moviepy(video_path, script, output_path)

    def render_ass_with_ffmpeg(self, video_path: str, script: CommentaryScript, output_path: str) -> str:
        """Render phụ đề dùng định dạng ASS và FFmpeg (Chuẩn chuyên nghiệp)."""
        temp_ass = video_path + ".ass"
        
        # 1. Sinh file .ass
        self._ass_gen.generate(script, temp_ass)
        
        # 2. Chạy FFmpeg để "burn" sub vào video
        # Lưu ý: Cần escape đường dẫn cho filter subtitles của FFmpeg
        escaped_ass = temp_ass.replace("\\", "/").replace(":", "\\:")
        
        cmd = [
            "ffmpeg.exe", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{escaped_ass}'",
            "-c:a", "copy", # Giữ nguyên audio
            output_path
        ]
        
        logger.info(f"Running FFmpeg ASS burn: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg error: {result.stderr}")
            
        # Dọn dẹp
        if os.path.exists(temp_ass):
            os.remove(temp_ass)
            
        return output_path

    def render_with_moviepy(self, video_path: str, script: CommentaryScript, output_path: str) -> str:
        """Bộ render dự phòng dùng MoviePy."""
        try:
            from moviepy import VideoFileClip, CompositeVideoClip
            video = VideoFileClip(video_path)
            subtitle_clips = []

            all_segments = []
            if script.intro: all_segments.append(script.intro)
            all_segments.extend(script.segments)
            if script.outro: all_segments.append(script.outro)

            for seg in all_segments:
                if not seg.text: continue
                txt_clip = self._create_styled_text(seg.text, video.w)
                txt_clip = txt_clip.with_start(seg.start_time)
                duration = seg.duration_estimate if seg.duration_estimate > 0 else 3.0
                txt_clip = txt_clip.with_duration(duration)
                txt_clip = txt_clip.with_position(self._get_position(video.h))
                subtitle_clips.append(txt_clip)

            if not subtitle_clips: return video_path

            final_video = CompositeVideoClip([video] + subtitle_clips)
            final_video.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=30, logger=None)
            final_video.close()
            video.close()
            return output_path
        except Exception as e:
            logger.error(f"MoviePy fallback failed: {e}")
            return video_path


    def _create_styled_text(self, text: str, video_w: int) -> Any:
        """Tạo TextClip dựa trên preset_style."""
        from moviepy import TextClip
        
        # Cấu hình mặc định từ config
        font = self._config.font
        size = self._config.font_size
        color = self._config.color
        stroke_color = self._config.outline_color
        stroke_width = self._config.outline_width
        
        # Override theo preset
        if self._config.preset_style == "capcut_yellow":
            color = "yellow"
            stroke_color = "black"
            stroke_width = 3
        elif self._config.preset_style == "modern_white":
            color = "white"
            stroke_color = "#333333"
            stroke_width = 2
        elif self._config.preset_style == "glow_pink":
            color = "#FF00FF"
            stroke_color = "white"
            stroke_width = 4

        return TextClip(
            text=text,
            font=font,
            font_size=size,
            color=color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            method='caption', # Tự động xuống dòng
            size=(video_w * 0.8, None), # Chiếm 80% chiều rộng
            text_align='center'
        )

    def _get_position(self, video_h: int) -> tuple:
        """Tính toán vị trí hiển thị."""
        if self._config.position == "bottom":
            return ("center", video_h * 0.8)
        elif self._config.position == "top":
            return ("center", video_h * 0.2)
        return ("center", "center")


class EffectsManager:
    """Quản lý và áp dụng Meme và Voiceover."""

    def __init__(self, config: MemeEffectsConfig) -> None:
        self._config = config

    @log_duration(msg_template="Meme application {func_name}")
    def apply_memes(
        self,
        video_path: str,
        placements: list[dict],
        output_path: str,
    ) -> str:
        """Áp dụng memes (sound/image) vào video."""
        if not self._config.enabled or not placements:
            return video_path
            
        logger.info(f"Applying {len(placements)} memes to {os.path.basename(video_path)}")
        
        try:
            from moviepy import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, CompositeAudioClip
            from moviepy import vfx
        except ImportError:
            logger.warning("moviepy not installed. Skipping meme effects.")
            return video_path

        try:
            video = VideoFileClip(video_path)
            
            sound_placements = [p for p in placements if p.get('sound_path')]
            image_placements = [p for p in placements if p.get('image_path')]
            
            # 1. Add sounds
            if sound_placements:
                audio_clips = [video.audio] if video.audio else []
                for p in sound_placements:
                    if not os.path.exists(p['sound_path']):
                        continue
                    sfx = AudioFileClip(p['sound_path'])
                    vol = p.get('volume', self._config.sounds.default_volume)
                    sfx = sfx.with_volume_scaled(vol)
                    sfx = sfx.with_start(p['time'])
                    
                    remaining = video.duration - p['time']
                    if sfx.duration > remaining:
                        sfx = sfx.subclipped(0, remaining)
                    
                    audio_clips.append(sfx)
                    
                if len(audio_clips) > 1:
                    mixed_audio = CompositeAudioClip(audio_clips)
                    video = video.with_audio(mixed_audio)

            # 2. Add images
            if image_placements:
                overlay_clips = [video]
                for p in image_placements:
                    if not os.path.exists(p['image_path']):
                        continue
                    img = ImageClip(p['image_path'])
                    
                    size_ratio = p.get('size_ratio', self._config.images.default_size_ratio)
                    new_width = int(video.w * size_ratio)
                    img = img.resized(width=new_width)
                    
                    duration = p.get('duration', self._config.images.default_duration)
                    img = img.with_duration(duration)
                    img = img.with_start(p['time'])
                    
                    # Position simple mapping
                    pos_str = p.get('position', self._config.images.default_position)
                    pos_map = {
                        "top_left": (0.05, 0.05),
                        "top_right": (0.75, 0.05),
                        "bottom_left": (0.05, 0.75),
                        "bottom_right": (0.75, 0.75),
                        "center": ("center", "center"),
                        "top_center": ("center", 0.05),
                        "bottom_center": ("center", 0.75)
                    }
                    pos = pos_map.get(pos_str, (0.1, 0.1))
                        
                    img = img.with_position(pos, relative=True)
                    
                    # Fades
                    img = img.with_effects([
                        vfx.FadeIn(self._config.images.fade_in),
                        vfx.FadeOut(self._config.images.fade_out),
                    ])
                    
                    overlay_clips.append(img)
                    
                if len(overlay_clips) > 1:
                    video = CompositeVideoClip(overlay_clips)

            # Render
            video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=30,
                logger=None
            )
            video.close()
            return output_path

        except Exception as e:
            logger.error(f"Failed to apply memes: {e}")
            return video_path

class VoiceoverMixer:
    """Trộn giọng nói AI vào video với hiệu ứng giảm âm nền (ducking)."""

    def __init__(self, config: VoiceoverConfig) -> None:
        self._config = config

    @log_duration(msg_template="Voiceover mixing {func_name}")
    def mix_voiceover(
        self,
        video_path: str,
        script: CommentaryScript,
        output_path: str,
    ) -> str:
        """Trộn kịch bản bình luận vào video."""
        if not self._config.enabled or not script.segments:
            return video_path

        logger.info(f"Mixing voiceover into {os.path.basename(video_path)}")

        try:
            from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
        except ImportError:
            logger.warning("moviepy not installed. Skipping voiceover mixing.")
            return video_path

        try:
            video = VideoFileClip(video_path)
            orig_audio = video.audio
            
            # Thu thập tất cả các đoạn âm thanh
            voice_clips = []
            
            # 1. Intro
            if script.intro and script.intro.audio_path and os.path.exists(script.intro.audio_path):
                vo = AudioFileClip(script.intro.audio_path)
                vo = vo.with_start(script.intro.start_time)
                voice_clips.append(vo)
                
            # 2. Segments
            for seg in script.segments:
                if seg.audio_path and os.path.exists(seg.audio_path):
                    vo = AudioFileClip(seg.audio_path)
                    
                    # Tự động tăng tốc nếu voiceover dài hơn thời lượng clip (với buffer 0.2s)
                    target_dur = seg.duration_estimate if seg.duration_estimate > 0 else 5.0
                    if vo.duration > (target_dur + 0.2):
                        speed_factor = vo.duration / target_dur
                        logger.info(f"Speeding up voiceover by {speed_factor:.2f}x to fit {target_dur}s")
                        # Sử dụng time_transform cho đơn giản hoặc vfx.speedx
                        from moviepy.video.fx import MultiplySpeed
                        vo = vo.with_effects([MultiplySpeed(speed_factor)])
                    
                    vo = vo.with_start(seg.start_time)
                    voice_clips.append(vo)
                    
            # 3. Outro
            if script.outro and script.outro.audio_path and os.path.exists(script.outro.audio_path):
                vo = AudioFileClip(script.outro.audio_path)
                vo = vo.with_start(script.outro.start_time)
                voice_clips.append(vo)

            if not voice_clips:
                return video_path

            # Hỗ trợ Ducking (Giảm âm nền)
            if orig_audio:
                ducked_orig = orig_audio.with_volume_scaled(self._config.mixing.original_volume_during_vo)
                final_voice = [v.with_volume_scaled(self._config.mixing.voiceover_volume) for v in voice_clips]
                mixed_audio = CompositeAudioClip([ducked_orig] + final_voice)
                video = video.with_audio(mixed_audio)

            # Render
            video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=30,
                logger=None
            )
            video.close()
            for v in voice_clips:
                v.close()
            
            return output_path

        except Exception as e:
            logger.error(f"Failed to mix voiceover: {e}")
            return video_path
