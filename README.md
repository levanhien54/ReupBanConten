# 🎬 ReupBanConten - AI Video Remix Engine

> Hệ thống tự động tải video ngắn từ kênh YouTube, phân tích nội dung bằng AI/LLM,
> cắt thông minh và trộn thành video hoàn toàn mới.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-In%20Development-orange)

---

## 📋 Mục Lục

- [Tổng Quan](#-tổng-quan)
- [Tính Năng](#-tính-năng)
- [Kiến Trúc](#-kiến-trúc)
- [Cài Đặt](#-cài-đặt)
- [Sử Dụng](#-sử-dụng)
- [Cấu Hình](#-cấu-hình)
- [Tech Stack](#-tech-stack)
- [Đóng Góp](#-đóng-góp)

---

## 🎯 Tổng Quan

**ReupBanConten** là một pipeline tự động hóa hoàn chỉnh cho việc:

1. **Thu thập** — Tải hàng loạt video ngắn từ một kênh YouTube
2. **Phân tích** — Sử dụng AI (Whisper + LLM) để hiểu nội dung, cảm xúc, highlight
3. **Cắt thông minh** — Phát hiện cảnh + LLM chọn đoạn hay, cắt thành clips có tag
4. **Remix** — LLM tạo kịch bản → ghép clips → thêm effects → render video mới

### Điểm khác biệt

| Tính năng | Dự án khác | ReupBanConten |
|-----------|-----------|---------------|
| Nguồn video | Stock footage / 1 video | Nhiều video từ 1 kênh |
| Phân tích | Cơ bản / không có | LLM deep analysis |
| Cắt | Thủ công / random | AI-guided smart cutting |
| Remix | Ghép đơn giản | Kịch bản LLM + effects |

---

## ✨ Tính Năng

### Phase 1: Thu Thập Video
- 🔍 Quét toàn bộ video từ kênh YouTube
- 📥 Tải batch với bộ lọc (duration, date, views)
- 📊 Trích xuất metadata đầy đủ (title, tags, description, thumbnail)
- 💾 Lưu trữ có tổ chức trong SQLite database

### Phase 2: Phân Tích AI
- 🎙️ Trích xuất transcript có timestamp (faster-whisper)
- 👁️ Phân tích visual frames (BLIP-2 / LLaVA)
- 🧠 LLM phân tích: chủ đề, mood, highlights, phân loại
- 📈 Chấm điểm "viral potential" cho từng đoạn

### Phase 3: Cắt Thông Minh
- 🎬 Phát hiện cảnh tự động (PySceneDetect)
- ✂️ Cắt clips theo timestamps từ LLM
- 🏷️ Gán tag tự động (mood, topic, energy level)
- 📚 Xây dựng clip library có thể tái sử dụng

### Phase 4: Remix & Xuất
- 📝 LLM tạo kịch bản remix (thứ tự, transition, timing)
- 🎨 Effects engine (fade, slide, zoom, speed ramp)
- 💬 Auto-subtitle overlay
- 🎵 Background music mixing
- 🎥 FFmpeg render tối ưu

---

## 🏗️ Kiến Trúc

```
┌─────────────────────────────────────────────────────────────┐
│                    ReupBanConten Pipeline                     │
├──────────┬──────────┬──────────────┬────────────────────────┤
│ PHASE 1  │ PHASE 2  │   PHASE 3    │       PHASE 4          │
│ Download │ Analyze  │  Smart Cut   │    Remix & Export       │
│          │          │              │                        │
│ yt-dlp   │ Whisper  │ SceneDetect  │ LLM Script Generator   │
│ Channel  │ BLIP-2   │ LLM Clipper  │ MoviePy Assembler      │
│ Scanner  │ LLM      │ Tag Engine   │ Effects Engine         │
│ Metadata │ Classify │ Clip Library │ FFmpeg Renderer        │
├──────────┴──────────┴──────────────┴────────────────────────┤
│              LLM Layer (Ollama / OpenAI / Claude)            │
├─────────────────────────────────────────────────────────────┤
│              Database (SQLite) + Cache + Storage             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Cài Đặt

### Yêu cầu hệ thống
- Python 3.11+
- FFmpeg (đã cài trong PATH)
- NVIDIA GPU 4GB+ VRAM (khuyến nghị, cho Whisper & BLIP)
- RAM 8GB+ (cho Ollama LLM local)

### Bước 1: Clone & Setup

```bash
cd d:\ReupBanConten
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Bước 2: Cài đặt FFmpeg

```bash
# Windows (scoop)
scoop install ffmpeg

# Hoặc tải từ https://ffmpeg.org/download.html
```

### Bước 3: Cài đặt Ollama (LLM local)

```bash
# Tải từ https://ollama.ai
ollama pull llama3
ollama pull mistral
```

### Bước 4: Cấu hình

```bash
copy .env.example .env
# Chỉnh sửa .env với API keys (nếu dùng OpenAI/Claude)
```

---

## 📖 Sử Dụng

### CLI Commands

```bash
# 1. Quét kênh YouTube
python -m src.main scan --channel "https://youtube.com/@channel" --max-videos 20

# 2. Tải video
python -m src.main download --filter shorts --duration-max 180

# 3. Phân tích nội dung
python -m src.main analyze --llm ollama --model llama3

# 4. Cắt clips thông minh
python -m src.main cut --strategy highlights --min-duration 5 --max-duration 30

# 5. Remix thành video mới
python -m src.main remix --strategy energy-flow --output-duration 60 --add-subtitles

# 6. Pipeline đầy đủ (tất cả các bước)
python -m src.main pipeline --channel "https://youtube.com/@channel" \
    --max-videos 10 --remix-strategy narrative --output-duration 90
```

### Python API

```python
from src.downloader import ChannelScanner, VideoDownloader
from src.analyzer import Transcriber, LLMAnalyzer
from src.cutter import SmartClipper
from src.remixer import RemixEngine

# Quét & tải
scanner = ChannelScanner("https://youtube.com/@channel")
videos = scanner.get_shorts(max_count=10)
downloader = VideoDownloader()
downloaded = downloader.batch_download(videos)

# Phân tích
transcriber = Transcriber(model="large-v3")
analyzer = LLMAnalyzer(provider="ollama", model="llama3")

for video in downloaded:
    transcript = transcriber.transcribe(video.path)
    analysis = analyzer.analyze(transcript, video.metadata)

# Cắt
clipper = SmartClipper()
clips = clipper.cut_all(downloaded, strategy="highlights")

# Remix
engine = RemixEngine()
output = engine.remix(clips, strategy="energy-flow", duration=60)
print(f"Video mới: {output.path}")
```

---

## ⚙️ Cấu Hình

Xem `config/settings.yaml` để tùy chỉnh:

```yaml
downloader:
  max_concurrent: 3
  default_quality: "720p"
  filter_shorts_only: true

analyzer:
  whisper_model: "large-v3"
  whisper_device: "cuda"  # hoặc "cpu"
  llm_provider: "ollama"
  llm_model: "llama3"

cutter:
  scene_threshold: 30.0
  min_clip_duration: 3
  max_clip_duration: 30

remixer:
  default_strategy: "energy-flow"
  output_fps: 30
  output_resolution: "1080x1920"  # Shorts format
  add_subtitles: true
```

---

## 🛠️ Tech Stack

| Thành phần | Công nghệ | Phiên bản |
|------------|-----------|-----------|
| Ngôn ngữ | Python | 3.11+ |
| Tải video | yt-dlp | Latest |
| Video editing | MoviePy | 2.0+ |
| Video backend | FFmpeg | 6.0+ |
| Scene detection | PySceneDetect | 0.6+ |
| Transcription | faster-whisper | 1.0+ |
| LLM Local | Ollama | Latest |
| LLM Orchestration | LangChain | 0.2+ |
| Database | SQLite3 | Built-in |
| TTS | Edge-TTS | Latest |
| GUI (tùy chọn) | PyQt6 / Gradio | Latest |

---

## 📁 Cấu Trúc Dự Án

```
d:\ReupBanConten\
├── README.md                     # Tài liệu chính
├── requirements.txt              # Python dependencies
├── .env.example                  # Template API keys
├── config/                       # Cấu hình
├── docs/                         # Tài liệu chi tiết
│   ├── ARCHITECTURE.md           # Kiến trúc hệ thống
│   ├── API_REFERENCE.md          # API reference
│   ├── PROMPTS_GUIDE.md          # Hướng dẫn prompt engineering
│   ├── DEPLOYMENT.md             # Hướng dẫn deploy
│   └── skills/                   # Skill documents
├── src/                          # Source code
│   ├── downloader/               # Module tải video
│   ├── analyzer/                 # Module phân tích AI
│   ├── cutter/                   # Module cắt clips
│   ├── remixer/                  # Module remix video
│   ├── llm/                      # LLM integration layer
│   ├── database/                 # Data persistence
│   └── ui/                       # User interface
├── data/                         # Runtime data
├── tests/                        # Unit tests
└── scripts/                      # Utility scripts
```

---

## 🤝 Đóng Góp

1. Fork repo
2. Tạo feature branch: `git checkout -b feature/ten-tinh-nang`
3. Commit changes: `git commit -m "Add: tính năng mới"`
4. Push: `git push origin feature/ten-tinh-nang`
5. Tạo Pull Request

---

## 📄 License

MIT License - Xem file [LICENSE](LICENSE) để biết thêm chi tiết.
