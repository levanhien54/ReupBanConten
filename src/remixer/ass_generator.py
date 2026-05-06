"""ASS subtitle generator with short-form caption effects."""
from __future__ import annotations

import os
import re
import textwrap

from src.core.config import SubtitleConfig
from src.core.types import CommentaryScript, CommentarySegment


STYLE_COLORS = {
    "capcut_yellow": ("&H0000FFFF", "&H00000000"),
    "modern_white": ("&H00FFFFFF", "&H00222222"),
    "glow_pink": ("&H00FF00FF", "&H00FFFFFF"),
    "elegant_gold": ("&H0000D7FF", "&H00141414"),
    "neon_cyber": ("&H00FFFF00", "&H00FF00AA"),
}

POSITION_ALIGNMENT = {
    "bottom": 2,
    "center": 5,
    "top": 8,
}


class ASSGenerator:
    """Generate styled .ass subtitles for FFmpeg burn-in."""

    def __init__(self, config: SubtitleConfig) -> None:
        self._config = config

    def generate(
        self,
        script: CommentaryScript,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
    ) -> str:
        header = self._get_header(width, height)
        styles = self._get_styles()
        events = [
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        for seg in _iter_segments(script):
            if not seg.text:
                continue
            start_str = self._format_time(seg.start_time)
            duration = seg.duration_estimate if seg.duration_estimate > 0 else 3.0
            end_str = self._format_time(seg.start_time + duration)
            clean_text = self._format_segment_text(seg)
            events.append(
                f"Dialogue: 0,{start_str},{end_str},PremiumStyle,,0,0,0,,{clean_text}"
            )

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header + "\n" + styles + "\n" + "\n".join(events))
        return output_path

    def _get_header(self, width: int, height: int) -> str:
        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
"""

    def _get_styles(self) -> str:
        primary, outline = STYLE_COLORS.get(
            self._config.preset_style,
            STYLE_COLORS["capcut_yellow"],
        )
        alignment = POSITION_ALIGNMENT.get(self._config.position, 2)
        margin_v = 110 if self._config.position == "bottom" else 70
        shadow = "&H64000000"
        return f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PremiumStyle,{self._config.font},{self._config.font_size},{primary},&H000000FF,{outline},{shadow},1,0,0,0,100,100,0,0,1,{self._config.outline_width},2,{alignment},80,80,{margin_v},1
"""

    def _format_segment_text(self, seg: CommentarySegment) -> str:
        text = _wrap_subtitle_text(seg.text, width=self._config.max_chars_per_line)
        text = _escape_ass(text)
        if self._config.word_highlight and seg.keywords:
            text = _highlight_keywords(text, seg.keywords)

        effect = self._config.effect
        if effect == "impact_pop" and seg.style == "impact":
            return r"{\fad(50,70)\t(0,160,\fscx112\fscy112)}" + text
        if effect == "replay_fade" or seg.style == "replay":
            return r"{\fad(140,180)}" + text
        if effect == "none":
            return text
        return r"{\fad(90,120)}" + text

    def _format_time(self, seconds: float) -> str:
        seconds = max(0.0, seconds)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds * 100) % 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _iter_segments(script: CommentaryScript) -> list[CommentarySegment]:
    segments = []
    if script.intro:
        segments.append(script.intro)
    segments.extend(script.segments)
    if script.outro:
        segments.append(script.outro)
    return segments


def _wrap_subtitle_text(text: str, width: int = 24) -> str:
    lines = textwrap.wrap(
        text.strip(),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if len(lines) <= 2:
        return "\\N".join(lines)
    return "\\N".join([lines[0], " ".join(lines[1:])])


def _escape_ass(text: str) -> str:
    return text.replace("{", "").replace("}", "").replace("\n", "\\N")


def _highlight_keywords(text: str, keywords: list[str]) -> str:
    for keyword in sorted(set(keywords), key=len, reverse=True):
        if not keyword:
            continue
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(lambda m: r"{\c&H0000FF&}" + m.group(0) + r"{\c}", text)
    return text
