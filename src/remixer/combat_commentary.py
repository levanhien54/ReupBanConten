"""Fact-constrained combat-sports commentary generation."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from src.core.logging import get_logger
from src.core.types import CombatHighlight, CommentaryScript, CommentarySegment, TranscriptResult
from src.llm.provider import LLMProvider

logger = get_logger(__name__)


UNSUPPORTED_CLAIMS: dict[str, tuple[str, ...]] = {
    "knockout": ("knockout", "knock-out", "ko", "hạ knock-out", "hạ knockout"),
    "knockdown": ("knockdown", "knocked down", "down goes", "gục", "ngã xuống"),
    "submission": ("submission", "tap", "tapout", "choke", "armbar", "siết", "khóa", "xin thua"),
    "stoppage": ("referee stops", "stop the fight", "trọng tài dừng", "dừng trận"),
    "round": ("round", "hiệp"),
    "championship": ("champion", "title fight", "đai", "vô địch"),
}

SAFE_LINES = {
    "vi": {
        "impact": "Cú ra đòn này tạo áp lực ngay lập tức.",
        "submission": "Pha khóa siết này buộc đối thủ phải cảnh giác.",
        "scramble": "Tình huống áp sát khiến nhịp trận đổi chiều.",
        "motion": "Tốc độ pha này tăng lên rất nhanh.",
        "crowd_audio": "Khán giả phản ứng mạnh với khoảnh khắc này.",
        "api_semantic": "Đây là điểm nhấn đáng chú ý của pha đấu.",
        "default": "Khoảnh khắc này có thể đổi chiều trận đấu.",
    },
    "en": {
        "impact": "That strike changes the pressure immediately.",
        "submission": "That submission threat forces a quick reaction.",
        "scramble": "This scramble can swing the whole exchange.",
        "motion": "The pace jumps fast in this moment.",
        "crowd_audio": "The crowd reacts hard to this sequence.",
        "api_semantic": "This is the key moment to watch.",
        "default": "This moment can shift the fight quickly.",
    },
    "en-US": {
        "impact": "That strike changes the pressure immediately.",
        "submission": "That submission threat forces a quick reaction.",
        "scramble": "This scramble can swing the whole exchange.",
        "motion": "The pace jumps fast in this moment.",
        "crowd_audio": "The crowd reacts hard to this sequence.",
        "api_semantic": "This is the key moment to watch.",
        "default": "This moment can shift the fight quickly.",
    },
    "en-GB": {
        "impact": "That strike shifts the pressure straight away.",
        "submission": "That submission threat forces an immediate response.",
        "scramble": "This scramble can turn the whole exchange.",
        "motion": "The pace rises sharply in this moment.",
        "crowd_audio": "The crowd reacts strongly to this sequence.",
        "api_semantic": "This is the key moment to watch.",
        "default": "This moment can change the fight quickly.",
    },
    "fr-FR": {
        "impact": "Cette frappe met la pression immediatement.",
        "submission": "Cette menace de soumission force une reaction rapide.",
        "scramble": "Cette lutte au contact peut inverser l'echange.",
        "motion": "Le rythme monte tres vite sur cette action.",
        "crowd_audio": "Le public reagit fort a cette sequence.",
        "api_semantic": "C'est le moment cle a regarder.",
        "default": "Ce moment peut changer le combat rapidement.",
    },
    "de-DE": {
        "impact": "Dieser Treffer erhoeht sofort den Druck.",
        "submission": "Diese Submission-Gefahr erzwingt eine schnelle Reaktion.",
        "scramble": "Dieses Gerangel kann den Austausch kippen.",
        "motion": "Das Tempo steigt in diesem Moment stark an.",
        "crowd_audio": "Das Publikum reagiert stark auf diese Sequenz.",
        "api_semantic": "Das ist der entscheidende Moment.",
        "default": "Dieser Moment kann den Kampf schnell drehen.",
    },
    "ja-JP": {
        "impact": "この一撃で一気に流れが変わります。",
        "submission": "このサブミッションの圧力で即座の対応が必要です。",
        "scramble": "この攻防で展開が大きく動きます。",
        "motion": "ここで一気にテンポが上がります。",
        "crowd_audio": "観客がこの場面に大きく反応しています。",
        "api_semantic": "ここが注目すべきポイントです。",
        "default": "この瞬間が試合の流れを変えます。",
    },
    "ko-KR": {
        "impact": "이 타격이 곧바로 압박을 만듭니다.",
        "submission": "이 서브미션 위협은 빠른 대응을 강요합니다.",
        "scramble": "이 공방이 흐름을 크게 바꿀 수 있습니다.",
        "motion": "이 순간 속도가 빠르게 올라갑니다.",
        "crowd_audio": "관중이 이 장면에 강하게 반응합니다.",
        "api_semantic": "지금이 꼭 봐야 할 핵심 순간입니다.",
        "default": "이 순간이 경기 흐름을 빠르게 바꿉니다.",
    },
    "pt-BR": {
        "impact": "Esse golpe muda a pressao imediatamente.",
        "submission": "Essa ameaca de finalizacao exige resposta rapida.",
        "scramble": "Essa disputa pode virar toda a troca.",
        "motion": "O ritmo sobe muito rapido nesse momento.",
        "crowd_audio": "A torcida reage forte a essa sequencia.",
        "api_semantic": "Esse e o momento chave para observar.",
        "default": "Esse momento pode mudar a luta rapidamente.",
    },
}

IMPACT_KEYWORDS = ("gục", "knockout", "knockdown", "đòn", "strike", "siết", "ngã", "áp lực", "pressure")


@dataclass
class CombatEvidencePacket:
    sport: str
    start_time: float
    hook_time: float
    end_time: float
    confidence: float
    signals: list[str]
    reasons: list[str]
    transcript: str = ""
    visual_labels: list[str] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    known_facts: dict[str, Optional[str]] = field(default_factory=dict)
    language: str = "vi"


class CombatCommentaryGenerator:
    """Generate commentary that only uses supported evidence."""

    def __init__(self, llm: Optional[LLMProvider] = None) -> None:
        self._llm = llm

    async def generate_script(
        self,
        highlights: list[CombatHighlight],
        *,
        transcript: Optional[TranscriptResult] = None,
        sport: str = "combat",
        known_facts: Optional[dict[str, Optional[str]]] = None,
        language: str = "vi",
    ) -> CommentaryScript:
        packets = [
            build_evidence_packet(
                highlight,
                transcript=transcript,
                sport=sport,
                known_facts=known_facts,
                language=language,
            )
            for highlight in highlights
        ]
        segments = []
        for packet in packets:
            segments.append(await self.generate_segment(packet))
        return CommentaryScript(
            segments=segments,
            total_segments=len(segments),
            estimated_total_duration=sum(s.duration_estimate for s in segments),
        )

    async def generate_segment(self, packet: CombatEvidencePacket) -> CommentarySegment:
        if self._llm and self._llm.is_available():
            try:
                candidate = await self._generate_with_llm(packet)
                return validate_or_fallback(candidate, packet)
            except Exception as exc:
                logger.warning(f"Combat commentary LLM fallback: {exc}")
        return fallback_segment(packet)

    async def _generate_with_llm(self, packet: CombatEvidencePacket) -> CommentarySegment:
        data = await self._llm.generate_json(
            build_commentary_prompt(packet),
            temperature=0.2,
            max_tokens=900,
        )
        item = (data.get("segments") or [data])[0]
        text = str(item.get("text", "")).strip()
        return CommentarySegment(
            text=text,
            start_time=float(item.get("start_time", max(0.0, packet.hook_time - packet.start_time - 0.2))),
            duration_estimate=float(item.get("duration_estimate", 1.4)),
            emotion=str(item.get("emotion", "tense")),
            evidence_used=[str(x) for x in item.get("evidence_used", packet.signals)],
            certainty=str(item.get("certainty", _certainty(packet))),
            style=str(item.get("style", _style(packet))),
            keywords=[str(x) for x in item.get("keywords", _keywords(text))],
        )


def build_evidence_packet(
    highlight: CombatHighlight,
    *,
    transcript: Optional[TranscriptResult] = None,
    sport: str = "combat",
    known_facts: Optional[dict[str, Optional[str]]] = None,
    language: str = "vi",
) -> CombatEvidencePacket:
    signals = sorted({signal.kind for signal in highlight.signals})
    visual_labels = [
        signal.reason
        for signal in highlight.signals
        if signal.kind == "api_semantic" and signal.reason
    ]
    return CombatEvidencePacket(
        sport=sport,
        start_time=highlight.start_time,
        hook_time=highlight.hook_time,
        end_time=highlight.end_time,
        confidence=highlight.score,
        signals=signals,
        reasons=highlight.reasons,
        transcript=_transcript_near_highlight(transcript, highlight) if transcript else "",
        visual_labels=visual_labels,
        timeline=build_timeline_evidence(highlight, transcript=transcript),
        known_facts=known_facts or {},
        language=language,
    )


def build_timeline_evidence(
    highlight: CombatHighlight,
    *,
    transcript: Optional[TranscriptResult] = None,
) -> list[dict]:
    events = []
    clip_start = highlight.start_time
    for signal in highlight.signals:
        events.append(
            {
                "type": signal.kind,
                "time": round(signal.time - clip_start, 3),
                "abs_time": signal.time,
                "score": signal.score,
                "reason": signal.reason,
            }
        )

    if transcript:
        for segment in transcript.segments:
            if segment.end < highlight.start_time or segment.start > highlight.end_time:
                continue
            events.append(
                {
                    "type": "transcript_segment",
                    "time": round(max(segment.start, highlight.start_time) - clip_start, 3),
                    "end": round(min(segment.end, highlight.end_time) - clip_start, 3),
                    "text": segment.text,
                }
            )
        for word in transcript.word_timestamps:
            if word.end < highlight.start_time or word.start > highlight.end_time:
                continue
            events.append(
                {
                    "type": "word",
                    "time": round(word.start - clip_start, 3),
                    "end": round(word.end - clip_start, 3),
                    "text": word.word,
                    "probability": word.probability,
                }
            )

    events.sort(key=lambda item: item.get("time", 0.0))
    return events


def build_commentary_prompt(packet: CombatEvidencePacket) -> str:
    language_name = _language_name(packet.language)
    return (
        "You are a professional combat-sports commentator.\n"
        "Only comment based on the supplied evidence.\n"
        "Do not invent fighter names, round, result, title, injury, or rules.\n"
        "If evidence is uncertain, use cautious language.\n"
        f"Write every commentary line in {language_name}.\n"
        "Use natural, strong, short Shorts pacing. Each line should be 6-14 words.\n"
        "No emoji. No hashtag. Return valid JSON with key segments.\n\n"
        f"EVIDENCE:\n{json.dumps(asdict(packet), ensure_ascii=False, indent=2)}\n\n"
        "JSON schema: {\"segments\":[{\"start_time\":0.0,\"duration_estimate\":1.4,"
        "\"text\":\"...\",\"emotion\":\"tense\",\"evidence_used\":[\"impact\"],"
        "\"certainty\":\"high|medium|low\",\"style\":\"setup|impact|replay|cta\","
        "\"keywords\":[\"strike\"]}]}"
    )


def validate_or_fallback(segment: CommentarySegment, packet: CombatEvidencePacket) -> CommentarySegment:
    reasons = unsupported_claims(segment.text, packet)
    if reasons:
        logger.info(f"Rejected unsupported commentary claims: {reasons}")
        return fallback_segment(packet)
    segment.text = trim_commentary(segment.text)
    if not segment.keywords:
        segment.keywords = _keywords(segment.text)
    if not segment.evidence_used:
        segment.evidence_used = packet.signals
    segment.certainty = segment.certainty or _certainty(packet)
    segment.style = segment.style or _style(packet)
    return segment


def unsupported_claims(text: str, packet: CombatEvidencePacket) -> list[str]:
    normalized = _normalize(text)
    evidence = _normalize(" ".join([packet.transcript, *packet.reasons, *packet.visual_labels]))
    known = {k for k, v in packet.known_facts.items() if v}
    issues = []
    for claim, terms in UNSUPPORTED_CLAIMS.items():
        if not any(_normalize(term) in normalized for term in terms):
            continue
        if claim in {"round", "championship"}:
            if claim not in known:
                issues.append(claim)
            continue
        if not any(_normalize(term) in evidence for term in terms):
            issues.append(claim)
    if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text) and "fighter_names" not in known:
        issues.append("fighter_name")
    return sorted(set(issues))


def fallback_segment(packet: CombatEvidencePacket) -> CommentarySegment:
    primary = _primary_signal(packet)
    lines = SAFE_LINES.get(_language_key(packet.language), SAFE_LINES["vi"])
    text = lines.get(primary, lines["default"])
    start = max(0.0, packet.hook_time - packet.start_time - 0.25)
    return CommentarySegment(
        text=text,
        start_time=round(start, 2),
        duration_estimate=1.4,
        emotion="excited" if packet.confidence >= 0.85 else "tense",
        evidence_used=packet.signals,
        certainty=_certainty(packet),
        style=_style(packet),
        keywords=_keywords(text),
    )


def trim_commentary(text: str, min_words: int = 6, max_words: int = 14) -> str:
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).rstrip(",.;:") + "."


def _transcript_near_highlight(transcript: TranscriptResult, highlight: CombatHighlight) -> str:
    parts = []
    for segment in transcript.segments:
        if segment.end < highlight.start_time - 1.0 or segment.start > highlight.end_time + 1.0:
            continue
        parts.append(segment.text)
    return " ".join(parts)


def _primary_signal(packet: CombatEvidencePacket) -> str:
    for kind in ("impact", "submission", "scramble", "motion", "crowd_audio", "api_semantic"):
        if kind in packet.signals:
            return kind
    return "default"


def _style(packet: CombatEvidencePacket) -> str:
    if {"impact", "submission", "api_semantic"} & set(packet.signals):
        return "impact"
    if "replay_or_slowmo" in packet.signals:
        return "replay"
    return "setup"


def _certainty(packet: CombatEvidencePacket) -> str:
    if packet.confidence >= 0.9 and len(packet.signals) >= 2:
        return "high"
    if packet.confidence >= 0.75:
        return "medium"
    return "low"


def _keywords(text: str) -> list[str]:
    normalized = _normalize(text)
    return [word for word in IMPACT_KEYWORDS if _normalize(word) in normalized]


def _normalize(text: str) -> str:
    return text.lower()


def _language_name(code: str) -> str:
    return {
        "vi": "Vietnamese",
        "en": "American English",
        "en-US": "American English",
        "en-GB": "British English",
        "zh": "Chinese",
        "fr": "French",
        "fr-FR": "French",
        "de": "German",
        "de-DE": "German",
        "ja": "Japanese",
        "ja-JP": "Japanese",
        "ko": "Korean",
        "ko-KR": "Korean",
        "pt": "Brazilian Portuguese",
        "pt-BR": "Brazilian Portuguese",
        "es": "Spanish",
    }.get(code, code or "Vietnamese")


def _language_key(code: str) -> str:
    return {
        "en": "en-US",
        "fr": "fr-FR",
        "de": "de-DE",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "pt": "pt-BR",
    }.get(code, code or "vi")
