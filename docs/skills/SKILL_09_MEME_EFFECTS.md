# Skill 09: Meme Sound Effects & Image Overlays

## Mục Tiêu
Tự động thêm âm thanh meme và hình ảnh meme vào video remix để tăng cảm xúc,
tạo hiệu ứng hài hước/kịch tính dựa trên phân tích nội dung từ LLM.

---

## Pipeline

```
Video Remix (đã ghép)
       │
       ▼
┌─────────────────────────┐
│ 1. LLM phân tích từng    │  Xác định mood/emotion từng đoạn
│    segment trong remix    │  → Gợi ý loại meme phù hợp
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 2. Meme Asset Manager    │  Quản lý thư viện sounds + images
│    - Sound effects       │  Phân loại theo emotion/category
│    - Image overlays      │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 3. Auto-placement        │  Đặt meme đúng thời điểm
│    - Timing engine       │  - Sound: tại điểm chuyển cảnh/highlight
│    - Position engine     │  - Image: góc phù hợp, duration tự nhiên
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 4. Render với effects    │  MoviePy composite + audio mix
└─────────────────────────┘
```

---

## Bước 1: Thư Viện Meme Assets

### Cấu trúc thư viện
```
data/meme_assets/
├── sounds/
│   ├── funny/
│   │   ├── bruh.mp3
│   │   ├── vine_boom.mp3
│   │   ├── laugh_track.mp3
│   │   ├── fart.mp3
│   │   └── oof.mp3
│   ├── dramatic/
│   │   ├── dun_dun_dun.mp3
│   │   ├── dramatic_chipmunk.mp3
│   │   ├── suspense.mp3
│   │   └── horror_sting.mp3
│   ├── hype/
│   │   ├── airhorn.mp3
│   │   ├── wow.mp3
│   │   ├── mlg_hitmarker.mp3
│   │   └── oh_baby_triple.mp3
│   ├── fail/
│   │   ├── sad_trombone.mp3
│   │   ├── windows_error.mp3
│   │   └── curb_your_enthusiasm.mp3
│   ├── success/
│   │   ├── achievement.mp3
│   │   ├── level_up.mp3
│   │   └── applause.mp3
│   └── transition/
│       ├── whoosh.mp3
│       ├── pop.mp3
│       └── swoosh.mp3
│
├── images/
│   ├── reactions/
│   │   ├── shocked_pikachu.png
│   │   ├── thinking_emoji.png
│   │   ├── skull_emoji.png
│   │   └── fire_emoji.png
│   ├── overlays/
│   │   ├── deal_with_it_glasses.png
│   │   ├── thug_life.png
│   │   ├── red_circle.png
│   │   └── arrow_pointing.png
│   ├── text_effects/
│   │   ├── emotional_damage.png
│   │   ├── to_be_continued.png
│   │   ├── wasted_gta.png
│   │   └── mission_passed.png
│   └── borders/
│       ├── fire_border.gif
│       └── sparkle_border.gif
│
└── catalog.json              # Index tất cả assets + metadata
```

