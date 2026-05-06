# 📖 API Reference - ReupBanConten

## Tổng Quan Modules

---

## 1. Downloader Module (`src/downloader/`)

### ChannelScanner

```python
class ChannelScanner:
    """Quét và lấy danh sách video từ kênh YouTube."""
    
    def __init__(self, channel_url: str, config: dict = None):
        """
        Args:
            channel_url: URL kênh YouTube (hỗ trợ @handle, /channel/, /c/)
            config: Override settings từ config/settings.yaml
        """
    
    def get_all_videos(self) -> list[VideoInfo]:
        """Lấy toàn bộ video public của kênh."""
    
    def get_shorts(self, max_count: int = 50) -> list[VideoInfo]:
        """Lọc chỉ lấy YouTube Shorts (vertical, < 60s)."""
    
    def get_recent(self, days: int = 30, max_count: int = 20) -> list[VideoInfo]:
        """Lấy video gần đây trong N ngày."""
    
    def filter_by_duration(self, min_sec: int, max_sec: int) -> list[VideoInfo]:
        """Lọc video theo thời lượng."""
    
    def filter_by_views(self, min_views: int) -> list[VideoInfo]:
        """Lọc video theo lượt xem tối thiểu."""
```

### VideoDownloader

```python
class VideoDownloader:
    """Tải video batch từ YouTube."""
    
    def __init__(self, output_dir: str = None, config: dict = None):
        """
        Args:
            output_dir: Thư mục lưu video (default: data/downloads/)
            config: Override download settings
        """
    
    async def download(self, video: VideoInfo, quality: str = "720p") -> DownloadResult:
        """Tải 1 video."""
    
    async def batch_download(self, videos: list[VideoInfo], 
                              max_concurrent: int = 3) -> list[DownloadResult]:
        """Tải nhiều video song song."""
    
    def set_proxy(self, proxy_url: str):
        """Cấu hình proxy cho download."""
    
    def set_cookies(self, cookies_file: str):
        """Dùng cookies cho video age-restricted."""
```

### MetadataExtractor

```python
class MetadataExtractor:
    """Trích xuất metadata từ video YouTube."""
    
    def extract(self, video_url: str) -> VideoMetadata:
        """Trích metadata: title, description, tags, duration, thumbnail."""
    
    def extract_subtitles(self, video_url: str, 
                          languages: list[str] = ["vi", "en"]) -> dict[str, str]:
        """Tải subtitle có sẵn trên YouTube."""
```

---

## 2. Analyzer Module (`src/analyzer/`)

### Transcriber

```python
class Transcriber:
    """Trích xuất transcript từ audio/video bằng Whisper."""
    
    def __init__(self, model: str = "large-v3", device: str = "cuda"):
        """
        Args:
            model: Whisper model (tiny/base/small/medium/large-v3)
            device: "cuda" hoặc "cpu"
        """
    
    def transcribe(self, file_path: str, language: str = None) -> TranscriptResult:
        """
        Transcribe video/audio file.
        
        Returns:
            TranscriptResult with:
            - full_text: str
            - segments: list[{start, end, text}]
            - word_timestamps: list[{word, start, end, probability}]
            - detected_language: str
        """
    
    def transcribe_batch(self, file_paths: list[str]) -> list[TranscriptResult]:
        """Transcribe nhiều file."""
```

### LLMAnalyzer

```python
class LLMAnalyzer:
    """Phân tích nội dung video bằng LLM."""
    
    def __init__(self, provider: str = "ollama", model: str = "llama3"):
        """
        Args:
            provider: "ollama", "openai", hoặc "anthropic"
            model: Tên model cụ thể
        """
    
    async def analyze(self, transcript: TranscriptResult, 
                       metadata: VideoMetadata) -> AnalysisResult:
        """
        Phân tích toàn diện 1 video.
        
        Returns:
            AnalysisResult with:
            - topics: list[str]
            - mood: str
            - category: str
            - summary: str
            - key_moments: list[KeyMoment]
            - overall_energy: float (0-1)
            - viral_potential: float (0-1)
        """
    
    async def analyze_batch(self, items: list[tuple]) -> list[AnalysisResult]:
        """Phân tích nhiều video (map-reduce nếu cần)."""
```

### ContentClassifier

```python
class ContentClassifier:
    """Phân loại nội dung video."""
    
    def classify(self, analysis: AnalysisResult) -> str:
        """Phân loại vào category chính."""
    
    def get_tags(self, analysis: AnalysisResult) -> list[str]:
        """Tạo danh sách tags tự động."""
```

---

## 3. Cutter Module (`src/cutter/`)

### SceneDetector

```python
class SceneDetector:
    """Phát hiện ranh giới cảnh trong video."""
    
    def __init__(self, threshold: float = 30.0):
        """
        Args:
            threshold: Sensitivity (thấp hơn = nhiều scene hơn)
        """
    
    def detect(self, video_path: str) -> list[SceneBoundary]:
        """
        Detect scene boundaries.
        
        Returns:
            list of SceneBoundary(start_time, end_time, start_frame, end_frame)
        """
```

