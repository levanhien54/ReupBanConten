from __future__ import annotations

from src.remixer.voiceover_engine import EDGE_TTS_VOICES


def test_edge_tts_voice_map_supports_country_language_choices():
    assert EDGE_TTS_VOICES["en-US"].startswith("en-US-")
    assert EDGE_TTS_VOICES["en-GB"].startswith("en-GB-")
    assert EDGE_TTS_VOICES["fr-FR"].startswith("fr-FR-")
    assert EDGE_TTS_VOICES["de-DE"].startswith("de-DE-")
    assert EDGE_TTS_VOICES["ja-JP"].startswith("ja-JP-")
    assert EDGE_TTS_VOICES["ko-KR"].startswith("ko-KR-")
    assert EDGE_TTS_VOICES["pt-BR"].startswith("pt-BR-")
