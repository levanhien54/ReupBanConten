from __future__ import annotations

import subprocess
import sys

from src.core.config import AppConfig
from src.core.types import CombatHighlight, CombatSignal, CommentarySegment, TranscriptResult, TranscriptSegment
from src.main import _write_combat_commentary_assets


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


def test_combat_cut_api_fallback_does_not_block_local_ranking(tmp_path, monkeypatch):
    monkeypatch.delenv("TWELVELABS_API_KEY", raising=False)
    video = tmp_path / "fight.mp4"
    video.write_bytes(b"not a real video")
    transcript = TranscriptResult(
        full_text="",
        segments=[
            TranscriptSegment(
                start=8.0,
                end=10.0,
                text="Clean right hand, down goes the fighter!",
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
            "--use-api",
            "--index-id",
            "dummy-index",
            "--dry-run",
        ],
        cwd="D:/ReupBanConten",
        capture_output=True,
        timeout=30,
    )

    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert result.returncode == 0, stderr
    assert "API semantic matches: 0" in stdout
    assert "Found 1 combat highlights" in stdout


def test_write_combat_commentary_assets_creates_json_and_ass(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    highlight = CombatHighlight(
        start_time=4.2,
        hook_time=5.0,
        end_time=7.0,
        score=0.88,
        reasons=["impact:keyword:big shot"],
        signals=[CombatSignal(time=5.0, score=0.9, kind="impact", reason="keyword:big shot")],
    )
    transcript = TranscriptResult(
        full_text="",
        segments=[TranscriptSegment(start=4.6, end=5.2, text="Big shot lands")],
    )
    segment = CommentarySegment(
        text="Cú ra đòn này tạo áp lực ngay lập tức.",
        start_time=0.55,
        duration_estimate=1.4,
        style="impact",
        keywords=["đòn", "áp lực"],
        evidence_used=["impact"],
    )

    _write_combat_commentary_assets(
        config=AppConfig(),
        clip_path=str(clip),
        highlight=highlight,
        commentary_segment=segment,
        transcript=transcript,
    )

    assert (tmp_path / "clip.commentary.json").exists()
    ass = (tmp_path / "clip.ass").read_text(encoding="utf-8")
    assert "Dialogue:" in ass
    assert "PremiumStyle" in ass
