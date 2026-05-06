# Skill 04: Video Remix Engine

## Mục Tiêu
Trộn các clips đã cắt thành video mới: LLM tạo kịch bản, ghép clips, effects, render.

## Kiến Thức Cần Có
- MoviePy cho video concatenation & effects
- FFmpeg cho render pipeline
- LLM cho creative script generation

---

## Bước 1: LLM Script Generator

### Tạo kịch bản remix tự động
```python
import json

class ScriptGenerator:
    STRATEGIES = {
        'energy-flow': 'Sắp xếp: calm → build → peak → cool down',
        'topic-based': 'Nhóm clips cùng chủ đề, transition mượt giữa topics',
        'narrative': 'Tạo câu chuyện mạch lạc, có intro/climax/outro',
        'random-creative': 'Trộn ngẫu nhiên với transitions đa dạng, tạo bất ngờ',
        'best-of': 'Chỉ lấy top highlights, sắp theo highlight_score giảm dần',
        'chronological': 'Giữ thứ tự thời gian gốc',
    }
    
    def __init__(self, llm_provider):
        self.llm = llm_provider
    
    async def generate_script(self, clips: list[dict],
                                strategy: str = "energy-flow",
                                target_duration: float = 60.0) -> dict:
        """Tạo kịch bản remix từ clips."""
        
        # Simple strategies không cần LLM
        if strategy == 'best-of':
            return self._best_of_script(clips, target_duration)
        if strategy == 'chronological':
            return self._chronological_script(clips, target_duration)
        
        # Complex strategies dùng LLM
        clips_summary = self._format_clips_for_llm(clips)
        
        prompt = f"""Bạn là đạo diễn video. Tạo kịch bản remix.

Chiến lược: {strategy} - {self.STRATEGIES[strategy]}
Thời lượng mong muốn: {target_duration}s

Clips có sẵn:
{clips_summary}

Trả về JSON:
{{"title": "Tên video", "sequence": [
  {{"clip_id": 1, "transition_in": "crossfade", "transition_duration": 0.5, 
    "speed_factor": 1.0, "notes": "Lý do"}}
], "estimated_duration": 58.5, "mood_flow": "calm->peak->calm"}}"""
        
        response = await self.llm.generate(prompt, temperature=0.5)
        return json.loads(response)
    
    def _best_of_script(self, clips: list[dict], target_duration: float) -> dict:
        """Script đơn giản: top highlights."""
        sorted_clips = sorted(clips, key=lambda c: c.get('highlight_score', 0), 
                               reverse=True)
        
        sequence = []
        total = 0.0
        for clip in sorted_clips:
            if total + clip['duration'] > target_duration:
                break
            sequence.append({
                'clip_id': clip['id'],
                'transition_in': 'crossfade',
                'transition_duration': 0.5,
                'speed_factor': 1.0,
            })
            total += clip['duration']
        
        return {'title': 'Best Highlights', 'sequence': sequence, 
                'estimated_duration': total}
    
    def _chronological_script(self, clips: list[dict], 
                                target_duration: float) -> dict:
        """Script theo thứ tự thời gian."""
        sorted_clips = sorted(clips, key=lambda c: c.get('start_time', 0))
        
        sequence = []
        total = 0.0
        for clip in sorted_clips:
            if total + clip['duration'] > target_duration:
                break
            sequence.append({
                'clip_id': clip['id'],
                'transition_in': 'cut',
                'transition_duration': 0,
                'speed_factor': 1.0,
            })
            total += clip['duration']
        
        return {'title': 'Chronological Remix', 'sequence': sequence,
                'estimated_duration': total}
    
    def _format_clips_for_llm(self, clips: list[dict]) -> str:
        lines = []
        for c in clips:
            lines.append(
                f"ID:{c['id']} | {c['duration']:.1f}s | "
                f"mood:{c.get('mood','?')} | energy:{c.get('energy_level','?')} | "
                f"type:{c.get('content_type','?')} | score:{c.get('highlight_score',0):.2f} | "
                f"tags:{c.get('tags',[])}"
            )
        return '\n'.join(lines)
```

---

## Bước 2: Video Assembler (MoviePy)

### Ghép clips theo kịch bản
```python
from moviepy import (VideoFileClip, concatenate_videoclips, 
                      CompositeVideoClip, TextClip)

class VideoAssembler:
    def __init__(self):
        self.clips_cache = {}
    
    def assemble(self, script: dict, clips_db: dict[int, dict]) -> str:
        """Ghép clips theo kịch bản, trả về path assembled video."""
        video_clips = []
        
        for step in script['sequence']:
            clip_info = clips_db[step['clip_id']]
            clip = VideoFileClip(clip_info['file_path'])
            
            # Áp dụng speed
            speed = step.get('speed_factor', 1.0)
            if speed != 1.0:
                clip = clip.with_speed_scaled(speed)
            
            video_clips.append({
                'clip': clip,
                'transition': step.get('transition_in', 'cut'),
                'transition_duration': step.get('transition_duration', 0),
            })
        
        # Ghép clips
        final = self._concatenate_with_transitions(video_clips)
        return final
    
    def _concatenate_with_transitions(self, clips_data: list[dict]):
        """Ghép clips với transitions."""
        if not clips_data:
            return None
        
        if len(clips_data) == 1:
            return clips_data[0]['clip']
        
        # Simple concatenation with crossfade
        video_clips = []
        for i, data in enumerate(clips_data):
            clip = data['clip']
            
            if i > 0 and data['transition'] == 'crossfade':
                duration = data['transition_duration']
                clip = clip.with_effects([
                    # FadeIn effect
                ])
            
            video_clips.append(clip)
        
        return concatenate_videoclips(video_clips, method="compose")
```

