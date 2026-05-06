from __future__ import annotations

import subprocess
import sys

from src.core.types import TranscriptResult, TranscriptSegment


def test_combat_cut_dry_run_uses_transcript_json(tmp_path):
    video = tmp_path / "fight.mp4"
    video.write_bytes(b"not a real video")
    transcript = TranscriptResult(
        full_text="",
        segments=[
            TranscriptSegment(
                start=3.0,
                end=5.0,
                text="Huge head kick and a knockdown!",
            )
        ],
    )
    transcript_path = tmp_path / "fight.json"
    transcript_path.write_text(transcript.model_dump_json(), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "combat-cut",
            "--input",
            str(video),
            "--transcript",
            str(transcript_path),
            "--transcript-only",
            "--dry-run",
        ],
        cwd="D:/ReupBanConten",
        capture_output=True,
        timeout=30,
    )

    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert result.returncode == 0, stderr
    assert "Found 1 combat highlights" in stdout
    assert "score=" in stdout
    assert "impact:keyword" in stdout
