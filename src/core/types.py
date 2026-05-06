"""
Domain Types & Data Models.

Immutable data structures dùng xuyên suốt pipeline.
Tất cả đều là Pydantic models → serializable, validated, documented.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────────

class VideoStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    CUTTING = "cutting"
    CUT = "cut"
    FAILED = "failed"


class Mood(str, Enum):
    HAPPY = "happy"
    SAD = "sad"
    EXCITING = "exciting"
    CALM = "calm"
    FUNNY = "funny"
    DRAMATIC = "dramatic"
    NEUTRAL = "neutral"


class EnergyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PEAK = "peak"


class ContentType(str, Enum):
    DIALOGUE = "dialogue"
    ACTION = "action"
    REACTION = "reaction"
    TRANSITION = "transition"
    INTRO = "intro"
    OUTRO = "outro"
    UNKNOWN = "unknown"


class RemixStrategy(str, Enum):
    TOPIC_BASED = "topic-based"
    ENERGY_FLOW = "energy-flow"
    NARRATIVE = "narrative"
    RANDOM_CREATIVE = "random-creative"
    BEST_OF = "best-of"
    CHRONOLOGICAL = "chronological"


class TransitionType(str, Enum):
    CROSSFADE = "crossfade"
    FADE = "fade"
    SLIDE = "slide"
    ZOOM = "zoom"
    CUT = "cut"


class MemeType(str, Enum):
    SOUND = "sound"
    IMAGE = "image"
    BOTH = "both"


# ──────────────────────────────────────────────
#  Video & Channel Models
# ──────────────────────────────────────────────

class ChannelInfo(BaseModel):
    """Thông tin kênh YouTube."""
    url: str
    name: Optional[str] = None
    channel_id: Optional[str] = None
    subscriber_count: Optional[int] = None
    video_count: Optional[int] = None
    scanned_at: Optional[datetime] = None


class VideoInfo(BaseModel):
    """Thông tin cơ bản 1 video (từ scan)."""
    video_id: str
    url: str
    title: Optional[str] = None
    duration: Optional[float] = None
    view_count: Optional[int] = 0
    upload_date: Optional[str] = None


class VideoMetadata(BaseModel):
    """Metadata đầy đủ của video."""
    video_id: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    duration: float = 0.0
    view_count: int = 0
    like_count: Optional[int] = None
    upload_date: Optional[str] = None
    thumbnail_url: Optional[str] = None
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    subtitles: dict[str, Any] = Field(default_factory=dict)


class DownloadedVideo(BaseModel):
    """Video đã tải về máy."""
    video_id: str
    file_path: str
    file_hash: Optional[str] = None
    metadata: VideoMetadata
    status: VideoStatus = VideoStatus.DOWNLOADED
    downloaded_at: datetime = Field(default_factory=datetime.now)


# ──────────────────────────────────────────────
#  Transcript Models
# ──────────────────────────────────────────────

class WordTimestamp(BaseModel):
    """Timestamp cho từng từ."""
    word: str
    start: float
    end: float
    probability: float = 1.0


class TranscriptSegment(BaseModel):
    """1 đoạn transcript có timestamp."""
    start: float
    end: float
    text: str


class TranscriptResult(BaseModel):
    """Kết quả transcription đầy đủ."""
    full_text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
    word_timestamps: list[WordTimestamp] = Field(default_factory=list)
    detected_language: str = "unknown"
    language_probability: float = 0.0
    duration: float = 0.0


# ──────────────────────────────────────────────
#  Analysis Models
# ──────────────────────────────────────────────

class KeyMoment(BaseModel):
    """Một khoảnh khắc quan trọng trong video."""
    start_time: float
    end_time: float
    description: str = ""
    energy_score: float = 0.5
    is_highlight: bool = False


class CombatSignal(BaseModel):
    """Raw signal used to rank a combat-sports highlight."""
    time: float
    score: float
    kind: str
    reason: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class CombatHighlight(BaseModel):
    """Ranked candidate for a short combat-sports hook clip."""
    start_time: float
    end_time: float
    hook_time: float
    score: float
    reasons: list[str] = Field(default_factory=list)
    signals: list[CombatSignal] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Kết quả phân tích LLM."""
    topics: list[str] = Field(default_factory=list)
    mood: Mood = Mood.NEUTRAL
    category: str = "other"
    summary: str = ""
    language: str = "unknown"
    has_speech: bool = True
    key_moments: list[KeyMoment] = Field(default_factory=list)
    overall_energy: float = 0.5
    viral_potential: float = 0.5


# ──────────────────────────────────────────────
#  Scene & Clip Models
# ──────────────────────────────────────────────

class SceneBoundary(BaseModel):
    """Ranh giới giữa 2 cảnh."""
    cut_time: float
    confidence: float = 1.0
    methods: list[str] = Field(default_factory=list)


class VideoSegment(BaseModel):
    """1 segment (scene) của video."""
    index: int
    start_time: float
    end_time: float
    duration: float
    confidence: float = 1.0
    methods: list[str] = Field(default_factory=list)


