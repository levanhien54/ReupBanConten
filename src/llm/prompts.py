"""
Prompt Manager — Load, cache, và format prompt templates.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class PromptManager:
    """
    Quản lý prompt templates từ file.

    Usage:
        pm = PromptManager("config/prompts")
        prompt = pm.get("analyze_content", transcript="...", title="...")
    """

    def __init__(self, prompts_dir: str = "config/prompts") -> None:
        self._prompts_dir = Path(prompts_dir)
        self._cache: dict[str, str] = {}

        if not self._prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {prompts_dir}")

    def get(self, name: str, **kwargs: str) -> str:
        """
        Load và format prompt template.

        Args:
            name: Tên template (không cần .txt)
            **kwargs: Variables để format vào template

        Returns:
            Formatted prompt string
        """
        template = self._load_template(name)

        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing variable in prompt '{name}': {e}")
                raise ValueError(
                    f"Missing variable {e} in prompt template '{name}'"
                ) from e

        return template

    def _load_template(self, name: str) -> str:
        """Load template từ file, với cache."""
        if name not in self._cache:
            path = self._prompts_dir / f"{name}.txt"
            if not path.exists():
                raise FileNotFoundError(f"Prompt template not found: {path}")

            self._cache[name] = path.read_text(encoding="utf-8")
            logger.debug(f"Loaded prompt template: {name}")

        return self._cache[name]

    def list_templates(self) -> list[str]:
        """Liệt kê tất cả templates."""
        if not self._prompts_dir.exists():
            return []
        return [
            f.stem for f in self._prompts_dir.glob("*.txt")
        ]

    def clear_cache(self) -> None:
        """Xóa cache (reload templates)."""
        self._cache.clear()
