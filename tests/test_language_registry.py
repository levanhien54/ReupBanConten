from __future__ import annotations

from src.remixer.language_registry import (
    canonical_language_code,
    edge_tts_voice,
    language_code_from_label,
    language_label,
    language_prompt_name,
    supported_language_labels,
)


def test_language_registry_exposes_requested_country_choices():
    assert supported_language_labels() == [
        "Viet Nam",
        "Hoa Ky (My)",
        "Vuong quoc Anh (Anh)",
        "Phap",
        "Duc",
        "Nhat Ban",
        "Han Quoc",
        "Brazil",
    ]


def test_language_registry_maps_ui_labels_to_codes():
    assert language_code_from_label("Hoa Ky (My)") == "en-US"
    assert language_code_from_label("Vuong quoc Anh (Anh)") == "en-GB"
    assert language_code_from_label("Brazil") == "pt-BR"
    assert language_label("pt") == "Brazil"


def test_language_registry_keeps_legacy_aliases():
    assert canonical_language_code("en") == "en-US"
    assert canonical_language_code("ja") == "ja-JP"
    assert language_prompt_name("en") == "American English"
    assert edge_tts_voice("ko").startswith("ko-KR-")
