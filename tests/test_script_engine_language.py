from __future__ import annotations

import pytest

from src.remixer.script_engine import ScriptEngine


class CapturingLLM:
    def __init__(self):
        self.prompt = ""

    async def generate_json(self, prompt):
        self.prompt = prompt
        return {
            "title": "A short",
            "description": "A description",
            "sequence": [
                {
                    "segment": "hook",
                    "visual_description": "a fast exchange",
                    "commentary_text": "That strike changes everything",
                    "duration": 2.0,
                    "notes": "hook",
                }
            ],
        }


@pytest.mark.asyncio
async def test_script_engine_prompt_forces_selected_commentary_language():
    llm = CapturingLLM()
    engine = ScriptEngine(llm)

    await engine.generate_viral_script("mma hooks", commentary_language="en-GB")

    assert "commentary_text must be written in British English" in llm.prompt
    assert "title must be written in British English" in llm.prompt


@pytest.mark.asyncio
async def test_script_engine_prompt_supports_brazilian_portuguese():
    llm = CapturingLLM()
    engine = ScriptEngine(llm)

    await engine.generate_viral_script("mma hooks", commentary_language="pt-BR")

    assert "commentary_text must be written in Brazilian Portuguese" in llm.prompt
    assert "title must be written in Brazilian Portuguese" in llm.prompt
