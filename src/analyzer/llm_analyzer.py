"""
LLM Analyzer — Phân tích video và đánh giá.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from src.core.config import AnalyzerConfig
from src.core.errors import AnalysisError
from src.core.logging import get_logger, log_duration
from src.core.types import AnalysisResult, VideoMetadata
from src.llm.prompts import PromptManager
from src.llm.provider import LLMProvider, generate_with_retry

logger = get_logger(__name__)


class LLMAnalyzer:
    """Phân tích nội dung video dùng LLM."""

    def __init__(self, config: AnalyzerConfig, llm_provider: LLMProvider) -> None:
        self._config = config
        self._llm = llm_provider
        self._prompt_manager = PromptManager()

    @log_duration(msg_template="Video analysis {func_name}")
    async def analyze(
        self,
        transcript_text: str,
        metadata: VideoMetadata,
    ) -> AnalysisResult:
        """Phân tích video từ transcript và metadata."""
        logger.info(f"Analyzing video: {metadata.video_id}")

        if not transcript_text.strip():
            logger.warning("Empty transcript, using metadata only.")

        prompt = self._prompt_manager.get(
            "analyze_content",
            transcript=transcript_text[:15000],  # Limit length
            title=metadata.title,
            description=metadata.description[:1000],
            duration=str(metadata.duration),
        )

        try:
            result_json = await generate_with_retry(
                self._llm,
                prompt,
                max_retries=3,
            )
            return AnalysisResult(**result_json)
        except Exception as e:
            raise AnalysisError(f"LLM analysis failed: {e}") from e
