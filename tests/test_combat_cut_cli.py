from __future__ import annotations

import subprocess
import sys

from src.core.config import AppConfig
from src.core.types import CombatHighlight, CombatSignal, CommentarySegment, TranscriptResult, TranscriptSegment
from src.main import _mux_combat_commentary_video, _video_has_audio_stream, _write_combat_commentary_assets


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


def test_combat_cut_help_lists_vertical_mode():
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "combat-cut", "--help"],
        cwd="D:/ReupBanConten",
        capture_output=True,
        timeout=30,
    )

    stdout = result.stdout.decode("utf-8", errors="replace")
    assert result.returncode == 0
    assert "--vertical-mode" in stdout
    assert "[blur|copy]" in stdout


def test_write_combat_commentary_assets_creates_json_and_ass(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    config = AppConfig()
    config.voiceover.enabled = False
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
        config=config,
        clip_path=str(clip),
        highlight=highlight,
        commentary_segment=segment,
        transcript=transcript,
        language="en-US",
    )

    assert (tmp_path / "clip.commentary.json").exists()
    ass = (tmp_path / "clip.ass").read_text(encoding="utf-8")
    assert "Dialogue:" in ass
    assert "PremiumStyle" in ass
    payload = (tmp_path / "clip.commentary.json").read_text(encoding="utf-8")
    assert '"language": "en-US"' in payload


def test_mux_combat_commentary_video_creates_final_mp4(tmp_path):
    video_path = tmp_path / "clip.mp4"
    audio_path = tmp_path / "voice.mp3"
    ass_path = tmp_path / "clip.ass"
    output_path = tmp_path / "clip_final.mp4"

    video_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=1080x1920:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=220:sample_rate=44100",
        "-t",
        "1",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(video_path),
    ]
    audio_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=44100",
        "-t",
        "1",
        str(audio_path),
    ]
    if subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5).returncode != 0:
        return
    subprocess.run(video_cmd, capture_output=True, check=True, timeout=60)
    subprocess.run(audio_cmd, capture_output=True, check=True, timeout=60)

    ass_path.write_text(
        """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PremiumStyle,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3,2,2,80,80,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:00.80,PremiumStyle,,0,0,0,,Test subtitle
""",
        encoding="utf-8",
    )

    _mux_combat_commentary_video(
        clip_path=str(video_path),
        ass_path=str(ass_path),
        audio_path=str(audio_path),
        output_path=str(output_path),
    )

    assert output_path.exists()
    assert _video_has_audio_stream(str(output_path))


def test_mux_combat_commentary_video_handles_clip_without_audio(tmp_path):
    video_path = tmp_path / "silent_clip.mp4"
    audio_path = tmp_path / "voice.mp3"
    ass_path = tmp_path / "silent_clip.ass"
    output_path = tmp_path / "silent_clip_final.mp4"

    if subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5).returncode != 0:
        return
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1080x1920:rate=30",
            "-t",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            str(video_path),
        ],
        capture_output=True,
        check=True,
        timeout=60,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=44100",
            "-t",
            "1",
            str(audio_path),
        ],
        capture_output=True,
        check=True,
        timeout=60,
    )
    ass_path.write_text(
        """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PremiumStyle,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3,2,2,80,80,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.20,0:00:00.80,PremiumStyle,,0,0,0,,Delayed subtitle
""",
        encoding="utf-8",
    )

    assert not _video_has_audio_stream(str(video_path))
    _mux_combat_commentary_video(
        clip_path=str(video_path),
        ass_path=str(ass_path),
        audio_path=str(audio_path),
        output_path=str(output_path),
        voice_start=0.2,
    )

    assert output_path.exists()
    assert _video_has_audio_stream(str(output_path))
