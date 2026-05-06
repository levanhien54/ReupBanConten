# Skill 07: ElevenLabs Voiceover & Commentary

## Mục Tiêu
Sử dụng ElevenLabs API để tạo giọng bình luận (voiceover) cho video remix.
LLM tạo kịch bản bình luận → ElevenLabs tổng hợp giọng nói → Ghép vào video.

## Kiến Thức Cần Có
- ElevenLabs API (text-to-speech)
- LLM prompt engineering cho kịch bản bình luận
- Audio mixing (MoviePy / FFmpeg)

---

## Pipeline Commentary

```
Clips đã chọn + Analysis
         │
         ▼
┌─────────────────────┐
│  LLM: Tạo kịch bản  │  Viết lời bình luận cho từng đoạn
│  bình luận           │  với timing cụ thể
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  ElevenLabs API      │  Text → Speech synthesis
│  (TTS)               │  Chọn giọng, style, emotion
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Audio Mixer         │  Ghép voiceover + original audio
│  (MoviePy/FFmpeg)    │  Điều chỉnh volume balance
└─────────┬───────────┘
          │
          ▼
    Video với bình luận
```

---

## Bước 1: Setup ElevenLabs

### Cài đặt
```bash
pip install elevenlabs
```

### Client wrapper
```python
from elevenlabs import ElevenLabs
from elevenlabs import VoiceSettings
import os

class ElevenLabsClient:
    """Wrapper cho ElevenLabs API."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY is required")
        
        self.client = ElevenLabs(api_key=self.api_key)
        self._voices_cache = None
    
    def list_voices(self) -> list[dict]:
        """Lấy danh sách voices có sẵn."""
        if self._voices_cache is None:
            response = self.client.voices.get_all()
            self._voices_cache = [
                {
                    'voice_id': v.voice_id,
                    'name': v.name,
                    'category': v.category,
                    'labels': v.labels,
                    'description': v.description,
                }
                for v in response.voices
            ]
        return self._voices_cache
    
    def find_voice(self, name: str = None, language: str = None) -> str:
        """Tìm voice phù hợp."""
        voices = self.list_voices()
        
        if name:
            for v in voices:
                if name.lower() in v['name'].lower():
                    return v['voice_id']
        
        # Default: Rachel (clear, narrator-like)
        for v in voices:
            if 'rachel' in v['name'].lower():
                return v['voice_id']
        
        return voices[0]['voice_id'] if voices else None
    
    def synthesize(self, text: str, voice_id: str = None,
                    output_path: str = "voiceover.mp3",
                    stability: float = 0.5,
                    similarity_boost: float = 0.75,
                    style: float = 0.5,
                    speed: float = 1.0) -> str:
        """
        Tổng hợp giọng nói từ text.
        
        Args:
            text: Nội dung bình luận
            voice_id: ID giọng nói (None = auto-select)
            output_path: Đường dẫn file output
            stability: 0.0-1.0 (thấp=biến đổi, cao=ổn định)
            similarity_boost: 0.0-1.0 (độ giống original voice)
            style: 0.0-1.0 (mức style exaggeration)
            speed: 0.5-2.0 (tốc độ nói)
        
        Returns:
            Path to generated audio file
        """
        if voice_id is None:
            voice_id = self.find_voice()
        
        audio_generator = self.client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",  # Hỗ trợ tiếng Việt
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                use_speaker_boost=True,
            ),
        )
        
        # Lưu audio
        with open(output_path, 'wb') as f:
            for chunk in audio_generator:
                f.write(chunk)
        
        return output_path
    
    def synthesize_segments(self, segments: list[dict], 
                             voice_id: str = None,
                             output_dir: str = "./data/voiceovers") -> list[dict]:
        """
        Tổng hợp nhiều đoạn bình luận.
        
        Args:
            segments: [{"text": "...", "timing": "00:05", "emotion": "excited"}]
            
        Returns:
            Segments với audio_path đã tạo
        """
        os.makedirs(output_dir, exist_ok=True)
        results = []
        
        for i, seg in enumerate(segments):
            output_path = os.path.join(output_dir, f"comment_{i:03d}.mp3")
            
            # Điều chỉnh voice settings theo emotion
            settings = self._emotion_to_settings(seg.get('emotion', 'neutral'))
            
            self.synthesize(
                text=seg['text'],
                voice_id=voice_id,
                output_path=output_path,
                **settings
            )
            
            seg['audio_path'] = output_path
            results.append(seg)
            print(f"  🎙️ Segment {i}: '{seg['text'][:50]}...'")
        
        return results
    
    def _emotion_to_settings(self, emotion: str) -> dict:
        """Map emotion → voice settings."""
        emotion_map = {
            'excited': {'stability': 0.3, 'similarity_boost': 0.7, 'style': 0.8, 'speed': 1.1},
            'calm': {'stability': 0.8, 'similarity_boost': 0.8, 'style': 0.2, 'speed': 0.9},
            'dramatic': {'stability': 0.4, 'similarity_boost': 0.6, 'style': 0.9, 'speed': 0.95},
            'funny': {'stability': 0.3, 'similarity_boost': 0.7, 'style': 0.7, 'speed': 1.05},
            'neutral': {'stability': 0.5, 'similarity_boost': 0.75, 'style': 0.5, 'speed': 1.0},
            'sad': {'stability': 0.7, 'similarity_boost': 0.8, 'style': 0.6, 'speed': 0.85},
        }
        return emotion_map.get(emotion, emotion_map['neutral'])
    
    def get_quota(self) -> dict:
        """Kiểm tra quota còn lại."""
        subscription = self.client.user.get_subscription()
        return {
            'character_count': subscription.character_count,
            'character_limit': subscription.character_limit,
            'remaining': subscription.character_limit - subscription.character_count,
            'tier': subscription.tier,
        }
```

