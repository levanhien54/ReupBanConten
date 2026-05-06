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
    "impact": "Cú ra đòn này tạo áp lực ngay lập tức.",
    "submission": "Pha khóa siết này buộc đối thủ phải cảnh giác.",
    "scramble": "Tình huống áp sát khiến nhịp trận đổi chiều.",
    "motion": "Tốc độ pha này tăng lên rất nhanh.",
    "crowd_audio": "Khán giả phản ứng mạnh với khoảnh khắc này.",
    "api_semantic": "Đây là điểm nhấn đáng chú ý của pha bóng.",
    "default": "Khoảnh khắc này có thể đổi chiều trận đấu.",
}

IMPACT_KEYWORDS = ("gục", "knockout", "knockdown", "đòn", "siết", "ngã", "áp lực", "đổi chiều")


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


class CombatCommentaryGenerator:
    """Generate Vietnamese commentary that only uses supported evidence."""

    def __init__(self, llm: Optional[LLMProvider] = None) -> None:
        self._llm = llm

    async def generate_script(
        self,
        highlights: list[CombatHighlight],
        *,
        transcript: Optional[TranscriptResult] = None,
        sport: str = "combat",
        known_facts: Optional[dict[str, Optional[str]]] = None,
    ) -> CommentaryScript:
        packets = [
            build_evidence_packet(
                highlight,
                transcript=transcript,
                sport=sport,
                known_facts=known_facts,
            )
            for highlight in highlights
        ]
        segments = []
        for packet in packets:
            segment = await self.generate_segment(packet)
            segments.append(segment)
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
        prompt = build_commentary_prompt(packet)
        data = await self._llm.generate_json(prompt, temperature=0.2, max_tokens=900)
        item = (data.get("segments") or [data])[0]
        return CommentarySegment(
            text=str(item.get("text", "")).strip(),
            start_time=float(item.get("start_time", max(0.0, packet.hook_time - packet.start_time - 0.2))),
            duration_estimate=float(item.get("duration_estimate", 1.4)),
            emotion=str(item.get("emotion", "tense")),
            evidence_used=[str(x) for x in item.get("evidence_used", packet.signals)],
            certainty=str(item.get("certainty", _certainty(packet))),
            style=str(item.get("style", _style(packet))),
            keywords=[str(x) for x in item.get("keywords", _keywords(item.get("text", "")))],
        )


def build_evidence_packet(
    highlight: CombatHighlight,
    *,
    transcript: Optional[TranscriptResult] = None,
    sport: str = "combat",
    known_facts: Optional[dict[str, Optional[str]]] = None,
) -> CombatEvidencePacket:
    signals = sorted({signal.kind for signal in highlight.signals})
    text = _transcript_near_highlight(transcript, highlight) if transcript else ""
    timeline = build_timeline_evidence(highlight, transcript=transcript)
    visual_labels = []
    for signal in highlight.signals:
        if signal.kind == "api_semantic" and signal.reason:
            visual_labels.append(signal.reason)
    return CombatEvidencePacket(
        sport=sport,
        start_time=highlight.start_time,
        hook_time=highlight.hook_time,
        end_time=highlight.end_time,
        confidence=highlight.score,
        signals=signals,
        reasons=highlight.reasons,
        transcript=text,
        visual_labels=visual_labels,
        timeline=timeline,
        known_facts=known_facts or {},
    )


def build_timeline_evidence(
    highlight: CombatHighlight,
    *,
    transcript: Optional[TranscriptResult] = None,
) -> list[dict]:
    """Build relative timing evidence for commentary/subtitle alignment."""
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
    return (
        "Bạn là bình luận viên thể thao đối kháng chuyên nghiệp.\n"
        "Chỉ bình luận dựa trên evidence được cung cấp.\n"
        "Không bịa tên võ sĩ, hiệp đấu, kết quả, đai vô địch, chấn thương, hoặc luật.\n"
        "Nếu evidence chưa chắc chắn, dùng ngôn ngữ thận trọng.\n"
        "Viết tiếng Việt tự nhiên, mạnh, ngắn, đúng nhịp Shorts.\n"
        "Mỗi câu 6-14 từ. Không emoji. Không hashtag.\n"
        "Trả JSON có key segments.\n\n"
        f"EVIDENCE:\n{json.dumps(asdict(packet), ensure_ascii=False, indent=2)}\n\n"
        "JSON schema: {\"segments\":[{\"start_time\":0.0,\"duration_estimate\":1.4,"
        "\"text\":\"...\",\"emotion\":\"tense\",\"evidence_used\":[\"impact\"],"
        "\"certainty\":\"high|medium|low\",\"style\":\"setup|impact|replay|cta\","
        "\"keywords\":[\"đòn\"]}]}"
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
    text = SAFE_LINES.get(primary, SAFE_LINES["default"])
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
