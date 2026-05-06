"""Helpers for building combat pipeline CLI commands from UI state."""
from __future__ import annotations

import sys


def build_combat_cut_command(
    *,
    input_path: str,
    transcript_path: str = "",
    output_dir: str = "",
    top: int = 10,
    language: str = "vi",
    vertical_mode: str = "blur",
    write_commentary: bool = True,
    run_whisper: bool = False,
    transcript_only: bool = False,
    use_api: bool = False,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "combat-cut",
        "--input",
        input_path,
        "--top",
        str(top),
        "--commentary-language",
        language,
        "--vertical-mode",
        vertical_mode,
    ]
    if transcript_path:
        cmd.extend(["--transcript", transcript_path])
    if output_dir:
        cmd.extend(["--output-dir", output_dir])
    if write_commentary:
        cmd.append("--write-commentary")
    if run_whisper:
        cmd.append("--run-whisper")
    if transcript_only:
        cmd.append("--transcript-only")
    if use_api:
        cmd.append("--use-api")
    return cmd