### Asset Catalog Manager
```python
import os
import json
import random

class MemeAssetManager:
    """Quản lý thư viện meme sounds & images."""
    
    CATALOG_FILE = "catalog.json"
    
    def __init__(self, assets_dir: str = "./data/meme_assets"):
        self.assets_dir = assets_dir
        self.catalog = self._load_or_build_catalog()
    
    def _load_or_build_catalog(self) -> dict:
        """Load catalog hoặc build từ folder structure."""
        catalog_path = os.path.join(self.assets_dir, self.CATALOG_FILE)
        
        if os.path.exists(catalog_path):
            with open(catalog_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Auto-build từ folder structure
        catalog = {'sounds': {}, 'images': {}}
        
        for media_type in ['sounds', 'images']:
            type_dir = os.path.join(self.assets_dir, media_type)
            if not os.path.isdir(type_dir):
                continue
            for category in os.listdir(type_dir):
                cat_dir = os.path.join(type_dir, category)
                if not os.path.isdir(cat_dir):
                    continue
                catalog[media_type][category] = []
                for fname in os.listdir(cat_dir):
                    fpath = os.path.join(cat_dir, fname)
                    catalog[media_type][category].append({
                        'name': os.path.splitext(fname)[0],
                        'file': fname,
                        'path': fpath,
                        'category': category,
                    })
        
        # Save catalog
        os.makedirs(self.assets_dir, exist_ok=True)
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        
        return catalog
    
    def get_sound(self, category: str, name: str = None) -> str:
        """Lấy sound effect theo category, random nếu không chỉ định name."""
        sounds = self.catalog.get('sounds', {}).get(category, [])
        if not sounds:
            return None
        if name:
            match = [s for s in sounds if s['name'] == name]
            return match[0]['path'] if match else None
        return random.choice(sounds)['path']
    
    def get_image(self, category: str, name: str = None) -> str:
        """Lấy meme image theo category."""
        images = self.catalog.get('images', {}).get(category, [])
        if not images:
            return None
        if name:
            match = [i for i in images if i['name'] == name]
            return match[0]['path'] if match else None
        return random.choice(images)['path']
    
    def get_by_emotion(self, emotion: str) -> dict:
        """Map emotion → sounds + images phù hợp."""
        emotion_map = {
            'funny': {
                'sound_categories': ['funny', 'fail'],
                'image_categories': ['reactions', 'text_effects'],
            },
            'exciting': {
                'sound_categories': ['hype', 'success'],
                'image_categories': ['reactions', 'overlays'],
            },
            'dramatic': {
                'sound_categories': ['dramatic'],
                'image_categories': ['text_effects', 'reactions'],
            },
            'sad': {
                'sound_categories': ['fail'],
                'image_categories': ['reactions', 'text_effects'],
            },
            'neutral': {
                'sound_categories': ['transition'],
                'image_categories': [],
            },
            'peak': {
                'sound_categories': ['hype', 'funny'],
                'image_categories': ['reactions', 'overlays'],
            },
        }
        
        mapping = emotion_map.get(emotion, emotion_map['neutral'])
        
        sound = None
        for cat in mapping['sound_categories']:
            sound = self.get_sound(cat)
            if sound:
                break
        
        image = None
        for cat in mapping['image_categories']:
            image = self.get_image(cat)
            if image:
                break
        
        return {'sound': sound, 'image': image, 'emotion': emotion}
    
    def list_all(self) -> dict:
        """Liệt kê tất cả assets."""
        summary = {}
        for media_type in ['sounds', 'images']:
            summary[media_type] = {}
            for cat, items in self.catalog.get(media_type, {}).items():
                summary[media_type][cat] = len(items)
        return summary
```

---

## Bước 2: LLM Gợi Ý Meme Placement

### Prompt Template
```python
MEME_PLACEMENT_PROMPT = """Bạn là editor video meme chuyên nghiệp. Phân tích video remix và gợi ý ĐẶT meme sounds + images.

## Segments trong video remix:
{segments_description}

## Meme Assets có sẵn:
### Sounds: {available_sounds}
### Images: {available_images}

## Quy tắc:
- Không spam meme, chỉ đặt tại điểm HAY NHẤT (max {max_memes} memes)
- Sound effect phù hợp mood tại thời điểm đó
- Image overlay không che nội dung quan trọng
- Đặt meme tại: chuyển cảnh, highlight, twist, fail moment
- Mỗi meme image hiển thị 1-3 giây

## Trả về JSON:
{{
  "meme_placements": [
    {{
      "time": 5.2,
      "type": "sound",
      "asset_category": "funny",
      "asset_name": "vine_boom",
      "reason": "Khoảnh khắc bất ngờ",
      "volume": 0.8
    }},
    {{
      "time": 12.0,
      "type": "image",
      "asset_category": "reactions",
      "asset_name": "shocked_pikachu",
      "position": "bottom_right",
      "duration": 2.0,
      "size_ratio": 0.25,
      "reason": "Phản ứng với sự kiện bất ngờ"
    }},
    {{
      "time": 15.0,
      "type": "both",
      "sound_category": "hype",
      "sound_name": "airhorn",
      "image_category": "text_effects",
      "image_name": "emotional_damage",
      "position": "center",
      "duration": 1.5,
      "reason": "Climax moment"
    }}
  ],
  "total_memes": 5,
  "meme_density": "medium"
}}

CHỈ trả về JSON."""
```

