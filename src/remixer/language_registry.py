"""Shared language choices for commentary, subtitles, and voiceover."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageChoice:
    code: str
    ui_label: str
    prompt_name: str
    edge_tts_voice: str


LANGUAGE_CHOICES: tuple[LanguageChoice, ...] = (
    LanguageChoice("vi", "Viet Nam", "Vietnamese", "vi-VN-HoaiMyNeural"),
    LanguageChoice("en-US", "Hoa Ky (My)", "American English", "en-US-EmmaNeural"),
    LanguageChoice("en-GB", "Vuong quoc Anh (Anh)", "British English", "en-GB-SoniaNeural"),
    LanguageChoice("fr-FR", "Phap", "French", "fr-FR-DeniseNeural"),
    LanguageChoice("de-DE", "Duc", "German", "de-DE-KatjaNeural"),
    LanguageChoice("ja-JP", "Nhat Ban", "Japanese", "ja-JP-NanamiNeural"),
    LanguageChoice("ko-KR", "Han Quoc", "Korean", "ko-KR-SunHiNeural"),
    LanguageChoice("pt-BR", "Brazil", "Brazilian Portuguese", "pt-BR-FranciscaNeural"),
)

LANGUAGE_ALIASES = {
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "pt": "pt-BR",
    "zh": "zh-CN",
    "es": "es-ES",
}

EXTRA_EDGE_TTS_VOICES = {
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "es-ES": "es-ES-ElviraNeural",
}

_LANGUAGE_BY_CODE = {choice.code: choice for choice in LANGUAGE_CHOICES}
_LANGUAGE_BY_LABEL = {choice.ui_label: choice for choice in LANGUAGE_CHOICES}


def supported_language_labels() -> list[str]:
    return [choice.ui_label for choice in LANGUAGE_CHOICES]


def canonical_language_code(code: str) -> str:
    if not code:
        return "vi"
    return LANGUAGE_ALIASES.get(code, code)


def language_label(code: str) -> str:
    choice = _LANGUAGE_BY_CODE.get(canonical_language_code(code))
    return choice.ui_label if choice else _LANGUAGE_BY_CODE["vi"].ui_label


def language_code_from_label(label: str) -> str:
    choice = _LANGUAGE_BY_LABEL.get(label)
    return choice.code if choice else "vi"


def language_prompt_name(code: str) -> str:
    canonical = canonical_language_code(code)
    choice = _LANGUAGE_BY_CODE.get(canonical)
    if choice:
        return choice.prompt_name
    if canonical == "zh-CN":
        return "Chinese"
    if canonical == "es-ES":
        return "Spanish"
    return canonical or "Vietnamese"


def edge_tts_voice(code: str) -> str:
    return EDGE_TTS_VOICES.get(canonical_language_code(code), EDGE_TTS_VOICES["vi"])


EDGE_TTS_VOICES = {
    **{choice.code: choice.edge_tts_voice for choice in LANGUAGE_CHOICES},
    **{alias: _LANGUAGE_BY_CODE[canonical].edge_tts_voice for alias, canonical in LANGUAGE_ALIASES.items() if canonical in _LANGUAGE_BY_CODE},
    **EXTRA_EDGE_TTS_VOICES,
    "zh": EXTRA_EDGE_TTS_VOICES["zh-CN"],
    "es": EXTRA_EDGE_TTS_VOICES["es-ES"],
}
