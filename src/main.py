"""
ReupBanConten â€” Entry Point.

Usage:
    python -m src.main --help
    python -m src.main scan --channel "https://youtube.com/@example"
    python -m src.main pipeline --channel "https://youtube.com/@example" --auto
"""
from __future__ import annotations

import asyncio
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Entry point
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> None:
    cli()


if __name__ == "__main__":
    main()

