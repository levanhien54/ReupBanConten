"""
ReupBanConten â€” Entry Point.

Usage:
    python -m src.main --help
    python -m src.main scan --channel "https://youtube.com/@example"
    python -m src.main pipeline --channel "https://youtube.com/@example" --auto
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import click
from typing import Optional

from src.core.config import load_config, AppConfig
from src.core.logging import setup_logging, get_logger
from src.core.database import get_database
from src.core.events import get_event_bus, EventType

logger = get_logger(__name__)


def _configure_console_encoding() -> None:
    """Make Click help output safe on Windows consoles with legacy code pages."""
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            if stream.__class__.__module__.startswith("click."):
                continue
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


_configure_console_encoding()


def _bootstrap() -> AppConfig:
    """Initialize all core systems."""
    _configure_console_encoding()

    config = load_config()
    setup_logging(
        level=config.log_level,
        log_dir=config.storage.logs,
    )
    get_database(config.database.path)
    logger.info(
        f"đŸ¬ {config.name} v{config.version} started",
        extra={"phase": "startup"},
    )
    return config


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  CLI Commands
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@click.group()
@click.version_option(version="0.1.0", prog_name="ReupBanConten")
def cli() -> None:
    """đŸ¬ ReupBanConten â€” AI Video Remix Engine"""
    pass


@cli.command()
def init() -> None:
    """Khá»Ÿi táº¡o project: táº¡o thÆ° má»¥c, database, kiá»ƒm tra dependencies."""
    config = _bootstrap()
    click.echo("âœ… Database initialized")
    click.echo("âœ… Directories created")
    click.echo(f"đŸ“ Data dir: {config.storage.base_dir}")
    click.echo(f"đŸ—„ï¸  Database: {config.database.path}")

    # Download Meme Starter Pack
    if config.meme_effects.auto_download_starter:
        from src.remixer.meme_downloader import MemeDownloader
        downloader = MemeDownloader(config.meme_effects.assets_dir)
        downloader.download_starter_pack()

    # Check dependencies
    deps = _check_dependencies()
    for name, status in deps.items():
        icon = "âœ…" if status else "âŒ"
        click.echo(f"{icon} {name}")


@cli.command()
@click.option("--channel", "-c", required=True, help="URL kĂªnh YouTube")
@click.option("--max-videos", "-n", default=20, help="Sá»‘ video tá»‘i Ä‘a")
@click.option("--shorts-only", is_flag=True, default=True, help="Chá»‰ láº¥y shorts")
def scan(channel: str, max_videos: int, shorts_only: bool) -> None:
    """QuĂ©t kĂªnh YouTube, láº¥y danh sĂ¡ch video."""
    config = _bootstrap()
    click.echo(f"đŸ” Scanning channel: {channel}")
    click.echo(f"   Max videos: {max_videos}, Shorts only: {shorts_only}")

    from src.downloader.channel_scanner import ChannelScanner

    scanner = ChannelScanner(config.downloader)
    videos = scanner.scan(channel, max_count=max_videos, shorts_only=shorts_only)

    click.echo(f"\nâœ… Found {len(videos)} videos")
    for v in videos[:10]:
        dur = f"{v.duration:.0f}s" if v.duration else "?"
        views = f"{v.view_count:,}" if v.view_count else "?"
        click.echo(f"   đŸ“¹ [{dur}] {v.title} ({views} views)")

    if len(videos) > 10:
        click.echo(f"   ... and {len(videos) - 10} more")


@cli.command()
@click.option("--input", "-i", "input_path", required=True, help="ÄÆ°á»ng dáº«n video gá»‘c")
@click.option("--skip-duplicate", is_flag=True, default=True, help="Bá» qua náº¿u video Ä‘Ă£ tá»“n táº¡i (hash check)")
def preprocess(input_path: str, skip_duplicate: bool) -> None:
    """Tiá»n xá»­ lĂ½ video: chuáº©n hĂ³a, Ä‘á»‹nh danh, cáº¯t thĂ´."""
    config = _bootstrap()
    from src.preprocessor import VideoHasher, VideoNormalizer, PreCutter
    from src.core.database import get_database, VideoRepository
    
    click.echo(f"đŸ”„ Processing: {input_path}")
    
    # 1. Äá»‹nh danh (Hash)
    hasher = VideoHasher()
    try:
        file_hash = hasher.generate_hash(input_path)
    except Exception as e:
        click.secho(f"âŒ Error hashing: {e}", fg="red")
        return

    # 2. Check Database
    db = get_database()
    repo = VideoRepository(db)
    existing = repo.get_by_hash(file_hash)
    
    if existing and skip_duplicate:
        click.secho(f"â­ï¸  Video already processed (Hash: {file_hash}). Skipping.", fg="yellow")
        return

    # 3. Chuáº©n hĂ³a (Normalize)
    normalizer = VideoNormalizer(config.storage.cache)
    try:
        normalized_path = normalizer.normalize(
            input_path, 
            resolution=config.preprocessor.resolution,
            fps=config.preprocessor.fps
        )
        click.echo(f"âœ… Normalized: {normalized_path}")
    except Exception as e:
        click.secho(f"âŒ Normalization failed: {e}", fg="red")
        return

    # 4. Smart Pre-cut
    pre_cutter = PreCutter(config.storage.cache)
    pre_cutter.remove_junk(normalized_path)
    
    click.secho(f"âœ¨ Preprocessing complete for {file_hash}", fg="green")


@cli.command()
@click.option("--url", "-u", required=True, help="URL video YouTube")
@click.option("--folder", "-f", help="ThÆ° má»¥c lÆ°u trá»¯")
def download(url: str, folder: Optional[str]) -> None:
    """Táº£i video tá»« YouTube."""
    config = _bootstrap()
    from src.downloader.download_manager import DownloadManager
    
    click.echo(f"đŸ“¥ Downloading: {url}")
    manager = DownloadManager(config.downloader)
    
    output_dir = folder or config.storage.downloads
    video = manager.download_video(url, output_dir)
    
    if video:
        click.secho(f"âœ… Downloaded: {video.metadata.title}", fg="green")
        click.echo(f"   Path: {video.file_path}")
    else:
        click.secho("âŒ Download failed", fg="red")


@cli.command("combat-cut")
@click.option("--input", "-i", "input_path", required=True, help="Video input path")
@click.option("--video-id", "-v", help="Stable video id for output names and DB rows")
@click.option("--transcript", "-t", "transcript_path", help="Transcript JSON cache path")
@click.option("--top", default=10, show_default=True, help="Number of highlights to export")
@click.option("--output-dir", "-o", help="Output directory for combat highlight clips")
@click.option("--run-whisper", is_flag=True, help="Run Whisper if transcript cache is missing")
@click.option("--transcript-only", is_flag=True, help="Only use transcript signals")
@click.option("--use-api", is_flag=True, help="Merge Twelve Labs semantic matches into ranking")
@click.option("--index-id", help="Twelve Labs index id/name for semantic combat search")
@click.option("--api-query", help="Semantic query for combat highlights")
@click.option("--api-limit", default=20, show_default=True, help="Maximum semantic API matches")
@click.option("--write-commentary", is_flag=True, help="Write evidence-based commentary JSON and ASS subtitles")
@click.option("--commentary-language", default="vi", show_default=True, help="Language code for generated commentary/subtitles")
@click.option(
    "--vertical-mode",
    type=click.Choice(["blur", "copy"]),
    default="blur",
    show_default=True,
    help="Export format: blur creates 1080x1920 with blurred background; copy keeps source format",
)
@click.option("--dry-run", is_flag=True, help="Rank highlights without exporting clips")
def combat_cut(
    input_path: str,
    video_id: Optional[str],
    transcript_path: Optional[str],
    top: int,
    output_dir: Optional[str],
    run_whisper: bool,
    transcript_only: bool,
    use_api: bool,
    index_id: Optional[str],
    api_query: Optional[str],
    api_limit: int,
    write_commentary: bool,
    commentary_language: str,
    vertical_mode: str,
    dry_run: bool,
) -> None:
    """Rank and cut hook-focused combat-sports highlights."""
    config = _bootstrap()
    if not os.path.exists(input_path):
        click.secho(f"Input file not found: {input_path}", fg="red")
        return

    from src.analyzer.combat_sports import CombatSportsAnalyzer
    from src.core.database import ClipRepository
    from src.cutter.smart_clipper import SmartClipper
    from src.remixer.vertical_video import build_vertical_filter

    resolved_video_id = video_id or _safe_video_id(input_path)
    transcript = _load_transcript_for_combat_cut(
        config=config,
        input_path=input_path,
        video_id=resolved_video_id,
        transcript_path=transcript_path,
        run_whisper=run_whisper,
    )

    analyzer = CombatSportsAnalyzer(config.combat_sports)
    api_results = []
    if use_api:
        api_results = _search_combat_api(
            analyzer=analyzer,
            config=config,
            index_id=index_id,
            query=api_query,
            limit=api_limit,
        )
        click.echo(f"API semantic matches: {len(api_results)}")

    highlights = analyzer.analyze(
        video_path=None if transcript_only else input_path,
        transcript=transcript,
        api_results=api_results,
        top_k=top,
    )
    if not highlights:
        click.secho("No combat highlights passed the score threshold.", fg="yellow")
        return

    click.echo(f"Found {len(highlights)} combat highlights:")
    for idx, highlight in enumerate(highlights, start=1):
        click.echo(
            f"  {idx:02d}. score={highlight.score:.2f} "
            f"{highlight.start_time:.2f}s-{highlight.end_time:.2f}s "
            f"hook={highlight.hook_time:.2f}s "
            f"reasons={', '.join(highlight.reasons[:3])}"
        )

    if dry_run:
        return

    clipper = SmartClipper(config.cutter)
    clip_repo = ClipRepository(get_database())
    destination = output_dir or os.path.join(config.storage.clips, "combat")
    vertical_filter = build_vertical_filter(vertical_mode, width=1080, height=1920)
    click.echo(f"Vertical export mode: {vertical_mode}")
    commentary_script = None
    if write_commentary:
        commentary_script = asyncio.run(
            _build_combat_commentary(
                highlights=highlights,
                transcript=transcript,
                language=commentary_language,
            )
        )
    exported = 0
    for idx, highlight in enumerate(highlights, start=1):
        clip = clipper.export_clip(
            video_id=f"{resolved_video_id}_combat_{idx:02d}",
            video_path=input_path,
            start_time=highlight.start_time,
            end_time=highlight.end_time,
            output_dir=destination,
            video_filter=vertical_filter,
        )
        clip_id = clip_repo.insert(
            video_id=resolved_video_id,
            file_path=clip.file_path,
            start_time=clip.start_time,
            end_time=clip.end_time,
            duration=clip.duration,
            tags_json=json.dumps(["combat", *sorted(_highlight_tags(highlight))], ensure_ascii=False),
            mood="exciting",
            energy_level="high" if highlight.score < 0.9 else "peak",
            content_type="action",
            highlight_score=highlight.score,
            transcript_segment="; ".join(highlight.reasons),
            source_folder="combat",
        )
        exported += 1
        if commentary_script:
            _write_combat_commentary_assets(
                config=config,
                clip_path=clip.file_path,
                highlight=highlight,
                commentary_segment=commentary_script.segments[idx - 1],
                transcript=transcript,
            )
        click.echo(f"  Exported clip #{clip_id}: {clip.file_path}")

    click.secho(f"Exported {exported} combat highlight clips to {destination}", fg="green")


@cli.command("combat-index")
@click.option("--input", "-i", "input_path", required=True, help="Video input path")
@click.option("--index-id", help="Twelve Labs index id/name to upload into")
def combat_index(input_path: str, index_id: Optional[str]) -> None:
    """Upload a combat-sports video into the semantic video index."""
    config = _bootstrap()
    if not os.path.exists(input_path):
        click.secho(f"Input file not found: {input_path}", fg="red")
        return

    from src.analyzer.twelve_labs_client import TwelveLabsClient

    tl_client = TwelveLabsClient()
    if not tl_client.is_available():
        click.secho("Twelve Labs is unavailable. Set TWELVELABS_API_KEY and install twelvelabs.", fg="yellow")
        return

    resolved_index_id = index_id or config.analyzer.twelve_labs.index_name
    try:
        video_api_id = asyncio.run(tl_client.upload_video(resolved_index_id, input_path))
    except Exception as exc:
        click.secho(f"Combat index upload failed: {exc}", fg="red")
        return

    click.secho(f"Indexed video. Twelve Labs video_id: {video_api_id}", fg="green")


@cli.command("combat-search-api")
@click.option("--index-id", help="Twelve Labs index id/name to search")
@click.option("--query", "-q", help="Semantic query for combat highlights")
@click.option("--limit", default=20, show_default=True, help="Maximum results")
def combat_search_api(index_id: Optional[str], query: Optional[str], limit: int) -> None:
    """Search the semantic video API for combat-sports highlight moments."""
    config = _bootstrap()
    from src.analyzer.combat_sports import CombatSportsAnalyzer

    analyzer = CombatSportsAnalyzer(config.combat_sports)
    results = _search_combat_api(
        analyzer=analyzer,
        config=config,
        index_id=index_id,
        query=query,
        limit=limit,
    )

    if not results:
        click.secho("No semantic API matches found.", fg="yellow")
        return

    click.echo(f"Found {len(results)} semantic API matches:")
    for idx, result in enumerate(results, start=1):
        start = float(result.get("start", 0.0) or 0.0)
        end = float(result.get("end", start) or start)
        confidence = result.get("confidence", result.get("score", 0.0))
        video_api_id = result.get("video_id", "")
        click.echo(
            f"  {idx:02d}. confidence={float(confidence or 0.0):.2f} "
            f"{start:.2f}s-{end:.2f}s video_id={video_api_id}"
        )


@cli.command("combat-evaluate")
@click.option("--input", "-i", "input_path", required=True, help="Video input path")
@click.option("--transcript", "-t", "transcript_path", help="Transcript JSON cache path")
@click.option("--output-dir", "-o", help="Directory containing exported combat clips")
@click.option("--report", "report_path", help="JSON report path")
@click.option("--top", default=10, show_default=True, help="Number of highlights to rank")
@click.option("--transcript-only", is_flag=True, help="Only use transcript signals")
@click.option("--use-api", is_flag=True, help="Merge Twelve Labs semantic matches into ranking")
@click.option("--index-id", help="Twelve Labs index id/name for semantic combat search")
@click.option("--api-query", help="Semantic query for combat highlights")
@click.option("--api-limit", default=20, show_default=True, help="Maximum semantic API matches")
def combat_evaluate(
    input_path: str,
    transcript_path: Optional[str],
    output_dir: Optional[str],
    report_path: Optional[str],
    top: int,
    transcript_only: bool,
    use_api: bool,
    index_id: Optional[str],
    api_query: Optional[str],
    api_limit: int,
) -> None:
    """Measure combat highlight ranking speed and exported clip validity."""
    config = _bootstrap()
    if not os.path.exists(input_path):
        click.secho(f"Input file not found: {input_path}", fg="red")
        return

    from src.analyzer.combat_evaluator import CombatEvaluator, write_report
    from src.analyzer.combat_sports import CombatSportsAnalyzer

    resolved_video_id = _safe_video_id(input_path)
    transcript = _load_transcript_for_combat_cut(
        config=config,
        input_path=input_path,
        video_id=resolved_video_id,
        transcript_path=transcript_path,
        run_whisper=False,
    )

    api_results = []
    if use_api:
        analyzer = CombatSportsAnalyzer(config.combat_sports)
        api_results = _search_combat_api(
            analyzer=analyzer,
            config=config,
            index_id=index_id,
            query=api_query,
            limit=api_limit,
        )

    evaluator = CombatEvaluator(config)
    report = evaluator.evaluate(
        input_path=input_path,
        transcript=transcript,
        api_results=api_results,
        output_dir=output_dir,
        top_k=top,
        transcript_only=transcript_only,
    )

    destination = report_path or os.path.join(config.storage.logs, f"{resolved_video_id}_combat_eval.json")
    write_report(report, destination)
    ranking = report["ranking"]
    outputs = report["outputs"]
    quality = report["quality_estimate"]
    click.echo(f"Ranking time: {ranking['seconds']:.3f}s")
    click.echo(f"Speed: {ranking['video_seconds_per_processing_second']} video seconds / processing second")
    click.echo(f"Highlights: {ranking['highlight_count']} top_score={ranking['top_score']:.2f}")
    click.echo(
        f"Output clips: {outputs['valid_clip_count']}/{outputs['clip_count']} valid "
        f"avg_duration={outputs['avg_clip_duration']:.2f}s"
    )
    click.echo(
        f"Quality estimate: hook={quality['hook_strength_estimate']:.2f}/5 "
        f"validity={quality['output_validity']:.2f}/5 "
        f"duplicates={quality['duplicate_control_estimate']:.2f}/5"
    )
    click.secho(f"Report saved: {destination}", fg="green")


@cli.command()
@click.option("--video-id", "-v", required=True, help="ID video trong database")
@click.option("--index", is_flag=True, default=True, help="Äáº©y video lĂªn Twelve Labs Index")
def analyze(video_id: str, index: bool) -> None:
    """PhĂ¢n tĂ­ch ná»™i dung video báº±ng AI (Twelve Labs + Whisper)."""
    config = _bootstrap()
    from src.core.database import get_database, VideoRepository
    from src.analyzer.twelve_labs_client import TwelveLabsClient
    from src.analyzer.transcriber import Transcriber

    repo = VideoRepository(get_database())
    video = repo.get_by_video_id(video_id)
    if not video or not video["file_path"]:
        click.secho(f"âŒ Video {video_id} khĂ´ng tá»“n táº¡i hoáº·c chÆ°a táº£i vá».", fg="red")
        return

    async def _run_analysis():
        click.echo(f"đŸ§  Äang phĂ¢n tĂ­ch video: {video['title']}")
        
        # 1. Twelve Labs Indexing
        if index:
            tl = TwelveLabsClient()
            if tl.is_available():
                click.echo("đŸ“¤ Äang Ä‘áº©y video lĂªn Twelve Labs...")
                tl_vid_id = await tl.upload_video(config.analyzer.twelve_labs.index_name, video["file_path"])
                summary = await tl.generate_summary(tl_vid_id)
                click.echo(f"âœ… Twelve Labs Indexing hoĂ n táº¥t. TĂ³m táº¯t: {summary[:100]}...")
            else:
                click.secho("â ï¸ Twelve Labs API Key khĂ´ng kháº£ dá»¥ng. Bá» qua bÆ°á»›c nĂ y.", fg="yellow")

        # 2. Transcribe
        click.echo("đŸ™ï¸ Äang chuyá»ƒn Ä‘á»•i giá»ng nĂ³i thĂ nh vÄƒn báº£n...")
        transcriber = Transcriber(config.analyzer.whisper, output_dir=config.storage.transcripts)
        transcript = transcriber.transcribe_with_cache(video["file_path"], video_id)
        click.echo(f"âœ… Transcription hoĂ n táº¥t. ({len(transcript.segments)} segments)")

    asyncio.run(_run_analysis())
    click.secho(f"âœ¨ PhĂ¢n tĂ­ch xong video {video_id}", fg="green")


@cli.command()
@click.option("--topic", "-t", required=True, help="Chá»§ Ä‘á» video muá»‘n táº¡o")
@click.option("--duration", "-d", default=60, help="Thá»i lÆ°á»£ng má»¥c tiĂªu (giĂ¢y)")
@click.option("--output", "-o", default="remix_v2.mp4", help="TĂªn file Ä‘áº§u ra")
def remix(topic: str, duration: int, output: str) -> None:
    """đŸ¬ Táº¡o video Remix v2.0 báº±ng AI Director (RAG)."""
    config = _bootstrap()
    from src.remixer.orchestrator_v2 import RemixOrchestratorV2
    
    click.echo(f"đŸ€ Äang khá»Ÿi táº¡o AI Director cho chá»§ Ä‘á»: {topic}")
    orchestrator = RemixOrchestratorV2(config)
    
    async def _run_remix():
        output_path = await orchestrator.create_remix(topic, output_name=output)
        return output_path

    output_path = asyncio.run(_run_remix())
    click.secho(f"âœ¨ Remix thĂ nh cĂ´ng! Video lÆ°u táº¡i: {output_path}", fg="green")


@cli.command()
@click.option("--channel", "-c", required=True, help="URL kĂªnh YouTube")
@click.option("--max-videos", "-n", default=10, help="Sá»‘ video tá»‘i Ä‘a")
@click.option("--strategy", "-s", default="energy-flow", help="Remix strategy")
@click.option("--duration", "-d", default=60, help="Target duration (seconds)")
@click.option("--add-memes", is_flag=True, default=True, help="Add meme effects")
@click.option("--add-voiceover", is_flag=True, default=True, help="Add voiceover")
def pipeline(
    channel: str,
    max_videos: int,
    strategy: str,
    duration: int,
    add_memes: bool,
    add_voiceover: bool,
) -> None:
    """đŸ€ Full pipeline: scan â†’ download â†’ analyze â†’ cut â†’ remix."""
    config = _bootstrap()
    from src.downloader.channel_scanner import ChannelScanner
    from src.downloader.download_manager import DownloadManager

    click.echo("=" * 60)
    click.echo("đŸ¬ REUPBANCONTEN â€” FULL PIPELINE")
    click.echo("=" * 60)
    click.echo(f"Channel:   {channel}")
    click.echo(f"Videos:    {max_videos}")
    click.echo(f"Strategy:  {strategy}")
    click.echo(f"Duration:  {duration}s")
    click.echo(f"Memes:     {add_memes}")
    click.echo(f"Voiceover: {add_voiceover}")
    click.echo("=" * 60)

    config.voiceover.enabled = add_voiceover
    config.meme_effects.enabled = add_memes

    scanner = ChannelScanner(config.downloader)
    videos = scanner.scan(
        channel,
        max_count=max_videos,
        shorts_only=config.downloader.filter_shorts_only,
    )
    if not videos:
        click.secho("No videos found.", fg="red")
        return

    click.echo(f"Scan complete: {len(videos)} videos")
    manager = DownloadManager(config.downloader)
    result = manager.download_batch([v.url for v in videos], config.storage.downloads)
    click.echo(f"Download complete: {result.success}/{result.total}")

    if result.failed:
        click.secho("Some downloads failed:", fg="yellow")
        for err in result.errors[:5]:
            click.echo(f"   - {err.video_id}: {err.error_code} {err.error_msg}")

    if result.success == 0:
        click.secho("Pipeline stopped because no videos were downloaded.", fg="red")
        return

    click.echo(
        "Downloaded files are ready. Next: preprocess/analyze/cut selected files, "
        "then run remix or use the UI for assisted review."
    )


@cli.command()
def status() -> None:
    """Hiá»ƒn thá»‹ tráº¡ng thĂ¡i hiá»‡n táº¡i cá»§a project."""
    config = _bootstrap()
    db = get_database()

    video_count = db.fetch_one("SELECT COUNT(*) as c FROM videos")
    clip_count = db.fetch_one("SELECT COUNT(*) as c FROM clips")
    remix_count = db.fetch_one("SELECT COUNT(*) as c FROM remix_projects")

    click.echo("đŸ“ Project Status:")
    click.echo(f"   Videos:  {video_count['c'] if video_count else 0}")
    click.echo(f"   Clips:   {clip_count['c'] if clip_count else 0}")
    click.echo(f"   Remixes: {remix_count['c'] if remix_count else 0}")


@cli.command()
def ui() -> None:
    """đŸ–¥ï¸ Khá»Ÿi cháº¡y giao diá»‡n Ä‘á»“ há»a (GUI)."""
    config = _bootstrap()
    
    try:
        from src.ui.app import launch_ui
        launch_ui(config)
    except ImportError as e:
        click.secho(
            f"âŒ KhĂ´ng thá»ƒ khá»Ÿi cháº¡y UI. Lá»—i thÆ° viá»‡n: {e}\n"
            "HĂ£y cháº¡y: pip install PySide6 qdarktheme",
            fg="red"
        )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _check_dependencies() -> dict[str, bool]:
    """Kiá»ƒm tra dependencies Ä‘Ă£ cĂ i Ä‘áº·t."""
    deps = {}

    # FFmpeg
    import shutil
    deps["FFmpeg"] = shutil.which("ffmpeg") is not None

    # Python packages
    for pkg in ["yt_dlp", "moviepy", "faster_whisper", "ollama", "click", "pydantic"]:
        try:
            __import__(pkg)
            deps[pkg] = True
        except ImportError:
            deps[pkg] = False

    return deps


def _safe_video_id(input_path: str) -> str:
    """Create a DB/output-safe id from a local filename."""
    stem = os.path.splitext(os.path.basename(input_path))[0]
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)
    return safe[:80] or "combat_video"


def _load_transcript_for_combat_cut(
    *,
    config: AppConfig,
    input_path: str,
    video_id: str,
    transcript_path: Optional[str],
    run_whisper: bool,
):
    """Load transcript JSON, optionally generating it via Whisper."""
    from src.core.types import TranscriptResult

    candidates = []
    if transcript_path:
        candidates.append(transcript_path)
    candidates.append(os.path.join(config.storage.transcripts, f"{video_id}.json"))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return TranscriptResult.model_validate_json(f.read())

    if not run_whisper:
        return None

    from src.analyzer.transcriber import Transcriber

    transcriber = Transcriber(config.analyzer.whisper, output_dir=config.storage.transcripts)
    return transcriber.transcribe_with_cache(input_path, video_id)


def _search_combat_api(
    *,
    analyzer,
    config: AppConfig,
    index_id: Optional[str],
    query: Optional[str],
    limit: int,
) -> list[dict]:
    from src.analyzer.twelve_labs_client import TwelveLabsClient

    tl_client = TwelveLabsClient()
    if not tl_client.is_available():
        click.secho("Twelve Labs is unavailable; continuing with local signals only.", fg="yellow")
        return []

    resolved_index_id = index_id or config.analyzer.twelve_labs.index_name
    if not resolved_index_id:
        click.secho("Missing Twelve Labs index id/name; continuing with local signals only.", fg="yellow")
        return []

    try:
        return asyncio.run(
            analyzer.search_api(
                tl_client,
                resolved_index_id,
                query=query,
                limit=max(1, limit),
            )
        )
    except Exception as exc:
        click.secho(f"Semantic API search failed; continuing locally: {exc}", fg="yellow")
        return []


async def _build_combat_commentary(*, highlights, transcript, language: str = "vi"):
    from src.remixer.combat_commentary import CombatCommentaryGenerator

    generator = CombatCommentaryGenerator()
    return await generator.generate_script(
        highlights,
        transcript=transcript,
        sport="combat",
        language=language,
    )


def _write_combat_commentary_assets(
    *,
    config: AppConfig,
    clip_path: str,
    highlight,
    commentary_segment,
    transcript,
) -> None:
    from src.core.types import CommentaryScript
    from src.remixer.ass_generator import ASSGenerator
    from src.remixer.combat_commentary import build_evidence_packet

    base_path = os.path.splitext(clip_path)[0]
    packet = build_evidence_packet(highlight, transcript=transcript, sport="combat")
    payload = {
        "clip_path": clip_path,
        "highlight": highlight.model_dump(),
        "commentary": commentary_segment.model_dump(),
        "evidence": packet.__dict__,
    }
    json_path = base_path + ".commentary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    ass_path = base_path + ".ass"
    ASSGenerator(config.remixer.effects.subtitles).generate(
        CommentaryScript(segments=[commentary_segment]),
        ass_path,
        width=1080,
        height=1920,
    )
    click.echo(f"  Commentary assets: {json_path}, {ass_path}")


def _highlight_tags(highlight) -> set[str]:
    tags = set()
    for signal in highlight.signals:
        tags.add(signal.kind)
    for reason in highlight.reasons:
        tag = reason.split(":", 1)[0].strip()
        if tag:
            tags.add(tag)
    return tags


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Entry point
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> None:
    cli()


if __name__ == "__main__":
    main()