---

## Bước 2: LLM Tạo Kịch Bản Bình Luận

### Prompt Template
```python
COMMENTARY_PROMPT = """Bạn là người bình luận video chuyên nghiệp, giọng hài hước và cuốn hút.

## Thông tin video remix:
- Tên: {remix_title}
- Chiến lược: {strategy}
- Tổng thời lượng: {total_duration}s

## Danh sách clips theo thứ tự:
{clips_description}

## Yêu cầu:
Viết lời bình luận ngắn gọn cho video remix này.
- Mỗi đoạn bình luận 1-3 câu (15-40 từ)
- PHẢI có timing chính xác (khi nào nói)
- Tone phù hợp với mood clip tại thời điểm đó
- Giọng tự nhiên, có cảm xúc, KHÔNG robot
- Ngôn ngữ: {language}
- Bình luận PHẢI nằm trong khoảng trống giữa các đoạn nói gốc

## Trả về JSON:
{{
  "intro": {{
    "text": "Lời mở đầu hấp dẫn",
    "start_time": 0.0,
    "emotion": "excited"
  }},
  "segments": [
    {{
      "text": "Nội dung bình luận",
      "start_time": 5.0,
      "duration_estimate": 3.0,
      "emotion": "excited|calm|dramatic|funny|neutral|sad",
      "clip_context": "Mô tả ngắn clip đang diễn ra"
    }}
  ],
  "outro": {{
    "text": "Lời kết ấn tượng",
    "start_time": 55.0,
    "emotion": "excited"
  }},
  "total_commentary_segments": 5,
  "estimated_total_speech_duration": 25.0
}}

CHỈ trả về JSON hợp lệ."""
```

