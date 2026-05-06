"""
Event Bus — Pub/Sub cho pipeline communication.

Cho phép các module giao tiếp loose-coupled.
Dùng để: progress tracking, logging, UI updates, plugin hooks.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


class EventType(str, Enum):
    """Tất cả event types trong hệ thống."""

    # Pipeline
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"

    # Download
    CHANNEL_SCAN_STARTED = "download.scan_started"
    CHANNEL_SCAN_COMPLETED = "download.scan_completed"
    VIDEO_DOWNLOAD_STARTED = "download.video_started"
    VIDEO_DOWNLOAD_COMPLETED = "download.video_completed"
    VIDEO_DOWNLOAD_FAILED = "download.video_failed"
    BATCH_DOWNLOAD_PROGRESS = "download.batch_progress"

    # Analysis
    TRANSCRIPTION_STARTED = "analysis.transcribe_started"
    TRANSCRIPTION_COMPLETED = "analysis.transcribe_completed"
    LLM_ANALYSIS_STARTED = "analysis.llm_started"
    LLM_ANALYSIS_COMPLETED = "analysis.llm_completed"

    # Emotion Filter
    EMOTION_FILTER_STARTED = "filter.emotion_started"
    EMOTION_FILTER_COMPLETED = "filter.emotion_completed"

    # Cutting
    SCENE_DETECTION_STARTED = "cut.scene_started"
    SCENE_DETECTION_COMPLETED = "cut.scene_completed"
    CLIP_EXPORTED = "cut.clip_exported"

    # Remix
    SCRIPT_GENERATED = "remix.script_generated"
    ASSEMBLY_STARTED = "remix.assembly_started"
    ASSEMBLY_COMPLETED = "remix.assembly_completed"
    RENDER_STARTED = "remix.render_started"
    RENDER_PROGRESS = "remix.render_progress"
    RENDER_COMPLETED = "remix.render_completed"

    # Meme & Voiceover
    MEME_APPLIED = "effects.meme_applied"
    VOICEOVER_GENERATED = "effects.voiceover_generated"

    # General
    PROGRESS = "general.progress"
    WARNING = "general.warning"
    ERROR = "general.error"


@dataclass
class Event:
    """Immutable event object."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""

    def __str__(self) -> str:
        return f"Event({self.type.value}, source={self.source}, data_keys={list(self.data.keys())})"


# Type alias for handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None] | None]


class EventBus:
    """
    In-process event bus (pub/sub).

    Usage:
        bus = EventBus()

        # Subscribe
        @bus.on(EventType.VIDEO_DOWNLOAD_COMPLETED)
        async def on_download(event: Event):
            print(f"Downloaded: {event.data['video_id']}")

        # Publish
        await bus.emit(EventType.VIDEO_DOWNLOAD_COMPLETED, {
            "video_id": "abc123",
            "path": "/data/abc123.mp4",
        })
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []

    def on(self, event_type: EventType) -> Callable:
        """Decorator để subscribe handler."""
        def decorator(func: EventHandler) -> EventHandler:
            self.subscribe(event_type, func)
            return func
        return decorator

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe handler cho event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe handler cho TẤT CẢ events (dùng cho logging)."""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe handler."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def emit(
        self,
        event_type: EventType,
        data: Optional[dict[str, Any]] = None,
        source: str = "",
    ) -> None:
        """Publish event đến tất cả subscribers."""
        event = Event(type=event_type, data=data or {}, source=source)

        # Global handlers first
        for handler in self._global_handlers:
            await self._call_handler(handler, event)

        # Type-specific handlers
        for handler in self._handlers.get(event_type, []):
            await self._call_handler(handler, event)

    async def _call_handler(self, handler: EventHandler, event: Event) -> None:
        """Gọi handler an toàn (catch exceptions)."""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            # Log nhưng không crash pipeline
            import logging
            logging.getLogger("src.core.events").error(
                f"Event handler error: {handler.__name__} for {event.type}: {e}",
                exc_info=True,
            )

    def clear(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()
        self._global_handlers.clear()


# ──────────────────────────────────────────────
#  Global event bus instance
# ──────────────────────────────────────────────

_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
