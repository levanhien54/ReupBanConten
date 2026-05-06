from __future__ import annotations

from src.core.logging import get_logger
from src.core.types import RemixScript
from src.llm.provider import LLMProvider

logger = get_logger(__name__)


class ScriptEngine:
    """AI director for topic-based remix scripts."""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def generate_viral_script(
        self,
        topic: str,
        target_duration: float = 60.0,
        commentary_language: str = "vi",
    ) -> RemixScript:
        """Generate a remix script and force commentary into the selected language."""
        language_name = _language_name(commentary_language)
        prompt = f"""
You are a viral short-form video creative director.
Create a remix script for the topic: "{topic}".

Required structure:
1. HOOK (0-5s): immediately grab attention with a strong visual or line.
2. MEAT (5-55s): keep fast pacing; each clip should be under 3 seconds.
3. CTA (55-60s): short like/subscribe/follow call to action.

Describe the needed visual for every segment so the system can search the clip
library. Also write the voiceover/subtitle line in the field "commentary_text".

Language requirement:
- title must be written in {language_name}
- description must be written in {language_name}
- every commentary_text must be written in {language_name}
- do not mix another language except proper names, brand names, or unavoidable sports terms

Return valid JSON:
{{
  "title": "...",
  "description": "...",
  "estimated_duration": {target_duration},
  "sequence": [
    {{
      "segment": "hook",
      "visual_description": "visual to search for",
      "commentary_text": "voiceover line in {language_name}",
      "duration": 2.0,
      "notes": "reason"
    }}
  ]
}}
"""

        logger.info(f"Generating viral script for topic: {topic}")
        try:
            script_data = await self.llm.generate_json(prompt)
            return RemixScript.model_validate(script_data)
        except Exception as e:
            logger.error(f"AI script generation failed: {e}")
            raise


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
