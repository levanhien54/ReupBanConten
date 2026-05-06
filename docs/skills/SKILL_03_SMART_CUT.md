# Skill 03: Smart Video Cutting & Scene Detection

## Mục Tiêu
Cắt video thông minh bằng kết hợp PySceneDetect + LLM highlight selection.

## Kiến Thức Cần Có
- PySceneDetect cho scene boundary detection
- MoviePy cho video cutting
- FFmpeg cho xuất file nhanh

---

## Bước 1: Scene Detection

### Setup PySceneDetect
```python
from scenedetect import detect, ContentDetector, AdaptiveDetector
from scenedetect import open_video

class SceneDetector:
    def __init__(self, threshold: float = 30.0, min_scene_len: float = 2.0):
        self.threshold = threshold
        self.min_scene_len = min_scene_len
    
    def detect_scenes(self, video_path: str) -> list[dict]:
        """Phát hiện scene boundaries trong video."""
        video = open_video(video_path)
        
        # Content-based detection (thay đổi visual)
        scenes = detect(
            video_path,
            ContentDetector(
                threshold=self.threshold,
                min_scene_len=int(self.min_scene_len * video.frame_rate)
            )
        )
        
        result = []
        for i, (start, end) in enumerate(scenes):
            result.append({
                'scene_index': i,
                'start_time': start.get_seconds(),
                'end_time': end.get_seconds(),
                'start_frame': start.get_frames(),
                'end_frame': end.get_frames(),
                'duration': end.get_seconds() - start.get_seconds(),
            })
        
        return result
    
    def detect_adaptive(self, video_path: str) -> list[dict]:
        """Detection thích ứng - tốt hơn cho video có biến đổi ánh sáng."""
        scenes = detect(
            video_path,
            AdaptiveDetector(
                min_scene_len=int(self.min_scene_len * 30),  # assuming 30fps
                adaptive_threshold=3.5,
            )
        )
        
        return [
            {
                'scene_index': i,
                'start_time': start.get_seconds(),
                'end_time': end.get_seconds(),
                'duration': end.get_seconds() - start.get_seconds(),
            }
            for i, (start, end) in enumerate(scenes)
        ]
```

---

## Bước 2: Smart Clipping (LLM-guided)

### Kết hợp scenes + LLM highlights
```python
class SmartClipper:
    def __init__(self, llm_provider, config: dict = None):
        self.llm = llm_provider
        self.config = config or {}
        self.min_duration = self.config.get('min_clip_duration', 3)
        self.max_duration = self.config.get('max_clip_duration', 30)
    
    async def select_clips(self, scenes: list[dict], 
                            analysis: dict,
                            max_clips: int = 10) -> list[dict]:
        """LLM chọn clips tối ưu từ scenes + analysis."""
        
        prompt = f"""Bạn là editor chuyên nghiệp. Chọn {max_clips} đoạn HAY NHẤT.

## Scenes detected:
{self._format_scenes(scenes)}

## Video analysis:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

## Quy tắc:
- Mỗi clip: {self.min_duration}s - {self.max_duration}s
- Ưu tiên energy cao, nội dung hấp dẫn
- Tránh cắt giữa câu nói

Trả về JSON:
{{"clips": [
  {{"start_time": 5.2, "end_time": 18.7, "reason": "...", 
    "highlight_score": 0.95, "tags": [...], "mood": "...",
    "energy_level": "high", "content_type": "action"}}
]}}"""
        
        response = await self.llm.generate(prompt, temperature=0.3)
        return json.loads(response).get('clips', [])
    
    def merge_with_scenes(self, llm_clips: list[dict], 
                           scenes: list[dict]) -> list[dict]:
        """Căn chỉnh LLM clips với scene boundaries."""
        merged = []
        for clip in llm_clips:
            # Tìm scene gần nhất cho start/end
            best_start = self._snap_to_scene(clip['start_time'], scenes, 'start')
            best_end = self._snap_to_scene(clip['end_time'], scenes, 'end')
            
            clip['start_time'] = best_start
            clip['end_time'] = best_end
            clip['duration'] = best_end - best_start
            
            if clip['duration'] >= self.min_duration:
                merged.append(clip)
        
        return merged
    
    def _snap_to_scene(self, time: float, scenes: list[dict], 
                        edge: str) -> float:
        """Snap timestamp đến scene boundary gần nhất."""
        key = 'start_time' if edge == 'start' else 'end_time'
        closest = min(scenes, key=lambda s: abs(s[key] - time))
        
        if abs(closest[key] - time) < 1.0:  # Trong 1 giây
            return closest[key]
        return time
    
    def _format_scenes(self, scenes: list[dict]) -> str:
        lines = []
        for s in scenes:
            lines.append(
                f"Scene {s['scene_index']}: "
                f"{s['start_time']:.1f}s - {s['end_time']:.1f}s "
                f"(duration: {s['duration']:.1f}s)"
            )
        return '\n'.join(lines)
```

