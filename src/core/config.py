"""
Centralized Configuration Management.

Single source of truth cho toàn bộ config.
Load từ YAML → override bằng .env → validate bằng Pydantic.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────
#  Pydantic Config Models (type-safe, validated)
# ──────────────────────────────────────────────

class YoutubeApiConfig(BaseModel):
    api_key: Optional[str] = None
    enabled: bool = False                 # False = dùng yt-dlp flat scan
    max_results_per_page: int = 50        # 1..50 (API limit)
    request_timeout: int = 15


class ProxyConfig(BaseModel):
    enabled: bool = False
    url: Optional[str] = None             # http://user:pass@host:port
    test_url: str = "https://www.youtube.com"
    test_timeout: int = 10


class YtdlpConfig(BaseModel):
    cookies_file: Optional[str] = None
    proxy: Optional[str] = None           # sẽ được override bởi ProxyConfig nếu enabled
    rate_limit: Optional[str] = None
    retries: int = 3
    sleep_interval: int = 2


class MetadataConfig(BaseModel):
    extract_thumbnail: bool = True
    extract_subtitles: bool = True
    subtitle_languages: list[str] = Field(default_factory=lambda: ["vi", "en"])


class DownloaderConfig(BaseModel):
    max_concurrent: int = 3
    default_quality: str = "720p"
    preferred_format: str = "mp4"
    filter_shorts_only: bool = True
    max_video_duration: int = 180
    min_video_duration: int = 10
    max_videos_per_channel: int = 50
    ytdlp: YtdlpConfig = Field(default_factory=YtdlpConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    youtube_api: YoutubeApiConfig = Field(default_factory=YoutubeApiConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)


class WhisperConfig(BaseModel):
    model: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    language: Optional[str] = "vi"
    beam_size: int = 5
    vad_filter: bool = True
    word_timestamps: bool = True


class VisualConfig(BaseModel):
    enabled: bool = False
    model: str = "blip2"
    frame_interval: int = 5
    max_frames: int = 20


class TwelveLabsConfig(BaseModel):
    api_key: Optional[str] = None
    index_name: str = "reup_ban_conten_v2"
    engine_marengo: str = "marengo2.6"
    engine_pegasus: str = "pegasus1"
    auto_index: bool = True


class LLMConfig(BaseModel):
    provider: str = "ollama"
    fallback: list[str] = Field(default_factory=lambda: ["openai"])
    model: str = "llama3"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120
    chunk_size: int = 3000
    chunk_overlap: int = 200


class ClassifierConfig(BaseModel):
    categories: list[str] = Field(default_factory=lambda: [
        "entertainment", "education", "gaming", "music",
        "comedy", "lifestyle", "news", "tech", "sports", "other"
    ])


class AnalyzerConfig(BaseModel):
    whisper: WhisperConfig = Field(default_factory=WhisperConfig)
    visual: VisualConfig = Field(default_factory=VisualConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    twelve_labs: TwelveLabsConfig = Field(default_factory=TwelveLabsConfig)

    @property
    def transcriber(self) -> WhisperConfig:
        """Backward-compatible shortcut for older CLI/UI code."""
        return self.whisper


class SceneDetectionConfig(BaseModel):
    method: str = "content"
    threshold: float = 30.0
    min_scene_length: float = 2.0


class ClippingConfig(BaseModel):
    min_clip_duration: int = 3
    max_clip_duration: int = 30
    highlight_threshold: float = 0.7


class CutterConfig(BaseModel):
    scene_detection: SceneDetectionConfig = Field(default_factory=SceneDetectionConfig)
    clipping: ClippingConfig = Field(default_factory=ClippingConfig)


class TransitionConfig(BaseModel):
    enabled: bool = True
    default_type: str = "crossfade"
    duration: float = 0.5


class SubtitleConfig(BaseModel):
    enabled: bool = True
    font: str = "Arial"
    font_size: int = 60
    color: str = "yellow"
    outline_color: str = "black"
    outline_width: int = 3
    shadow_color: str = "rgba(0,0,0,0.5)"
    shadow_offset: tuple[int, int] = (5, 5)
    background_color: Optional[str] = None # e.g. "black@0.5"
    position: str = "bottom" # bottom, top, center
    word_highlight: bool = True
    highlight_color: str = "white"
    preset_style: str = "capcut_yellow" # capcut_yellow, modern_white, glow_pink


class OutputConfig(BaseModel):
    default_duration: int = 60
    min_duration: int = 15
    max_duration: int = 300
    fps: int = 30
    resolution: str = "1080x1920"
    codec: str = "libx264"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    video_bitrate: str = "5M"
    hardware_acceleration: str = "auto"


class EffectsConfig(BaseModel):
    transitions: TransitionConfig = Field(default_factory=TransitionConfig)
    subtitles: SubtitleConfig = Field(default_factory=SubtitleConfig)


class TransformationConfig(BaseModel):
    change_order: bool = True
    add_subtitles: bool = True
    add_transitions: bool = True
    speed_variation: bool = False
    color_shift: bool = False
    crop_variation: bool = False
    add_voiceover: bool = True


class SmartCropConfig(BaseModel):
    enabled: bool = True
    method: str = "face_tracking"
    smoothness: int = 15
    detection_fps: int = 2


class RemixerConfig(BaseModel):
    default_strategy: str = "energy-flow"
    strategies: list[str] = Field(default_factory=lambda: [
        "topic-based", "energy-flow", "narrative",
        "random-creative", "best-of", "chronological"
    ])
    output: OutputConfig = Field(default_factory=OutputConfig)
    effects: EffectsConfig = Field(default_factory=EffectsConfig)
    transformation: TransformationConfig = Field(default_factory=TransformationConfig)
    smart_crop: SmartCropConfig = Field(default_factory=SmartCropConfig)


class EmotionFilterConfig(BaseModel):
    enabled: bool = True
    flatness_threshold: float = 0.6
    segment_duration: float = 3.0
    use_speech_emotion: bool = False


class ElevenLabsConfig(BaseModel):
    model: str = "eleven_multilingual_v2"
    default_voice: Optional[str] = None
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.5
    speed: float = 1.0


class VoiceoverMixingConfig(BaseModel):
    original_volume_during_vo: float = 0.3
    voiceover_volume: float = 1.0
    fade_in: float = 0.2
    fade_out: float = 0.2


class CommentaryConfig(BaseModel):
    language: str = "vi"
    max_segments: int = 8
    min_gap_between: float = 3.0
    style: str = "entertaining"


class VoiceoverConfig(BaseModel):
    enabled: bool = True
    provider: str = "elevenlabs"
    elevenlabs: ElevenLabsConfig = Field(default_factory=ElevenLabsConfig)
    mixing: VoiceoverMixingConfig = Field(default_factory=VoiceoverMixingConfig)
    commentary: CommentaryConfig = Field(default_factory=CommentaryConfig)


class PreciseSceneConfig(BaseModel):
    content_threshold: float = 27.0
    adaptive_threshold: float = 3.5
    hist_threshold: float = 0.5
    min_scene_len: float = 1.0
    consensus_tolerance: float = 0.5


class BlackFlashFilterConfig(BaseModel):
    black_threshold: float = 15.0
    black_ratio: float = 0.7
    flash_threshold: float = 100.0
    min_segment_duration: float = 0.5


class CrossFolderRemixConfig(BaseModel):
    max_segments_per_folder: int = 3
    min_folders_used: int = 3
    no_adjacent_same_folder: bool = True
    segments_base_dir: str = "./data/segments"


class MemeSoundsConfig(BaseModel):
    default_volume: float = 0.7
    duck_original: bool = True
    duck_volume: float = 0.4


class MemeImagesConfig(BaseModel):
    default_size_ratio: float = 0.25
    default_duration: float = 2.0
    default_position: str = "bottom_right"
    fade_in: float = 0.2
    fade_out: float = 0.3


class MemeEffectsConfig(BaseModel):
    enabled: bool = True
    assets_dir: str = "./data/meme_assets"
    max_memes_per_video: int = 8
    min_gap_between_memes: float = 3.0
    auto_download_starter: bool = True
    sounds: MemeSoundsConfig = Field(default_factory=MemeSoundsConfig)
    images: MemeImagesConfig = Field(default_factory=MemeImagesConfig)


class PreprocessorConfig(BaseModel):
    enabled: bool = True
    resolution: int = 720
    fps: int = 20
    crf: int = 23
    chunk_size: int = 65536
    silence_threshold: float = -40.0
    min_silence_len: float = 0.5
    remove_black_frames: bool = True
    black_threshold: float = 0.05


class CombatSportsHighlightConfig(BaseModel):
    enabled: bool = True
    sports: list[str] = Field(default_factory=lambda: [
        "boxing",
        "mma",
        "muay_thai",
        "kickboxing",
        "bjj",
        "wrestling",
        "judo",
        "taekwondo",
    ])
    target_clip_duration: float = 2.5
    hook_duration: float = 1.5
    pre_action_padding: float = 0.8
    post_action_padding: float = 1.2
    min_highlight_score: float = 0.72
    max_same_fight_segments: int = 3
    weights: dict[str, float] = Field(default_factory=lambda: {
        "impact": 0.30,
        "motion": 0.20,
        "crowd_audio": 0.18,
        "commentary_intensity": 0.14,
        "camera_cut": 0.10,
        "replay_or_slowmo": 0.08,
    })


class DatabaseConfig(BaseModel):
    provider: str = "sqlite"  # sqlite, postgres
    path: str = "./data/reupbanconten.db"
    
    # PostgreSQL settings
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    dbname: str = "reup_ban_conten"


class StorageConfig(BaseModel):
    base_dir: str = "./data"
    downloads: str = "./data/downloads"
    clips: str = "./data/clips"
    segments: str = "./data/segments"
    outputs: str = "./data/outputs"
    cache: str = "./data/cache"
    thumbnails: str = "./data/thumbnails"
    transcripts: str = "./data/transcripts"
    voiceovers: str = "./data/voiceovers"
    meme_assets: str = "./data/meme_assets"
    logs: str = "./logs"

    @property
    def temp_dir(self) -> str:
        """Backward-compatible alias for older remixer code."""
        return self.cache

    @property
    def output_dir(self) -> str:
        """Backward-compatible alias for older remixer code."""
        return self.outputs


class AppConfig(BaseModel):
    """Root configuration — single source of truth."""

    name: str = "ReupBanConten"
    version: str = "0.1.0"
    description: str = "AI Video Remix Engine"
    log_level: str = "INFO"

    downloader: DownloaderConfig = Field(default_factory=DownloaderConfig)
    analyzer: AnalyzerConfig = Field(default_factory=AnalyzerConfig)
    twelve_labs: TwelveLabsConfig = Field(default_factory=TwelveLabsConfig)
    cutter: CutterConfig = Field(default_factory=CutterConfig)
    remixer: RemixerConfig = Field(default_factory=RemixerConfig)
    emotion_filter: EmotionFilterConfig = Field(default_factory=EmotionFilterConfig)
    voiceover: VoiceoverConfig = Field(default_factory=VoiceoverConfig)
    scene_detection_precise: PreciseSceneConfig = Field(default_factory=PreciseSceneConfig)
    black_flash_filter: BlackFlashFilterConfig = Field(default_factory=BlackFlashFilterConfig)
    cross_folder_remix: CrossFolderRemixConfig = Field(default_factory=CrossFolderRemixConfig)
    meme_effects: MemeEffectsConfig = Field(default_factory=MemeEffectsConfig)
    preprocessor: PreprocessorConfig = Field(default_factory=PreprocessorConfig)
    combat_sports: CombatSportsHighlightConfig = Field(default_factory=CombatSportsHighlightConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @property
    def llm(self) -> LLMConfig:
        """Backward-compatible shortcut for older modules."""
        return self.analyzer.llm

    def ensure_directories(self) -> None:
        """Tạo tất cả thư mục cần thiết."""
        for field_name, field_value in self.storage:
            if field_name != "base_dir":
                Path(field_value).mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
#  Config Loader (singleton)
# ──────────────────────────────────────────────

_config_instance: Optional[AppConfig] = None


def load_config(
    config_path: str = "config/settings.yaml",
    env_path: str = ".env",
    *,
    force_reload: bool = False,
) -> AppConfig:
    """
    Load config theo thứ tự ưu tiên:
    1. YAML file (base)
    2. .env file (override)
    3. Environment variables (highest priority)
    """
    global _config_instance
    if _config_instance is not None and not force_reload:
        return _config_instance

    # Load .env
    env_file = Path(env_path)
    if env_file.exists():
        load_dotenv(env_file)

    # Load YAML
    yaml_data = {}
    yaml_file = Path(config_path)
    if yaml_file.exists():
        with open(yaml_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
            if raw and isinstance(raw, dict):
                # Flatten 'app' key if present
                if "app" in raw:
                    yaml_data.update(raw.pop("app"))
                yaml_data.update(raw)

    # ENV overrides (selected keys)
    env_overrides = {
        "log_level": os.getenv("LOG_LEVEL"),
    }
    for key, value in env_overrides.items():
        if value is not None:
            yaml_data[key] = value

    # LLM provider override from env
    llm_provider = os.getenv("LLM_PROVIDER")
    if llm_provider:
        yaml_data.setdefault("analyzer", {}).setdefault("llm", {})["provider"] = llm_provider

    # Build & validate
    _config_instance = AppConfig(**yaml_data)
    _config_instance.ensure_directories()

    return _config_instance


def get_config() -> AppConfig:
    """Get current config (must call load_config first)."""
    if _config_instance is None:
        return load_config()
    return _config_instance
