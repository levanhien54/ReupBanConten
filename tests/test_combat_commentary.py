from __future__ import annotations

import pytest

from src.core.types import CombatHighlight, CombatSignal, TranscriptResult, TranscriptSegment
from src.remixer.combat_commentary import (
    CombatCommentaryGenerator,
    build_timeline_evidence,
    build_evidence_packet,
    unsupported_claims,
)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def is_available(self):
        return True

    async def generate_json(self, prompt, **kwargs):
        return self.payload


def _highlight() -> CombatHighlight:
    return CombatHighlight(
        start_time=4.2,
        hook_time=5.0,
        end_time=7.2,
        score=0.88,
        reasons=["impact:keyword:big shot"],
        signals=[
            CombatSignal(time=5.0, score=0.9, kind="impact", reason="keyword:big shot"),
            CombatSignal(time=5.2, score=0.8, kind="motion", reason="motion_burst"),
        ],
    )


@pytest.mark.asyncio
async def test_combat_commentary_rejects_unsupported_knockout_claim():
    generator = CombatCommentaryGenerator(
        FakeLLM(
            {
                "segments": [
                    {
                        "start_time": 0.0,
                        "duration_estimate": 1.4,
                        "text": "Pha này là knockout cực nặng ngay lập tức",
                        "emotion": "excited",
                        "evidence_used": ["impact"],
                        "certainty": "high",
                        "style": "impact",
                    }
                ]
            }
        )
    )
    script = await generator.generate_script([_highlight()])

    assert len(script.segments) == 1
    assert "knockout" not in script.segments[0].text.lower()
    assert script.segments[0].evidence_used == ["impact", "motion"]


@pytest.mark.asyncio
async def test_combat_commentary_fallback_uses_selected_language():
    generator = CombatCommentaryGenerator()

    script = await generator.generate_script([_highlight()], language="en")

    assert len(script.segments) == 1
    assert "strike" in script.segments[0].text.lower()
    assert "áp lực" not in script.segments[0].text.lower()


def test_unsupported_claims_allow_supported_knockdown_transcript():
    transcript = TranscriptResult(
        full_text="",
        segments=[
            TranscriptSegment(start=4.5, end=5.6, text="Huge right hand, down goes the fighter"),
        ],
    )
    packet = build_evidence_packet(_highlight(), transcript=transcript)

    assert unsupported_claims("Đối thủ ngã xuống sau cú đòn rất nặng", packet) == []


def test_timeline_evidence_maps_signals_and_words_relative_to_clip():
    transcript = TranscriptResult(
        full_text="",
        segments=[
            TranscriptSegment(start=4.6, end=5.4, text="Big shot lands"),
        ],
        word_timestamps=[
            {"word": "Big", "start": 4.6, "end": 4.8, "probability": 0.9},
            {"word": "shot", "start": 4.82, "end": 5.0, "probability": 0.9},
        ],
    )

    timeline = build_timeline_evidence(_highlight(), transcript=transcript)

    assert timeline[0]["type"] == "transcript_segment"
    assert any(item["type"] == "impact" and item["time"] == 0.8 for item in timeline)
    assert any(item["type"] == "word" and item["text"] == "shot" for item in timeline)