class SegmentQuality(BaseModel):
    """Kết quả kiểm tra chất lượng segment."""
    is_bad: bool = False
    reasons: list[str] = Field(default_factory=list)
    black_ratio: float = 0.0
    flash_rate: float = 0.0
    flash_count: int = 0
    avg_brightness: float = 128.0
    brightness_std: float = 0.0
    duration: float = 0.0


class Clip(BaseModel):
    """1 clip đã cắt từ video gốc."""
    id: Optional[int] = None
    video_id: str
    file_path: str
    start_time: float
    end_time: float
    duration: float
    highlight_score: float = 0.5
    transcript_segment: str = ""
    source_folder: Optional[str] = None

    # Tags
    tags: list[str] = Field(default_factory=list)
    mood: Mood = Mood.NEUTRAL
    energy_level: EnergyLevel = EnergyLevel.MEDIUM
    content_type: ContentType = ContentType.UNKNOWN


# ──────────────────────────────────────────────
#  Remix Models
# ──────────────────────────────────────────────

class RemixStep(BaseModel):
    """1 bước trong kịch bản remix."""
    clip_id: Optional[str | int] = None
    folder: Optional[str] = None
    segment: Optional[str] = None
    transition_in: TransitionType = TransitionType.CROSSFADE
    transition_duration: float = 0.5
    speed_factor: float = 1.0
    duration: float = 0.0
    notes: str = ""
    visual_description: str = ""
    
    # Uniqueness fields
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    zoom_factor: float = 1.0
    brightness_factor: float = 1.0
    contrast_factor: float = 1.0
    mirror: bool = False
    
    # Audio/Voiceover
    commentary_text: str = ""
    audio_path: Optional[str] = None


class RemixScript(BaseModel):
    """Kịch bản remix đầy đủ."""
    title: str = "Untitled Remix"
    description: str = ""
    sequence: list[RemixStep] = Field(default_factory=list)
    estimated_duration: float = 0.0
    mood_flow: str = ""
    strategy: RemixStrategy = RemixStrategy.ENERGY_FLOW
    folder_usage: dict[str, int] = Field(default_factory=dict)
    balance_score: float = 0.0


# ──────────────────────────────────────────────
#  Meme & Voiceover Models
# ──────────────────────────────────────────────

class MemePlacement(BaseModel):
    """Vị trí đặt meme trong video."""
    time: float
    type: MemeType = MemeType.SOUND
    sound_path: Optional[str] = None
    image_path: Optional[str] = None
    sound_category: str = ""
    image_category: str = ""
    position: str = "bottom_right"
    duration: float = 2.0
    volume: float = 0.7
    size_ratio: float = 0.25
    reason: str = ""


class CommentarySegment(BaseModel):
    """1 đoạn bình luận voiceover."""
    text: str
    start_time: float
    duration_estimate: float = 3.0
    emotion: str = "neutral"
    audio_path: Optional[str] = None
    evidence_used: list[str] = Field(default_factory=list)
    certainty: str = "medium"
    style: str = "setup"
    keywords: list[str] = Field(default_factory=list)


class CommentaryScript(BaseModel):
    """Kịch bản bình luận đầy đủ."""
    intro: Optional[CommentarySegment] = None
    segments: list[CommentarySegment] = Field(default_factory=list)
    outro: Optional[CommentarySegment] = None
    total_segments: int = 0
    estimated_total_duration: float = 0.0


# ──────────────────────────────────────────────
#  Emotion Filter Models
# ──────────────────────────────────────────────

class EmotionFeatures(BaseModel):
    """Audio features cho emotion detection."""
    start_time: float
    end_time: float
    duration: float
    pitch_mean: float = 0.0
    pitch_std: float = 0.0
    pitch_range: float = 0.0
    pitch_variance_score: float = 0.0
    voiced_ratio: float = 0.0
    energy_mean: float = 0.0
    energy_std: float = 0.0
    energy_dynamic_range: float = 0.0
    energy_variance_score: float = 0.0
    tempo: float = 0.0
    onset_density: float = 0.0
    spectral_centroid_std: float = 0.0
    spectral_bandwidth_mean: float = 0.0
    silence_ratio: float = 0.0
    flatness_score: float = 0.0
    is_flat: bool = False


class FilterResult(BaseModel):
    """Kết quả lọc emotion."""
    kept_segments: list[EmotionFeatures] = Field(default_factory=list)
    removed_segments: list[EmotionFeatures] = Field(default_factory=list)
    total_segments: int = 0
    kept_count: int = 0
    removed_count: int = 0
    kept_ratio: float = 0.0
    avg_flatness: float = 0.0


# ──────────────────────────────────────────────
#  Folder Organization Models
# ──────────────────────────────────────────────

class SegmentFile(BaseModel):
    """1 segment file trong folder."""
    file_path: str
    file_name: str
    index: int
    start_time: float
    end_time: float
    duration: float
    confidence: float = 1.0
    source_video: str = ""
    folder: str = ""
    transcript_segment: str = ""
    visual_description: str = ""
    mood: str = "neutral"


class VideoFolder(BaseModel):
    """1 folder chứa segments từ 1 video gốc."""
    folder_name: str
    folder_path: str
    source_video: str
    total_segments: int = 0
    segments: list[SegmentFile] = Field(default_factory=list)