### Commentary Script Generator
```python
class CommentaryGenerator:
    """Tạo kịch bản bình luận bằng LLM."""
    
    def __init__(self, llm_provider):
        self.llm = llm_provider
    
    async def generate_commentary(self, remix_script: dict,
                                    clips: list[dict],
                                    language: str = "vi") -> dict:
        """Tạo kịch bản bình luận cho video remix."""
        
        clips_desc = self._format_clips(clips, remix_script)
        
        prompt = COMMENTARY_PROMPT.format(
            remix_title=remix_script.get('title', 'Video Remix'),
            strategy=remix_script.get('mood_flow', 'dynamic'),
            total_duration=remix_script.get('estimated_duration', 60),
            clips_description=clips_desc,
            language=language,
        )
        
        response = await self.llm.generate(prompt, temperature=0.6)
        return json.loads(response)
    
    def _format_clips(self, clips: list[dict], script: dict) -> str:
        """Format clips cho prompt."""
        lines = []
        current_time = 0.0
        
        for step in script.get('sequence', []):
            clip_id = step['clip_id']
            clip = next((c for c in clips if c['id'] == clip_id), None)
            if clip is None:
                continue
            
            lines.append(
                f"[{current_time:.1f}s - {current_time + clip['duration']:.1f}s] "
                f"Clip #{clip_id}: mood={clip.get('mood','?')}, "
                f"energy={clip.get('energy_level','?')}, "
                f"transcript: \"{clip.get('transcript_segment', '')[:100]}\""
            )
            current_time += clip['duration']
        
        return '\n'.join(lines)
```

---

## Bước 3: Audio Mixing (Ghép Voiceover + Video)

```python
from moviepy import (VideoFileClip, AudioFileClip, CompositeAudioClip,
                      concatenate_audioclips)

class VoiceoverMixer:
    """Ghép voiceover vào video remix."""
    
    def __init__(self, original_volume: float = 0.3,
                 voiceover_volume: float = 1.0):
        """
        Args:
            original_volume: Volume audio gốc khi có voiceover (duck)
            voiceover_volume: Volume voiceover
        """
        self.original_volume = original_volume
        self.voiceover_volume = voiceover_volume
    
    def mix_voiceover(self, video_path: str,
                       commentary_segments: list[dict],
                       output_path: str) -> str:
        """
        Ghép voiceover vào video.
        
        Args:
            video_path: Path video gốc
            commentary_segments: Segments đã có audio_path từ ElevenLabs
            output_path: Path output
        """
        video = VideoFileClip(video_path)
        original_audio = video.audio
        
        # Tạo voiceover audio clips với timing
        vo_clips = []
        duck_regions = []  # Vùng cần giảm volume audio gốc
        
        for seg in commentary_segments:
            if not seg.get('audio_path'):
                continue
            
            vo_audio = AudioFileClip(seg['audio_path'])
            start_time = seg.get('start_time', 0)
            
            # Set timing
            vo_audio = vo_audio.with_start(start_time)
            vo_audio = vo_audio.with_volume_scaled(self.voiceover_volume)
            
            vo_clips.append(vo_audio)
            duck_regions.append({
                'start': start_time,
                'end': start_time + vo_audio.duration,
            })
        
        if not vo_clips:
            return video_path
        
        # Duck original audio khi có voiceover
        if original_audio and duck_regions:
            ducked_audio = self._duck_audio(original_audio, duck_regions)
        else:
            ducked_audio = original_audio
        
        # Mix tất cả
        all_audio = [ducked_audio] + vo_clips if ducked_audio else vo_clips
        final_audio = CompositeAudioClip(all_audio)
        
        # Xuất video
        final_video = video.with_audio(final_audio)
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='192k',
        )
        
        # Cleanup
        video.close()
        for clip in vo_clips:
            clip.close()
        
        return output_path
    
    def _duck_audio(self, audio, duck_regions: list[dict]):
        """Giảm volume audio gốc trong các vùng có voiceover."""
        
        def volume_filter(get_frame, t):
            """Dynamic volume adjustment."""
            for region in duck_regions:
                if region['start'] <= t <= region['end']:
                    return get_frame(t) * self.original_volume
            return get_frame(t)
        
        return audio.transform(volume_filter)
```

---

## Bước 4: Full Commentary Pipeline

