from __future__ import annotations

from src.core.config import SubtitleConfig
from src.core.types import CommentaryScript, CommentarySegment
from src.remixer.ass_generator import ASSGenerator


def test_ass_generator_applies_position_effect_and_keyword_highlight(tmp_path):
    config = SubtitleConfig(
        font="Arial",
        font_size=54,
        preset_style="capcut_yellow",
        position="center",
        effect="impact_pop",
        word_highlight=True,
        max_chars_per_line=18,
    )
    script = CommentaryScript(
        segments=[
            CommentarySegment(
                text="Cú đòn này tạo áp lực ngay lập tức",
                start_time=0.2,
                duration_estimate=1.5,
                style="impact",
                keywords=["đòn", "áp lực"],
            )
        ]
    )
    output = tmp_path / "caption.ass"

    ASSGenerator(config).generate(script, str(output), width=1080, height=1920)

    content = output.read_text(encoding="utf-8")
    assert "Style: PremiumStyle,Arial,54" in content
    assert ",5,80,80,70,1" in content
    assert r"\fscx112" in content
    assert r"{\c&H0000FF&}đòn{\c}" in content
