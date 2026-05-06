# Skill 01: YouTube Channel Scanning & Batch Download

## Mục Tiêu
Tải hàng loạt video ngắn từ 1 kênh YouTube với bộ lọc thông minh.

## Kiến Thức Cần Có
- yt-dlp CLI & Python API
- asyncio cho concurrent downloads
- SQLite cho metadata storage

---

## Bước 1: Quét Kênh YouTube

### Lấy danh sách video (flat playlist)
```python
import yt_dlp

def scan_channel(channel_url: str, max_videos: int = 50) -> list[dict]:
    """Quét kênh và trả về danh sách video info."""
    ydl_opts = {
        'extract_flat': True,        # Chỉ lấy metadata, không tải
        'playlistend': max_videos,
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(channel_url, download=False)
        
    videos = []
    for entry in result.get('entries', []):
        videos.append({
            'video_id': entry.get('id'),
            'url': f"https://www.youtube.com/watch?v={entry['id']}",
            'title': entry.get('title'),
            'duration': entry.get('duration'),
            'view_count': entry.get('view_count', 0),
        })
    
    return videos
```

### Lọc video ngắn (Shorts)
```python
def filter_shorts(videos: list[dict], max_duration: int = 180) -> list[dict]:
    """Lọc chỉ video ngắn (< max_duration giây)."""
    return [
        v for v in videos 
        if v.get('duration') and v['duration'] <= max_duration
    ]

def filter_by_views(videos: list[dict], min_views: int = 1000) -> list[dict]:
    """Lọc video có đủ lượt xem."""
    return [
        v for v in videos 
        if v.get('view_count', 0) >= min_views
    ]
```

---

## Bước 2: Tải Video Batch

### Download đơn
```python
def download_video(video_url: str, output_dir: str, quality: str = "720p") -> str:
    """Tải 1 video, trả về đường dẫn file."""
    ydl_opts = {
        'format': f'bestvideo[height<={quality[:-1]}]+bestaudio/best',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        'retries': 3,
        'sleep_interval': 2,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        return ydl.prepare_filename(info)
```

### Download batch (async)
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def batch_download(videos: list[dict], output_dir: str, 
                          max_concurrent: int = 3) -> list[str]:
    """Tải nhiều video song song."""
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    
    async def _download(video):
        async with semaphore:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                path = await loop.run_in_executor(
                    pool, download_video, video['url'], output_dir
                )
                results.append(path)
                print(f"✅ Downloaded: {video['title']}")
    
    tasks = [_download(v) for v in videos]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

---

## Bước 3: Trích Xuất Metadata

```python
def extract_full_metadata(video_url: str) -> dict:
    """Trích metadata đầy đủ từ YouTube."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'writesubtitles': True,
        'subtitleslangs': ['vi', 'en'],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
    
    return {
        'video_id': info.get('id'),
        'title': info.get('title'),
        'description': info.get('description'),
        'duration': info.get('duration'),
        'view_count': info.get('view_count'),
        'like_count': info.get('like_count'),
        'upload_date': info.get('upload_date'),
        'tags': info.get('tags', []),
        'categories': info.get('categories', []),
        'thumbnail': info.get('thumbnail'),
        'channel_name': info.get('channel'),
        'channel_id': info.get('channel_id'),
        'subtitles': info.get('subtitles', {}),
    }
```

---

## Bước 4: Lưu Database

```python
import sqlite3

def save_video_metadata(db_path: str, metadata: dict):
    """Lưu metadata vào SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO videos 
        (video_id, url, title, description, duration, view_count, upload_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'downloaded')
    ''', (
        metadata['video_id'],
        f"https://youtube.com/watch?v={metadata['video_id']}",
        metadata['title'],
        metadata['description'],
        metadata['duration'],
        metadata['view_count'],
        metadata['upload_date'],
    ))
    
    conn.commit()
    conn.close()
```

---

## Xử Lý Lỗi Thường Gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `ERROR: Sign in to confirm` | Video age-restricted | Dùng `--cookies-from-browser` |
| `HTTP Error 429` | Rate limited | Tăng `sleep_interval`, dùng proxy |
| `Video unavailable` | Video bị xóa/private | Skip và log |
| `Unable to download` | yt-dlp outdated | `pip install -U yt-dlp` |

---

## Test

```python
# test_downloader.py
def test_scan_channel():
    videos = scan_channel("https://youtube.com/@example", max_videos=5)
    assert len(videos) > 0
    assert all('video_id' in v for v in videos)

def test_filter_shorts():
    videos = [{'duration': 30}, {'duration': 300}, {'duration': 60}]
    shorts = filter_shorts(videos, max_duration=120)
    assert len(shorts) == 2
```