```python
async def add_commentary_to_remix(remix_video_path: str,
                                    remix_script: dict,
                                    clips: list[dict],
                                    llm_provider,
                                    output_path: str,
                                    language: str = "vi",
                                    voice_name: str = None) -> str:
    """
    Pipeline đầy đủ: LLM script → ElevenLabs TTS → Mix vào video.
    """
    
    # 1. Tạo kịch bản bình luận
    print("📝 Tạo kịch bản bình luận...")
    generator = CommentaryGenerator(llm_provider)
    commentary = await generator.generate_commentary(
        remix_script, clips, language
    )
    
    # 2. Tổng hợp giọng nói
    print("🎙️ Tổng hợp giọng nói ElevenLabs...")
    elevenlabs = ElevenLabsClient()
    voice_id = elevenlabs.find_voice(name=voice_name)
    
    # Collect tất cả segments
    all_segments = []
    if commentary.get('intro'):
        all_segments.append(commentary['intro'])
    all_segments.extend(commentary.get('segments', []))
    if commentary.get('outro'):
        all_segments.append(commentary['outro'])
    
    # Kiểm tra quota
    total_chars = sum(len(s['text']) for s in all_segments)
    quota = elevenlabs.get_quota()
    print(f"  Cần {total_chars} ký tự, còn {quota['remaining']} ký tự")
    
    if total_chars > quota['remaining']:
        print("⚠️ Không đủ quota ElevenLabs!")
        return remix_video_path
    
    # Synthesize
    synthesized = elevenlabs.synthesize_segments(
        all_segments, voice_id=voice_id
    )
    
    # 3. Mix vào video
    print("🎵 Ghép voiceover vào video...")
    mixer = VoiceoverMixer(original_volume=0.3)
    final = mixer.mix_voiceover(
        remix_video_path, synthesized, output_path
    )
    
    print(f"✅ Video với bình luận: {final}")
    return final
```

---

## Cấu Hình

```yaml
# Thêm vào config/settings.yaml
voiceover:
  provider: "elevenlabs"      # elevenlabs hoặc edge-tts (free fallback)
  
  elevenlabs:
    model: "eleven_multilingual_v2"
    default_voice: null         # Auto-select nếu null
    stability: 0.5
    similarity_boost: 0.75
    style: 0.5
    speed: 1.0
    
  mixing:
    original_volume_during_vo: 0.3   # Duck audio gốc khi có VO
    voiceover_volume: 1.0
    fade_in: 0.2
    fade_out: 0.2
    
  commentary:
    language: "vi"
    max_segments: 8
    min_gap_between: 3.0        # Giây giữa 2 đoạn bình luận
    style: "entertaining"       # entertaining, educational, dramatic
```

---

## Edge-TTS Fallback (Miễn phí)

```python
import edge_tts
import asyncio

class EdgeTTSFallback:
    """Fallback miễn phí khi không có ElevenLabs."""
    
    VOICE_MAP = {
        'vi': 'vi-VN-NamMinhNeural',       # Nam, tiếng Việt
        'vi_female': 'vi-VN-HoaiMyNeural',  # Nữ, tiếng Việt
        'en': 'en-US-GuyNeural',             # Nam, tiếng Anh
        'en_female': 'en-US-JennyNeural',    # Nữ, tiếng Anh
    }
    
    async def synthesize(self, text: str, output_path: str,
                          voice: str = "vi", rate: str = "+0%") -> str:
        """TTS bằng Edge-TTS (miễn phí, không giới hạn)."""
        voice_name = self.VOICE_MAP.get(voice, voice)
        
        communicate = edge_tts.Communicate(
            text=text, voice=voice_name, rate=rate
        )
        await communicate.save(output_path)
        return output_path
```

---

## Environment

```bash
# Thêm vào .env
ELEVENLABS_API_KEY=your-elevenlabs-api-key-here
ELEVENLABS_DEFAULT_VOICE=Rachel
```

## Dependencies

```
# Thêm vào requirements.txt
elevenlabs>=1.0.0            # ElevenLabs TTS API
edge-tts>=6.1.0              # Free TTS fallback
```