### Meme Placement Generator
```python
class MemePlacementGenerator:
    """LLM gợi ý vị trí đặt meme trong video."""
    
    def __init__(self, llm_provider, asset_manager: MemeAssetManager):
        self.llm = llm_provider
        self.assets = asset_manager
    
    async def suggest_placements(self, remix_script: dict,
                                   segments_info: list[dict],
                                   max_memes: int = 8) -> list[dict]:
        """LLM phân tích video và gợi ý vị trí meme."""
        
        # Format segments
        seg_desc = self._format_segments(segments_info)
        
        # Format available assets
        asset_summary = self.assets.list_all()
        sounds_str = ', '.join(
            f"{cat}({count})" 
            for cat, count in asset_summary.get('sounds', {}).items()
        )
        images_str = ', '.join(
            f"{cat}({count})"
            for cat, count in asset_summary.get('images', {}).items()
        )
        
        prompt = MEME_PLACEMENT_PROMPT.format(
            segments_description=seg_desc,
            available_sounds=sounds_str,
            available_images=images_str,
            max_memes=max_memes,
        )
        
        response = await self.llm.generate(prompt, temperature=0.6)
        result = json.loads(response)
        
        # Resolve asset paths
        placements = []
        for p in result.get('meme_placements', []):
            resolved = self._resolve_assets(p)
            if resolved:
                placements.append(resolved)
        
        return placements
    
    def _format_segments(self, segments: list[dict]) -> str:
        lines = []
        t = 0.0
        for seg in segments:
            dur = seg.get('duration', 3.0)
            lines.append(
                f"[{t:.1f}s-{t+dur:.1f}s] "
                f"mood:{seg.get('mood','?')} "
                f"energy:{seg.get('energy_level','?')} "
                f"type:{seg.get('content_type','?')}"
            )
            t += dur
        return '\n'.join(lines)
    
    def _resolve_assets(self, placement: dict) -> dict:
        """Resolve tên asset → đường dẫn file thực."""
        ptype = placement.get('type', 'sound')
        
        if ptype in ('sound', 'both'):
            cat = placement.get('asset_category') or placement.get('sound_category', 'transition')
            name = placement.get('asset_name') or placement.get('sound_name')
            path = self.assets.get_sound(cat, name)
            if path is None:
                path = self.assets.get_sound(cat)  # Random fallback
            placement['sound_path'] = path
        
        if ptype in ('image', 'both'):
            cat = placement.get('asset_category') or placement.get('image_category', 'reactions')
            name = placement.get('asset_name') or placement.get('image_name')
            path = self.assets.get_image(cat, name)
            if path is None:
                path = self.assets.get_image(cat)
            placement['image_path'] = path
        
        return placement
```

---

## Bước 3: Render Meme Effects

### Sound Effect Mixing
```python
from moviepy import (VideoFileClip, AudioFileClip, ImageClip,
                      CompositeVideoClip, CompositeAudioClip)

class MemeEffectsRenderer:
    """Render meme sounds & images lên video."""
    
    def __init__(self):
        self.position_map = {
            'top_left': (0.05, 0.05),
            'top_right': (0.70, 0.05),
            'bottom_left': (0.05, 0.75),
            'bottom_right': (0.70, 0.75),
            'center': ('center', 'center'),
            'top_center': ('center', 0.05),
            'bottom_center': ('center', 0.80),
        }
    
    def apply_memes(self, video_path: str,
                     placements: list[dict],
                     output_path: str) -> str:
        """
        Áp dụng tất cả meme effects lên video.
        
        Args:
            video_path: Video remix đã ghép
            placements: Danh sách meme placements từ LLM
            output_path: Output path
        """
        video = VideoFileClip(video_path)
        
        # Separate sounds và images
        sound_placements = [p for p in placements if p.get('sound_path')]
        image_placements = [p for p in placements if p.get('image_path')]
        
        # 1. Add sound effects
        if sound_placements:
            video = self._add_sounds(video, sound_placements)
        
        # 2. Add image overlays
        if image_placements:
            video = self._add_images(video, image_placements)
        
        # 3. Render
        video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='192k',
            fps=30,
        )
        video.close()
        return output_path
    
    def _add_sounds(self, video, placements: list[dict]):
        """Mix sound effects vào audio."""
        audio_clips = [video.audio] if video.audio else []
        
        for p in placements:
            try:
                sfx = AudioFileClip(p['sound_path'])
                volume = p.get('volume', 0.7)
                sfx = sfx.with_volume_scaled(volume)
                sfx = sfx.with_start(p['time'])
                
                # Trim nếu sound dài hơn video còn lại
                remaining = video.duration - p['time']
                if sfx.duration > remaining:
                    sfx = sfx.subclipped(0, remaining)
                
                audio_clips.append(sfx)
            except Exception as e:
                print(f"  ⚠️ Sound error at {p['time']}s: {e}")
        
        if len(audio_clips) > 1:
            mixed = CompositeAudioClip(audio_clips)
            video = video.with_audio(mixed)
        
        return video
    
    def _add_images(self, video, placements: list[dict]):
        """Overlay meme images lên video."""
        overlay_clips = [video]
        
        for p in placements:
            try:
                img = ImageClip(p['image_path'])
                
                # Size (tỷ lệ so với video)
                size_ratio = p.get('size_ratio', 0.25)
                new_width = int(video.w * size_ratio)
                img = img.resized(width=new_width)
                
                # Duration
                duration = p.get('duration', 2.0)
                img = img.with_duration(duration)
                img = img.with_start(p['time'])
                
                # Position
                pos_key = p.get('position', 'bottom_right')
                position = self.position_map.get(pos_key, ('center', 'center'))
                img = img.with_position(position, relative=True)
                
                # Fade in/out
                from moviepy import vfx
                img = img.with_effects([
                    vfx.FadeIn(0.2),
                    vfx.FadeOut(0.3),
                ])
                
                overlay_clips.append(img)
            except Exception as e:
                print(f"  ⚠️ Image error at {p['time']}s: {e}")
        
        if len(overlay_clips) > 1:
            video = CompositeVideoClip(overlay_clips)
        
        return video
```