---

## Bước 3: Effects Engine

### Transitions
```python
class EffectsEngine:
    def apply_crossfade(self, clip, duration: float = 0.5):
        """Crossfade transition."""
        from moviepy import vfx
        return clip.with_effects([vfx.CrossFadeIn(duration)])
    
    def apply_fadein(self, clip, duration: float = 1.0):
        """Fade from black."""
        from moviepy import vfx
        return clip.with_effects([vfx.FadeIn(duration)])
    
    def apply_fadeout(self, clip, duration: float = 1.0):
        """Fade to black."""
        from moviepy import vfx
        return clip.with_effects([vfx.FadeOut(duration)])
```

### Subtitles
```python
def add_subtitles(video_clip, word_timestamps: list[dict],
                   font_size: int = 40, color: str = 'white'):
    """Thêm subtitle overlay với word highlighting."""
    from moviepy import TextClip, CompositeVideoClip
    
    subtitle_clips = []
    
    for segment in word_timestamps:
        txt_clip = (
            TextClip(
                text=segment['word'],
                font_size=font_size,
                color=color,
                stroke_color='black',
                stroke_width=2,
                font='Arial',
            )
            .with_position(('center', 0.85), relative=True)
            .with_start(segment['start'])
            .with_duration(segment['end'] - segment['start'])
        )
        subtitle_clips.append(txt_clip)
    
    return CompositeVideoClip([video_clip] + subtitle_clips)
```

### Background Music
```python
from moviepy import AudioFileClip, CompositeAudioClip

def add_background_music(video_clip, music_path: str, 
                          volume: float = 0.15,
                          fade_in: float = 2.0,
                          fade_out: float = 2.0):
    """Mix background music vào video."""
    music = AudioFileClip(music_path)
    
    # Loop music nếu ngắn hơn video
    if music.duration < video_clip.duration:
        loops = int(video_clip.duration / music.duration) + 1
        music = concatenate_audioclips([music] * loops)
    
    # Trim to video length
    music = music.subclipped(0, video_clip.duration)
    
    # Adjust volume
    music = music.with_volume_scaled(volume)
    
    # Fade in/out
    music = music.audio_fadein(fade_in).audio_fadeout(fade_out)
    
    # Mix
    final_audio = CompositeAudioClip([video_clip.audio, music])
    return video_clip.with_audio(final_audio)
```

---

## Bước 4: FFmpeg Renderer

### Render cuối cùng
```python
import subprocess
import os

class Renderer:
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    def render_moviepy(self, assembled_clip, output_path: str,
                        resolution: tuple = (1080, 1920),
                        fps: int = 30) -> str:
        """Render bằng MoviePy."""
        # Resize nếu cần
        if resolution:
            assembled_clip = assembled_clip.resized(resolution)
        
        assembled_clip.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='192k',
            preset='medium',
            threads=4,
        )
        
        # Cleanup
        assembled_clip.close()
        return output_path
    
    def render_ffmpeg_concat(self, clip_paths: list[str], 
                              output_path: str) -> str:
        """Render nhanh bằng FFmpeg concat (không re-encode)."""
        # Tạo file list
        list_file = output_path + '.txt'
        with open(list_file, 'w') as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        os.remove(list_file)
        return output_path
    
    def render_preview(self, assembled_clip, output_path: str) -> str:
        """Render preview nhanh (chất lượng thấp)."""
        assembled_clip.write_videofile(
            output_path,
            fps=15,
            codec='libx264',
            preset='ultrafast',
            bitrate='1M',
        )
        return output_path
```

---

## Full Pipeline Example

```python
async def remix_pipeline(channel_url: str, output_path: str):
    """Full pipeline: download → analyze → cut → remix."""
    
    # 1. Download
    scanner = ChannelScanner(channel_url)
    videos = scanner.get_shorts(max_count=10)
    downloader = VideoDownloader()
    downloaded = await downloader.batch_download(videos)
    
    # 2. Analyze
    transcriber = Transcriber(model="large-v3")
    llm = OllamaProvider(model="llama3")
    analyzer = LLMAnalyzer(llm)
    
    all_analyses = {}
    for video in downloaded:
        transcript = transcriber.transcribe(video['file_path'])
        analysis = await analyzer.analyze(transcript, video['metadata'])
        all_analyses[video['id']] = {'transcript': transcript, 'analysis': analysis}
    
    # 3. Smart Cut
    scene_detector = SceneDetector()
    clipper = SmartClipper(llm)
    
    all_clips = []
    for video in downloaded:
        scenes = scene_detector.detect_scenes(video['file_path'])
        analysis = all_analyses[video['id']]['analysis']
        clips = await clipper.select_clips(scenes, analysis)
        cut_clips = await cut_all_clips(video['file_path'], clips, 
                                         'data/clips', video['id'])
        all_clips.extend(cut_clips)
    
    # 4. Remix
    generator = ScriptGenerator(llm)
    script = await generator.generate_script(all_clips, 
                                              strategy="energy-flow",
                                              target_duration=60)
    
    assembler = VideoAssembler()
    clips_db = {c['id']: c for c in all_clips}
    assembled = assembler.assemble(script, clips_db)
    
    renderer = Renderer()
    final_path = renderer.render_moviepy(assembled, output_path)
    
    print(f"✅ Remix hoàn tất: {final_path}")
    return final_path
```
