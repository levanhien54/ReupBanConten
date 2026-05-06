"""
Tests cho core modules: config, logging, errors, types, events, database.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

# ──────────────────────────────────────────────
#  Config Tests
# ──────────────────────────────────────────────

class TestConfig:
    """Test configuration loading và validation."""

    def test_default_config(self):
        """Tạo config với default values."""
        from src.core.config import AppConfig

        config = AppConfig()
        assert config.name == "ReupBanConten"
        assert config.version == "0.1.0"
        assert config.downloader.max_concurrent == 3
        assert config.analyzer.whisper.model == "large-v3"

    def test_config_override(self):
        """Override specific fields."""
        from src.core.config import AppConfig

        config = AppConfig(
            log_level="DEBUG",
            downloader={"max_concurrent": 5, "default_quality": "1080p"},
        )
        assert config.log_level == "DEBUG"
        assert config.downloader.max_concurrent == 5
        assert config.downloader.default_quality == "1080p"
        # Non-overridden fields keep defaults
        assert config.downloader.preferred_format == "mp4"

    def test_config_validation(self):
        """Pydantic validates types."""
        from src.core.config import DownloaderConfig

        config = DownloaderConfig(max_concurrent=5)
        assert isinstance(config.max_concurrent, int)


# ──────────────────────────────────────────────
#  Errors Tests
# ──────────────────────────────────────────────

class TestErrors:
    """Test exception hierarchy."""

    def test_base_error(self):
        from src.core.errors import ReupError

        err = ReupError("test error", error_code="TEST", context={"key": "val"})
        assert "TEST" in str(err)
        assert "key=val" in str(err)

    def test_download_error_hierarchy(self):
        from src.core.errors import DownloadError, ChannelNotFoundError, ReupError

        err = ChannelNotFoundError("not found")
        assert isinstance(err, DownloadError)
        assert isinstance(err, ReupError)

    def test_llm_error_context(self):
        from src.core.errors import LLMResponseParseError

        err = LLMResponseParseError(
            "parse failed",
            context={"response_preview": "invalid json..."},
        )
        assert "response_preview" in err.context


# ──────────────────────────────────────────────
#  Types Tests
# ──────────────────────────────────────────────

class TestTypes:
    """Test domain types serialization."""

    def test_video_info(self):
        from src.core.types import VideoInfo

        v = VideoInfo(video_id="abc123", url="https://youtube.com/watch?v=abc123")
        assert v.video_id == "abc123"

    def test_clip_serialization(self):
        from src.core.types import Clip, Mood, EnergyLevel

        clip = Clip(
            video_id="abc123",
            file_path="/data/clip.mp4",
            start_time=5.0,
            end_time=15.0,
            duration=10.0,
            mood=Mood.EXCITING,
            energy_level=EnergyLevel.HIGH,
        )
        data = clip.model_dump()
        assert data["mood"] == "exciting"
        assert data["energy_level"] == "high"

    def test_remix_script(self):
        from src.core.types import RemixScript, RemixStep, TransitionType

        script = RemixScript(
            title="Test Remix",
            sequence=[
                RemixStep(clip_id=1, transition_in=TransitionType.CROSSFADE),
                RemixStep(clip_id=2, transition_in=TransitionType.CUT),
            ],
        )
        assert len(script.sequence) == 2


# ──────────────────────────────────────────────
#  Events Tests
# ──────────────────────────────────────────────

class TestEvents:
    """Test event bus pub/sub."""

    @pytest.mark.asyncio
    async def test_event_subscribe_emit(self):
        from src.core.events import EventBus, EventType

        bus = EventBus()
        received = []

        @bus.on(EventType.VIDEO_DOWNLOAD_COMPLETED)
        async def handler(event):
            received.append(event.data)

        await bus.emit(
            EventType.VIDEO_DOWNLOAD_COMPLETED,
            {"video_id": "abc123"},
        )

        assert len(received) == 1
        assert received[0]["video_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_global_handler(self):
        from src.core.events import EventBus, EventType

        bus = EventBus()
        all_events = []

        async def global_handler(event):
            all_events.append(event.type)

        bus.subscribe_all(global_handler)

        await bus.emit(EventType.PIPELINE_STARTED)
        await bus.emit(EventType.VIDEO_DOWNLOAD_COMPLETED)

        assert len(all_events) == 2

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_crash(self):
        from src.core.events import EventBus, EventType

        bus = EventBus()

        @bus.on(EventType.PIPELINE_STARTED)
        async def bad_handler(event):
            raise ValueError("Handler error!")

        # Should not raise
        await bus.emit(EventType.PIPELINE_STARTED)


# ──────────────────────────────────────────────
#  Database Tests
# ──────────────────────────────────────────────

class TestDatabase:
    """Test database operations."""

    def test_init_creates_tables(self, tmp_path):
        from src.core.database import Database

        db = Database(str(tmp_path / "test.db"))
        tables = db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {t["name"] for t in tables}
        assert "videos" in table_names
        assert "clips" in table_names
        assert "channels" in table_names
        db.close()

    def test_video_repository(self, tmp_path):
        from src.core.database import Database, VideoRepository

        db = Database(str(tmp_path / "test.db"))
        repo = VideoRepository(db)

        # Insert
        vid_id = repo.upsert("test_vid", url="https://...", title="Test", duration=30)
        assert vid_id > 0

        # Read
        video = repo.get_by_video_id("test_vid")
        assert video is not None
        assert video["title"] == "Test"

        # Update
        repo.update_status("test_vid", "downloaded")
        video = repo.get_by_video_id("test_vid")
        assert video["status"] == "downloaded"

        db.close()


# ──────────────────────────────────────────────
#  LLM JSON Parser Tests
# ──────────────────────────────────────────────

class TestLLMJsonParser:
    """Test JSON parsing from LLM responses."""

    def test_direct_json(self):
        from src.llm.provider import parse_llm_json

        result = parse_llm_json('{"key": "value"}')
        assert result["key"] == "value"

    def test_markdown_block(self):
        from src.llm.provider import parse_llm_json

        response = 'Here is the result:\n```json\n{"topics": ["a", "b"]}\n```'
        result = parse_llm_json(response)
        assert result["topics"] == ["a", "b"]

    def test_embedded_json(self):
        from src.llm.provider import parse_llm_json

        response = 'Some text before {"mood": "happy"} some text after'
        result = parse_llm_json(response)
        assert result["mood"] == "happy"

    def test_invalid_json_raises(self):
        from src.core.errors import LLMResponseParseError
        from src.llm.provider import parse_llm_json

        with pytest.raises(LLMResponseParseError):
            parse_llm_json("this is not json at all")