---

## Bước 4: Full Pipeline

```python
async def add_memes_to_remix(video_path: str,
                               segments_info: list[dict],
                               llm_provider,
                               output_path: str,
                               max_memes: int = 8,
                               assets_dir: str = "./data/meme_assets") -> str:
    """
    Pipeline: LLM gợi ý meme → resolve assets → render.
    """
    print("🎭 Adding meme effects...")
    
    # 1. Load asset manager
    assets = MemeAssetManager(assets_dir)
    summary = assets.list_all()
    total = sum(sum(v.values()) for v in summary.values())
    print(f"  📦 Assets: {total} files loaded")
    
    # 2. LLM suggest placements
    generator = MemePlacementGenerator(llm_provider, assets)
    placements = await generator.suggest_placements(
        {}, segments_info, max_memes=max_memes
    )
    
    sounds = sum(1 for p in placements if p.get('sound_path'))
    images = sum(1 for p in placements if p.get('image_path'))
    print(f"  🎵 Sounds: {sounds} | 🖼️ Images: {images}")
    
    # 3. Render
    renderer = MemeEffectsRenderer()
    result = renderer.apply_memes(video_path, placements, output_path)
    
    print(f"  ✅ Output: {result}")
    return result
```

---

## Auto-Download Meme Sounds (Starter Pack)

```python
import urllib.request

STARTER_SOUNDS = {
    'funny/vine_boom.mp3': 'https://www.myinstants.com/media/sounds/vine-boom.mp3',
    'funny/bruh.mp3': 'https://www.myinstants.com/media/sounds/bruh.mp3',
    'dramatic/dun_dun_dun.mp3': 'https://www.myinstants.com/media/sounds/dun-dun-dun.mp3',
    'hype/airhorn.mp3': 'https://www.myinstants.com/media/sounds/airhorn.mp3',
    'fail/sad_trombone.mp3': 'https://www.myinstants.com/media/sounds/sad-trombone.mp3',
    'transition/whoosh.mp3': 'https://www.myinstants.com/media/sounds/swoosh.mp3',
}

def download_starter_pack(assets_dir: str = "./data/meme_assets"):
    """Tải bộ meme sounds cơ bản."""
    for rel_path, url in STARTER_SOUNDS.items():
        full_path = os.path.join(assets_dir, 'sounds', rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        if not os.path.exists(full_path):
            try:
                urllib.request.urlretrieve(url, full_path)
                print(f"  ✅ {rel_path}")
            except Exception as e:
                print(f"  ❌ {rel_path}: {e}")
```

---

## Cấu Hình

```yaml
# Thêm vào config/settings.yaml
meme_effects:
  enabled: true
  assets_dir: "./data/meme_assets"
  max_memes_per_video: 8        # Tối đa N memes
  min_gap_between_memes: 3.0    # Giây tối thiểu giữa 2 memes
  
  sounds:
    default_volume: 0.7          # 0.0-1.0
    duck_original: true          # Giảm audio gốc khi có SFX
    duck_volume: 0.4             # Volume audio gốc khi duck
    
  images:
    default_size_ratio: 0.25     # 25% kích thước video
    default_duration: 2.0        # Giây hiển thị
    default_position: "bottom_right"
    fade_in: 0.2
    fade_out: 0.3
    
  # Auto-download starter pack khi lần đầu chạy
  auto_download_starter: true
```

---

## Test

```python
def test_asset_manager():
    mgr = MemeAssetManager("./test_assets")
    sound = mgr.get_sound("funny")
    assert sound is None or os.path.exists(sound)

def test_emotion_mapping():
    mgr = MemeAssetManager("./data/meme_assets")
    result = mgr.get_by_emotion("exciting")
    assert 'sound' in result
    assert 'image' in result

def test_position_map():
    renderer = MemeEffectsRenderer()
    assert 'bottom_right' in renderer.position_map
    assert 'center' in renderer.position_map
```