---

## Bước 3: Xuất Clips

### Cắt bằng MoviePy
```python
from moviepy import VideoFileClip

def cut_clip_moviepy(video_path: str, start: float, end: float, 
                      output_path: str) -> str:
    """Cắt clip bằng MoviePy (chất lượng cao, chậm hơn)."""
    with VideoFileClip(video_path) as video:
        clip = video.subclipped(start, end)
        clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            logger=None,  # Tắt log
        )
    return output_path
```

### Cắt bằng FFmpeg (nhanh hơn)
```python
import subprocess

def cut_clip_ffmpeg(video_path: str, start: float, end: float,
                     output_path: str) -> str:
    """Cắt clip bằng FFmpeg trực tiếp (nhanh, không re-encode)."""
    duration = end - start
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),           # Seek position
        '-i', video_path,
        '-t', str(duration),          # Duration
        '-c', 'copy',                 # No re-encode (fast!)
        '-avoid_negative_ts', '1',
        output_path
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path

def cut_clip_ffmpeg_reencode(video_path: str, start: float, end: float,
                              output_path: str) -> str:
    """Cắt clip bằng FFmpeg có re-encode (chính xác hơn)."""
    duration = end - start
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', video_path,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast',
        '-c:a', 'aac', '-b:a', '192k',
        output_path
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path
```

### Batch cutting
```python
import os

async def cut_all_clips(video_path: str, clips: list[dict],
                         output_dir: str, video_id: str) -> list[dict]:
    """Cắt tất cả clips từ 1 video."""
    os.makedirs(output_dir, exist_ok=True)
    results = []
    
    for i, clip in enumerate(clips):
        filename = f"{video_id}_clip_{i:03d}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        try:
            cut_clip_ffmpeg(
                video_path, 
                clip['start_time'], 
                clip['end_time'],
                output_path
            )
            clip['file_path'] = output_path
            clip['clip_index'] = i
            results.append(clip)
            print(f"  ✂️ Clip {i}: {clip['start_time']:.1f}s - {clip['end_time']:.1f}s")
        except Exception as e:
            print(f"  ❌ Clip {i} failed: {e}")
    
    return results
```

---

## Bước 4: Clip Tagging

```python
class ClipTagger:
    def __init__(self, llm_provider):
        self.llm = llm_provider
    
    async def auto_tag(self, clip: dict, transcript_segment: str) -> dict:
        """Gán tags tự động cho clip."""
        
        # Nếu đã có tags từ LLM highlight selection
        if clip.get('tags') and clip.get('mood'):
            return clip
        
        # Nếu chưa, dùng LLM để tag
        prompt = f"""Phân loại clip video này:
Transcript: "{transcript_segment}"
Duration: {clip.get('duration', 0):.1f}s

Trả về JSON:
{{"tags": ["tag1", "tag2"], "mood": "happy|sad|exciting|calm|funny",
  "energy_level": "low|medium|high|peak", 
  "content_type": "dialogue|action|reaction|transition"}}"""
        
        response = await self.llm.generate(prompt, temperature=0.3)
        tags = json.loads(response)
        clip.update(tags)
        return clip
```

---

## Lưu Clips vào Database

```python
def save_clip_to_db(db_path: str, clip: dict, video_id: int):
    """Lưu clip info vào SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO clips 
        (video_id, file_path, start_time, end_time, duration,
         tags_json, mood, energy_level, content_type, highlight_score,
         transcript_segment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        video_id,
        clip['file_path'],
        clip['start_time'],
        clip['end_time'],
        clip['duration'],
        json.dumps(clip.get('tags', []), ensure_ascii=False),
        clip.get('mood', 'neutral'),
        clip.get('energy_level', 'medium'),
        clip.get('content_type', 'unknown'),
        clip.get('highlight_score', 0.5),
        clip.get('transcript_segment', ''),
    ))
    
    conn.commit()
    clip_id = cursor.lastrowid
    conn.close()
    return clip_id
```
