"""
Video Transcriber — Sử dụng faster-whisper.
"""
from __future__ import annotations

import os
from typing import Optional

from faster_whisper import WhisperModel

from src.core.config import WhisperConfig
from src.core.errors import TranscriptionError
from src.core.logging import get_logger, log_duration
from src.core.types import TranscriptResult, TranscriptSegment, WordTimestamp

logger = get_logger(__name__)


class Transcriber:
    """Class wrapper cho faster-whisper."""

    def __init__(self, config: WhisperConfig, output_dir: Optional[str] = None) -> None:
        self._config = config
        self._model: Optional[WhisperModel] = None
        self._output_dir = output_dir

    def transcribe_with_cache(self, audio_path: str, video_id: str) -> TranscriptResult:
        """Thực hiện transcription và lưu cache JSON."""
        if self._output_dir:
            cache_path = os.path.join(self._output_dir, f"{video_id}.json")
            if os.path.exists(cache_path):
                logger.info(f"Loading transcription from cache: {cache_path}")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return TranscriptResult.model_validate_json(f.read())

        result = self.transcribe(audio_path)

        if self._output_dir:
            cache_path = os.path.join(self._output_dir, f"{video_id}.json")
            os.makedirs(self._output_dir, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))
            logger.info(f"Transcription saved to cache: {cache_path}")

        return result

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                f"Loading Whisper model: {self._config.model} "
                f"({self._config.device}, {self._config.compute_type})"
            )
            try:
                self._model = WhisperModel(
                    self._config.model,
                    device=self._config.device,
                    compute_type=self._config.compute_type,
                )
            except Exception as e:
                raise TranscriptionError(f"Failed to load Whisper model: {e}") from e
        return self._model

    @log_duration(msg_template="Transcription {func_name}")
    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Trích xuất văn bản từ audio/video."""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._get_model()
        logger.info(f"Transcribing: {os.path.basename(audio_path)}")

        try:
            segments_generator, info = model.transcribe(
                audio_path,
                language=self._config.language,
                beam_size=self._config.beam_size,
                vad_filter=self._config.vad_filter,
                word_timestamps=self._config.word_timestamps,
            )

            result_segments = []
            result_words = []
            full_text_parts = []

            for segment in segments_generator:
                result_segments.append(
                    TranscriptSegment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                    )
                )
                full_text_parts.append(segment.text.strip())

                if self._config.word_timestamps and segment.words:
                    for word in segment.words:
                        result_words.append(
                            WordTimestamp(
                                word=word.word.strip(),
                                start=word.start,
                                end=word.end,
                                probability=word.probability,
                            )
                        )

            full_text = " ".join(full_text_parts)

            return TranscriptResult(
                full_text=full_text,
                segments=result_segments,
                word_timestamps=result_words,
                detected_language=info.language,
                language_probability=info.language_probability,
                duration=info.duration,
            )

        except Exception as e:
            raise TranscriptionError(
                f"Transcription failed for {audio_path}: {e}"
            ) from e
