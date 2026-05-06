"""
Remix Script Generator.
Sử dụng LLM để tạo kịch bản từ nhiều folders khác nhau.
"""
from __future__ import annotations

import json
import random
from typing import Any

from src.core.config import RemixerConfig, CrossFolderRemixConfig
from src.core.errors import ScriptGenerationError
from src.core.logging import get_logger, log_duration
from src.core.types import RemixScript, RemixStep, VideoFolder, SegmentFile, CommentaryScript, CommentarySegment, MemePlacement, MemeType
from src.llm.prompts import PromptManager
from src.llm.provider import LLMProvider, generate_with_retry

logger = get_logger(__name__)


class ScriptGenerator:
    """Tạo kịch bản remix thông minh."""

    def __init__(
        self,
        config: RemixerConfig,
        cross_folder_config: CrossFolderRemixConfig,
        llm: LLMProvider
    ) -> None:
        self._config = config
        self._cf_config = cross_folder_config
        self._llm = llm
        self._prompt_manager = PromptManager()

    @log_duration(msg_template="Script generation {func_name}")
    async def generate_cross_folder_script(
        self,
        folders: list[VideoFolder],
        target_duration: float = 60.0
    ) -> RemixScript:
        """Tạo kịch bản cross-folder remix dùng LLM."""
        if len(folders) < self._cf_config.min_folders_used:
            raise ScriptGenerationError(
                f"Not enough folders for cross-folder remix. "
                f"Got {len(folders)}, need {self._cf_config.min_folders_used}"
            )

        # Chuẩn bị dữ liệu cho LLM
        folders_desc = self._prepare_folders_description(folders)

        prompt = self._prompt_manager.get(
            "cross_folder_remix",
            max_per_folder=str(self._cf_config.max_segments_per_folder),
            min_folders=str(self._cf_config.min_folders_used),
            target_duration=str(target_duration),
            folders_description=folders_desc,
        )

        try:
            result_json = await generate_with_retry(
                self._llm,
                prompt,
                max_retries=3,
            )
            
            # Validate output rules
            self._validate_cross_folder_rules(result_json, folders)
            
            # Convert JSON array to RemixSteps
            steps = []
            for item in result_json.get("sequence", []):
                # Tìm thời lượng thực tế của segment từ dữ liệu đầu vào
                duration = 5.0 # default
                folder_name = item.get("folder")
                seg_name = item.get("segment")
                for f in folders:
                    if f.folder_name == folder_name:
                        for s in f.segments:
                            if s.file_name == target_seg:
                                found_seg = s
                                break
                
                steps.append(
                    RemixStep(
                        folder=target_folder,
                        segment=target_seg,
                        transition_in=item.get("transition", "crossfade"),
                        duration=found_seg.duration if found_seg else 5.0,
                        notes=item.get("reason", ""),
                        visual_description=found_seg.visual_description if found_seg else ""
                    )
                )

            return RemixScript(
                title=result_json.get("title", "Untitled Remix"),
                sequence=steps,
                estimated_duration=result_json.get("estimated_duration", target_duration),
                mood_flow=result_json.get("mood_flow", ""),
                folder_usage=result_json.get("folder_usage", {}),
                balance_score=result_json.get("balance_score", 1.0),
            )

        except Exception as e:
            raise ScriptGenerationError(f"Cross-folder script generation failed: {e}") from e

    def _prepare_folders_description(self, folders: list[VideoFolder]) -> str:
        lines = []
        for f in folders:
            lines.append(f"Folder: {f.folder_name} (Source: {f.source_video})")
            
            # Ưu tiên các segment có độ tin cậy (confidence) cao nhất thay vì lấy ngẫu nhiên
            sorted_segments = sorted(f.segments, key=lambda x: x.confidence, reverse=True)
            sample_segments = sorted_segments[:15] # Lấy top 15 highlights
            
            for s in sample_segments:
                dur = f"{s.duration:.1f}s"
                conf = f"conf:{s.confidence:.2f}"
                mood = s.mood.value if hasattr(s.mood, 'value') else str(s.mood)
                # Thêm transcript và mô tả hình ảnh để LLM hiểu bối cảnh đa phương thức
                transcript = (s.transcript_segment[:80] + "...") if len(s.transcript_segment) > 80 else s.transcript_segment
                visual = s.visual_description or "No visual data"
                
                lines.append(f"  - {s.file_name} [{dur}] ({conf}) Mood:{mood} | Visual: {visual} | Text: {transcript}")
        return "\n".join(lines)

    def _validate_cross_folder_rules(self, script_data: dict, folders: list[VideoFolder]) -> None:
        """Ensure LLM followed the strict cross-folder constraints."""
        sequence = script_data.get("sequence", [])
        if not sequence:
            raise ScriptGenerationError("LLM returned empty sequence")

        folder_counts = {}
        prev_folder = None

        for item in sequence:
            folder = item.get("folder")
            if not folder:
                continue

            # 1. Max segments per folder check
            folder_counts[folder] = folder_counts.get(folder, 0) + 1
            if folder_counts[folder] > self._cf_config.max_segments_per_folder:
                raise ScriptGenerationError(
                    f"Rule broken: Used more than {self._cf_config.max_segments_per_folder} "
                    f"segments from folder {folder}"
                )

            # 2. Adjacent same folder check
            if self._cf_config.no_adjacent_same_folder and folder == prev_folder:
                raise ScriptGenerationError(
                    f"Rule broken: Adjacent segments from the same folder {folder}"
                )

            prev_folder = folder

        # 3. Min folders used check
        if len(folder_counts) < self._cf_config.min_folders_used:
            raise ScriptGenerationError(
                f"Rule broken: Used only {len(folder_counts)} folders, "
                f"need at least {self._cf_config.min_folders_used}"
            )
    @log_duration(msg_template="Commentary generation {func_name}")
    async def generate_commentary_script(
        self,
        remix_script: RemixScript,
        language: str = "vi"
    ) -> CommentaryScript:
        """
        Tạo kịch bản bình luận AI dựa trên remix script và ngôn ngữ được chọn.
        """
        logger.info(f"Generating {language} commentary for remix: {remix_script.title}")

        # Chuẩn bị mô tả các clips trong sequence để LLM hiểu bối cảnh và thời lượng
        clips_desc = []
        current_time = 0.0
        for i, step in enumerate(remix_script.sequence):
            # Tìm segment tương ứng để lấy transcript gốc
            orig_text = ""
            # Giả định folder_name và file_name đã được lưu trong step
            # Đây là điểm cần tối ưu: nên lưu transcript trực tiếp vào RemixStep
            
            clips_desc.append(
                f"Clip {i+1}: [{current_time:.1f}s -> {current_time + step.duration:.1f}s] "
                f"(Dur: {step.duration:.1f}s) | Context: {step.notes}"
            )
            current_time += step.duration
        
        clips_description = "\n".join(clips_desc)

        prompt = self._prompt_manager.get(
            "generate_commentary",
            remix_title=remix_script.title,
            strategy=remix_script.strategy,
            total_duration=str(remix_script.estimated_duration),
            clips_description=clips_description,
            language=language
        )

        try:
            result_json = await generate_with_retry(
                self._llm,
                prompt,
                max_retries=3,
            )

            # Map JSON to CommentaryScript
            intro_data = result_json.get("intro", {})
            intro = CommentarySegment(
                text=intro_data.get("text", ""),
                start_time=intro_data.get("start_time", 0.0),
                emotion=intro_data.get("emotion", "excited")
            )

            outro_data = result_json.get("outro", {})
            outro = CommentarySegment(
                text=outro_data.get("text", ""),
                start_time=outro_data.get("start_time", remix_script.estimated_duration - 2.0),
                emotion=outro_data.get("emotion", "excited")
            )

            segments = []
            for seg in result_json.get("segments", []):
                segments.append(
                    CommentarySegment(
                        text=seg.get("text", ""),
                        start_time=seg.get("start_time", 0.0),
                        duration_estimate=seg.get("duration_estimate", 3.0),
                        emotion=seg.get("emotion", "neutral")
                    )
                )

            return CommentaryScript(
                intro=intro,
                segments=segments,
                outro=outro,
                total_segments=len(segments),
                estimated_total_duration=result_json.get("estimated_total_speech_duration", 0.0)
            )

        except Exception as e:
            logger.error(f"Commentary generation failed: {e}")
            raise ScriptGenerationError(f"Failed to generate commentary: {e}") from e

    @log_duration(msg_template="Meme script generation {func_name}")
    async def generate_meme_script(
        self,
        remix_script: RemixScript,
        assets_dir: str
    ) -> list[MemePlacement]:
        """Sử dụng LLM để gợi ý vị trí đặt memes."""
        if not os.path.exists(assets_dir):
            logger.warning(f"Meme assets directory not found: {assets_dir}")
            return []

        # 1. Quét danh sách memes có sẵn
        sounds = []
        images = []
        
        sound_dir = os.path.join(assets_dir, "sounds")
        image_dir = os.path.join(assets_dir, "images")
        
        if os.path.exists(sound_dir):
            for d in os.listdir(sound_dir):
                if os.path.isdir(os.path.join(sound_dir, d)):
                    sounds.append(f"{d}: {os.listdir(os.path.join(sound_dir, d))[:5]}")
        
        if os.path.exists(image_dir):
            for d in os.listdir(image_dir):
                if os.path.isdir(os.path.join(image_dir, d)):
                    images.append(f"{d}: {os.listdir(os.path.join(image_dir, d))[:5]}")

        segments_desc = []
        curr_time = 0.0
        for i, step in enumerate(remix_script.sequence):
            # Kết hợp bối cảnh hình ảnh để AI đặt meme chuẩn xác hơn
            visual = f" [Visual: {step.visual_description}]" if step.visual_description else ""
            segments_desc.append(f"Clip {i+1} [{curr_time:.1f}s]: {step.notes}{visual}")
            curr_time += step.duration

        prompt = self._prompt_manager.get(
            "meme_placement",
            segments_description="\n".join(segments_desc),
            available_sounds=", ".join(sounds),
            available_images=", ".join(images),
            max_memes=str(self._config.meme_effects.max_memes_per_video)
        )

        try:
            result_json = await generate_with_retry(self._llm, prompt)
            
            placements = []
            for p in result_json.get("meme_placements", []):
                m_type = p.get("type", "sound")
                
                # Tìm đường dẫn thực tế (giả định)
                s_path, i_path = None, None
                
                if m_type in ["sound", "both"]:
                    s_path = os.path.join(sound_dir, p.get("asset_category", ""), p.get("asset_name", "") + ".mp3")
                if m_type in ["image", "both"]:
                    i_path = os.path.join(image_dir, p.get("asset_category", ""), p.get("asset_name", "") + ".png")

                placements.append(MemePlacement(
                    time=p.get("time", 0.0),
                    type=MemeType.SOUND if m_type == "sound" else MemeType.IMAGE if m_type == "image" else MemeType.BOTH,
                    sound_path=s_path,
                    image_path=i_path,
                    position=p.get("position", "bottom_right"),
                    duration=p.get("duration", 2.0),
                    volume=p.get("volume", 0.7),
                    size_ratio=p.get("size_ratio", 0.25),
                    reason=p.get("reason", "")
                ))
            
            return placements
        except Exception as e:
            logger.error(f"Meme script generation failed: {e}")
            return []