### SmartClipper

```python
class SmartClipper:
    """Cắt clips thông minh kết hợp scene detection + LLM."""
    
    def __init__(self, config: dict = None):
        """Khởi tạo với config cutter settings."""
    
    async def cut_highlights(self, video_path: str,
                              analysis: AnalysisResult,
                              scenes: list[SceneBoundary],
                              min_duration: float = 3.0,
                              max_duration: float = 30.0) -> list[Clip]:
        """Cắt clips từ highlights đã phân tích."""
    
    async def cut_all(self, videos: list[ProcessedVideo],
                       strategy: str = "highlights") -> list[Clip]:
        """Cắt clips từ nhiều video."""
    
    def export_clip(self, video_path: str, start: float, 
                     end: float, output_path: str) -> str:
        """Xuất 1 clip ra file."""
```

### ClipTagger

```python
class ClipTagger:
    """Gán tag tự động cho clips."""
    
    async def tag(self, clip: Clip, transcript_segment: str) -> TaggedClip:
        """Gán tags: mood, energy, content_type."""
    
    async def tag_batch(self, clips: list[Clip]) -> list[TaggedClip]:
        """Gán tags cho nhiều clips."""
```

---

## 4. Remixer Module (`src/remixer/`)

### ScriptGenerator

```python
class ScriptGenerator:
    """LLM tạo kịch bản remix."""
    
    async def generate(self, clips: list[TaggedClip],
                        strategy: str = "energy-flow",
                        target_duration: float = 60.0) -> RemixScript:
        """
        Tạo kịch bản remix.
        
        Args:
            clips: Danh sách clips có tags
            strategy: Chiến lược remix
            target_duration: Thời lượng mong muốn (giây)
            
        Returns:
            RemixScript with sequence, transitions, metadata
        """
```

### VideoAssembler

```python
class VideoAssembler:
    """Ghép clips theo kịch bản."""
    
    def assemble(self, script: RemixScript, 
                  clips: dict[int, Clip]) -> AssembledVideo:
        """Ghép clips theo thứ tự trong script."""
```

### EffectsEngine

```python
class EffectsEngine:
    """Áp dụng effects cho video."""
    
    def add_transition(self, clip_a, clip_b, 
                        transition_type: str, duration: float):
        """Thêm transition giữa 2 clips."""
    
    def add_subtitles(self, video, transcript_segments: list):
        """Overlay subtitles lên video."""
    
    def add_background_music(self, video, music_path: str, volume: float):
        """Mix background music."""
    
    def apply_speed_ramp(self, video, speed_factor: float):
        """Thay đổi tốc độ video."""
```

### Renderer

```python
class Renderer:
    """FFmpeg render pipeline."""
    
    def render(self, assembled: AssembledVideo,
                output_path: str,
                resolution: str = "1080x1920",
                fps: int = 30) -> str:
        """Render video cuối cùng bằng FFmpeg."""
    
    def render_preview(self, assembled: AssembledVideo,
                        output_path: str) -> str:
        """Render preview chất lượng thấp (nhanh)."""
```

---

## 5. LLM Module (`src/llm/`)

### LLMProvider (Abstract)

```python
class LLMProvider(ABC):
    """Abstract base cho tất cả LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, 
                        temperature: float = 0.3,
                        max_tokens: int = 4096) -> str:
        """Gửi prompt và nhận response."""
    
    @abstractmethod
    async def generate_json(self, prompt: str, 
                             schema: dict = None) -> dict:
        """Gửi prompt và parse response thành JSON."""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Kiểm tra provider có sẵn sàng không."""
```

---

## Data Models (`src/database/models.py`)

```python
class VideoInfo(BaseModel):
    video_id: str
    url: str
    title: str
    duration: float
    view_count: int
    upload_date: str

class VideoMetadata(BaseModel):
    title: str
    description: str
    tags: list[str]
    duration: float
    thumbnail_url: str

class TranscriptResult(BaseModel):
    full_text: str
    segments: list[TranscriptSegment]
    word_timestamps: list[WordTimestamp]
    detected_language: str

class AnalysisResult(BaseModel):
    topics: list[str]
    mood: str
    category: str
    summary: str
    key_moments: list[KeyMoment]
    overall_energy: float
    viral_potential: float

class Clip(BaseModel):
    id: int
    video_id: int
    file_path: str
    start_time: float
    end_time: float
    duration: float
    highlight_score: float

class TaggedClip(Clip):
    tags: list[str]
    mood: str
    energy_level: str
    content_type: str

class RemixScript(BaseModel):
    title: str
    sequence: list[RemixStep]
    estimated_duration: float
    mood_flow: str
```
