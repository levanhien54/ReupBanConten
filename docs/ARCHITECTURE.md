# 🏗️ Kiến Trúc Hệ Thống - ReupBanConten

## Tổng Quan

ReupBanConten sử dụng kiến trúc **Pipeline-based** với 4 giai đoạn chính.

---

## Sơ Đồ Kiến Trúc

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                       │
│     CLI (Click)  │  GUI (PyQt6)  │  Web UI (Gradio)         │
├─────────────────────────────────────────────────────────────┤
│                  PIPELINE ORCHESTRATOR                        │
│              PipelineManager (main.py)                        │
├──────────┬──────────┬──────────────┬────────────────────────┤
│ Phase 1  │ Phase 2  │   Phase 3    │       Phase 4          │
│ Download │ Analyze  │  Smart Cut   │    Remix+Export        │
│          │          │              │                        │
│ Scanner  │Transcribe│ SceneDetect  │ ScriptGen              │
│ DLoader  │VisualAI  │ SmartClip    │ Assembler              │
│ MetaExt  │LLMAnalyze│ ClipTagger   │ Effects+Render         │
├──────────┴──────────┴──────────────┴────────────────────────┤
│                   SHARED SERVICES LAYER                       │
│   LLM Layer (Ollama/OpenAI/Claude)                           │
│   Database (SQLite) + Storage + Cache                        │
├─────────────────────────────────────────────────────────────┤
│                   EXTERNAL TOOLS                              │
│   yt-dlp │ FFmpeg │ faster-whisper │ Ollama Server           │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Dependencies

```
main.py
├── downloader/
│   ├── channel_scanner.py     ─── yt-dlp
│   ├── video_downloader.py    ─── yt-dlp
│   └── metadata_extractor.py  ─── yt-dlp, database
├── analyzer/
│   ├── transcriber.py         ─── faster-whisper
│   ├── visual_analyzer.py     ─── BLIP-2/LLaVA
│   ├── llm_analyzer.py        ─── llm/provider
│   └── content_classifier.py  ─── llm/provider
├── cutter/
│   ├── scene_detector.py      ─── PySceneDetect
│   ├── smart_clipper.py       ─── moviepy, llm/provider
│   └── clip_tagger.py         ─── llm/provider, database
├── remixer/
│   ├── script_generator.py    ─── llm/provider
│   ├── video_assembler.py     ─── moviepy
│   ├── effects_engine.py      ─── moviepy, ffmpeg
│   └── renderer.py            ─── ffmpeg
├── llm/
│   ├── provider.py            ─── Abstract base
│   ├── ollama_provider.py     ─── ollama
│   ├── openai_provider.py     ─── openai
│   └── prompt_manager.py      ─── config/prompts/
└── database/
    ├── models.py              ─── pydantic
    └── repository.py          ─── sqlite3
```

---

## Database Schema

### Bảng chính

| Bảng | Mô tả | Quan hệ |
|------|--------|---------|
| `channels` | Thông tin kênh YouTube | 1:N → videos |
| `videos` | Video gốc đã tải | N:1 → channel, 1:N → clips |
| `transcripts` | Transcript từ Whisper | N:1 → video |
| `analyses` | Kết quả phân tích LLM | N:1 → video |
| `clips` | Clips đã cắt | N:1 → video |
| `remix_projects` | Dự án remix | M:N → clips |
| `remix_clips` | Quan hệ remix-clip | FK → remix, clip |

### Key Columns

**videos**: id, channel_id, video_id, url, title, duration, file_path, status  
**clips**: id, video_id, file_path, start_time, end_time, tags_json, mood, energy_level, highlight_score  
**remix_projects**: id, name, strategy, clip_sequence_json, output_path, status  

---

## Error Handling

| Category | Errors | Strategy |
|----------|--------|----------|
| **Network** | YouTube blocked, rate limit | Retry + backoff, switch proxy |
| **LLM** | Timeout, invalid response | Retry, fallback provider |
| **Video** | Corrupt file, codec issue | Re-download, FFmpeg repair |
| **Storage** | Disk full | Alert user, cleanup old data |
| **GPU** | CUDA OOM | Fallback to CPU, reduce batch |

---

## Scalability

1. **Async I/O**: `asyncio` + `aiohttp` cho network ops
2. **Batch Processing**: Xử lý theo batch, không load tất cả RAM
3. **Caching**: Cache transcript & LLM analysis
4. **Worker Pools**: `ProcessPoolExecutor` cho video processing
5. **Incremental**: Hỗ trợ resume khi bị gián đoạn
6. **Plugin System**: Dễ thêm LLM provider, effect, strategy mới
