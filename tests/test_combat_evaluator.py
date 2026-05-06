from __future__ import annotations

import json
import subprocess

from src.analyzer.combat_evaluator import CombatEvaluator, probe_video
from src.core.config import AppConfig
from src.core.types import TranscriptResult, TranscriptSegment


def test_probe_video_reads_ffprobe_metadata(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    def fake_run(cmd, capture_output, check, text):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "format": {"duration": "2.500"},
                    "streams": [
                        {"codec_type": "video", "width": 1280, "height": 720},
                        {"codec_type": "audio"},
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    probe = probe_video(str(video))

    assert probe.valid is True
    assert probe.duration == 2.5
    assert probe.width == 1280
    assert probe.height == 720
    assert probe.has_audio is True


def test_combat_evaluator_reports_ranking_and_output_validity(tmp_path, monkeypatch):
    source = tmp_path / "fight.mp4"
    source.write_bytes(b"source")
    output_dir = tmp_path / "clips"
    output_dir.mkdir()
    (output_dir / "fight_clip.mp4").write_bytes(b"clip")

    def fake_run(cmd, capture_output, check, text):
        width = 1920 if str(cmd[-1]).endswith("fight.mp4") else 1080
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "format": {"duration": "10.000"},
                    "streams": [
                        {"codec_type": "video", "width": width, "height": 1080},
                        {"codec_type": "audio"},
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    transcript = TranscriptResult(
        full_text="",
        segments=[
            TranscriptSegment(start=4.0, end=5.0, text="Huge knockout and the crowd erupts!"),
        ],
    )

    report = CombatEvaluator(AppConfig()).evaluate(
        input_path=str(source),
        transcript=transcript,
        output_dir=str(output_dir),
        top_k=5,
        transcript_only=True,
    )

    assert report["ranking"]["highlight_count"] == 1
    assert report["ranking"]["top_score"] >= 0.72
    assert report["outputs"]["clip_count"] == 1
    assert report["outputs"]["valid_clip_count"] == 1
    assert report["quality_estimate"]["needs_human_review"] is True
