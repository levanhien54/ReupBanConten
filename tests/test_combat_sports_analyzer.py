from __future__ import annotations

from src.analyzer.combat_sports import CombatSportsAnalyzer
from src.core.config import CombatSportsHighlightConfig
from src.core.types import CombatSignal, TranscriptResult, TranscriptSegment


def _config(threshold: float = 0.72) -> CombatSportsHighlightConfig:
    return CombatSportsHighlightConfig(min_highlight_score=threshold)


def test_transcript_keywords_rank_impact_hook():
    analyzer = CombatSportsAnalyzer(_config())
    transcript = TranscriptResult(
        full_text="",
        segments=[
            TranscriptSegment(start=0.0, end=2.0, text="Both fighters are waiting."),
            TranscriptSegment(start=4.0, end=6.0, text="Huge left hook, he is knocked down!"),
        ],
    )

    highlights = analyzer.analyze(transcript=transcript)

    assert len(highlights) == 1
    highlight = highlights[0]
    assert highlight.score >= 0.72
    assert highlight.hook_time == 5.0
    assert highlight.start_time == 4.2
    assert any("impact" in reason for reason in highlight.reasons)


def test_vietnamese_keywords_are_normalized():
    analyzer = CombatSportsAnalyzer(_config())
    transcript = TranscriptResult(
        full_text="",
        segments=[
            TranscriptSegment(start=10.0, end=12.0, text="Cú đấm trúng rất nặng, đối thủ gục xuống!"),
        ],
    )

    signals = analyzer.score_transcript(transcript)

    assert len(signals) == 1
    assert signals[0].kind == "impact"
    assert signals[0].score >= 0.9


def test_nearby_signals_merge_with_diversity_bonus():
    analyzer = CombatSportsAnalyzer(_config(threshold=0.0))
    signals = [
        CombatSignal(time=5.0, score=0.9, kind="impact", reason="keyword:knockdown"),
        CombatSignal(time=5.7, score=0.8, kind="motion", reason="motion_burst"),
        CombatSignal(time=6.1, score=0.85, kind="crowd_audio", reason="audio_spike"),
    ]

    highlights = analyzer.rank_signals(signals)

    assert len(highlights) == 1
    assert highlights[0].score >= 0.85
    assert highlights[0].start_time == 4.2
    assert highlights[0].end_time >= 7.3
    assert len(highlights[0].signals) == 3


def test_api_results_are_ranked_as_semantic_signals():
    analyzer = CombatSportsAnalyzer(_config())

    highlights = analyzer.analyze(
        api_results=[
            {
                "start": 12.0,
                "end": 15.0,
                "confidence": 0.91,
                "reason": "clean knockdown and crowd reaction",
            }
        ]
    )

    assert len(highlights) == 1
    assert highlights[0].score >= 0.72
    assert highlights[0].hook_time == 13.5
    assert any(signal.kind == "api_semantic" for signal in highlights[0].signals)
    assert any("api_semantic" in reason for reason in highlights[0].reasons)


def test_low_score_signals_are_filtered():
    analyzer = CombatSportsAnalyzer(_config(threshold=0.72))
    signals = [
        CombatSignal(time=3.0, score=0.3, kind="motion", reason="small_motion"),
    ]

    highlights = analyzer.rank_signals(signals)

    assert highlights == []
