from __future__ import annotations

import json

from src.ui.combat_results import format_combat_output_summary, load_combat_output_summaries


def test_load_combat_output_summaries_reads_probe_metadata(tmp_path):
    payload = {
        "language": "en-US",
        "final_video_ready": True,
        "final_video_path": str(tmp_path / "clip_final.mp4"),
        "clip_path": str(tmp_path / "clip.mp4"),
        "highlight": {"score": 0.91, "start_time": 10.0, "end_time": 18.0, "hook_time": 12.5},
        "commentary": {"text": "A sharp right hand lands clean and changes the pace of the exchange."},
        "final_video_probe": {
            "width": 1080,
            "height": 1920,
            "has_audio": True,
            "duration": 4.2,
        },
    }
    (tmp_path / "clip.commentary.json").write_text(json.dumps(payload), encoding="utf-8")

    summaries = load_combat_output_summaries(str(tmp_path))

    assert len(summaries) == 1
    assert summaries[0].ready is True
    assert summaries[0].score == 0.91
    assert summaries[0].width == 1080
    assert summaries[0].height == 1920
    assert summaries[0].has_audio is True
    assert summaries[0].language == "en-US"
    assert summaries[0].clip_path.endswith("clip.mp4")
    assert summaries[0].hook_time == 12.5
    assert summaries[0].commentary_text.startswith("A sharp right hand")


def test_format_combat_output_summary_is_scannable(tmp_path):
    payload = {
        "language": "pt-BR",
        "final_video_ready": False,
        "final_video_path": "",
        "highlight": {"score": 0.72, "hook_time": 3.25},
        "commentary": {"text": "O golpe entra no momento exato e levanta a intensidade da luta."},
        "final_video_probe": {"width": 0, "height": 0, "has_audio": False, "duration": 0},
    }
    (tmp_path / "clip.commentary.json").write_text(json.dumps(payload), encoding="utf-8")

    text = format_combat_output_summary(load_combat_output_summaries(str(tmp_path)))

    assert "Final videos ready: 0/1" in text
    assert "CHECK score=0.72" in text
    assert "lang=pt-BR" in text
    assert "hook=3.25s" in text
    assert "commentary: O golpe entra" in text
