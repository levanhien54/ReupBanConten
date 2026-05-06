"""
ASS Subtitle Generator — Tạo file phụ đề .ass chuyên nghiệp.
Hỗ trợ các hiệu ứng CapCut style thông qua định dạng Advanced Substation Alpha.
"""
import os
from typing import Optional
from src.core.types import CommentaryScript, CommentarySegment
from src.core.config import SubtitleConfig

class ASSGenerator:
    """Tạo file phụ đề .ass với style cao cấp."""

    def __init__(self, config: SubtitleConfig) -> None:
        self._config = config

    def generate(self, script: CommentaryScript, output_path: str, width: int = 1920, height: int = 1080) -> str:
        """Sinh file .ass từ kịch bản bình luận."""
        
        # 1. Header & Styles
        header = self._get_header(width, height)
        styles = self._get_styles()
        
        # 2. Events (Dialogues)
        events = ["[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        
        all_segments = []
        if script.intro: all_segments.append(script.intro)
        all_segments.extend(script.segments)
        if script.outro: all_segments.append(script.outro)
        
        for seg in all_segments:
            if not seg.text:
                continue
            
            start_str = self._format_time(seg.start_time)
            end_time = seg.start_time + (seg.duration_estimate if seg.duration_estimate > 0 else 3.0)
            end_str = self._format_time(end_time)
            
            # Escape special characters in text
            clean_text = seg.text.replace("\n", "\\N")
            
            # Thêm hiệu ứng karaoke đơn giản nếu được bật
            if self._config.word_highlight:
                # {\\k50} là hiệu ứng karaoke 0.5s cho mỗi từ (giả định)
                # Đây là bản đơn giản, thực tế cần đồng bộ từ (word-level timestamps)
                pass

            line = f"Dialogue: 0,{start_str},{end_str},PremiumStyle,,0,0,0,,{clean_text}"
            events.append(line)
            
        content = header + "\n" + styles + "\n" + "\n".join(events)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return output_path

    def _get_header(self, w, h) -> str:
        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes
"""

    def _get_styles(self) -> str:
        # Chuyển đổi màu từ config sang format ASS (&HAA GGRRBB)
        # Mặc định: Vàng viền đen bóng mờ
        primary = "&H0000FFFF" # Yellow
        outline = "&H00000000" # Black
        shadow = "&H64000000"  # Semi-transparent black
        
        if self._config.preset_style == "modern_white":
            primary = "&H00FFFFFF"
        elif self._config.preset_style == "glow_pink":
            primary = "&H00FF00FF"
            outline = "&H00FFFFFF"

        return f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PremiumStyle,{self._config.font},{self._config.font_size},{primary},&H000000FF,{outline},{shadow},1,0,0,0,100,100,0,0,1,{self._config.outline_width},2,2,10,10,60,1
"""

    def _format_time(self, seconds: float) -> str:
        """Chuyển đổi giây sang format ASS H:MM:SS.cs"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds * 100) % 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
