from __future__ import annotations

import sys

from src.ui.combat_command import build_combat_cut_command


def test_build_combat_cut_command_maps_ui_options_to_cli_flags():
    cmd = build_combat_cut_command(
        input_path="fight.mp4",
        transcript_path="fight.json",
        output_dir="out",
        top=5,
        language="en-US",
        vertical_mode="blur",
        write_commentary=True,
        run_whisper=True,
        transcript_only=False,
        use_api=True,
    )

    assert cmd[:4] == [sys.executable, "-m", "src.main", "combat-cut"]
    assert cmd[cmd.index("--input") + 1] == "fight.mp4"
    assert cmd[cmd.index("--transcript") + 1] == "fight.json"
    assert cmd[cmd.index("--output-dir") + 1] == "out"
    assert cmd[cmd.index("--top") + 1] == "5"
    assert cmd[cmd.index("--commentary-language") + 1] == "en-US"
    assert cmd[cmd.index("--vertical-mode") + 1] == "blur"
    assert "--write-commentary" in cmd
    assert "--run-whisper" in cmd
    assert "--use-api" in cmd
    assert "--transcript-only" not in cmd


def test_build_combat_cut_command_can_skip_commentary_for_fast_export():
    cmd = build_combat_cut_command(
        input_path="fight.mp4",
        vertical_mode="copy",
        write_commentary=False,
    )

    assert cmd[cmd.index("--vertical-mode") + 1] == "copy"
    assert "--write-commentary" not in cmd
