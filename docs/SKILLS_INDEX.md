# Skills Index - ReupBanConten v2.0

## Tổng Quan Bộ Skills

Dự án ReupBanConten v2.0 gồm **14 skills**, mở rộng từ 9 skills gốc + 5 skills mới
cho AI Video Remixing Agent hoàn chỉnh.

---

## Danh Sách Skills

| # | Skill | Mô tả | Độ khó |
|---|-------|--------|--------|
| 01 | **YouTube Download** | Quét kênh, tải batch, metadata + **normalize 720p/20fps + SHA-256 dedup** | ⭐⭐ |
| 02 | **AI Analysis** | Whisper transcript + LLM phân tích + **Twelve Labs scene tags** | ⭐⭐⭐ |
| 03 | **Smart Cutting** | Scene detect + LLM clip cutting + **Clip Library 2s (không cắt giữa câu)** | ⭐⭐⭐ |
| 04 | **Video Remix** | LLM script + assembly + **Hook→Meat→CTA + J-cut/L-cut** | ⭐⭐⭐⭐ |
| 05 | **LLM Integration** | Multi-provider + fallback + **Gemini 1.5 Flash + RAG logic** | ⭐⭐⭐ |
| 06 | **Emotion Filter** | Phát hiện & loại bỏ đoạn cảm xúc đều đều (pre-LLM) | ⭐⭐⭐⭐ |
| 07 | **ElevenLabs Voiceover** | LLM kịch bản + ElevenLabs TTS + **auto-speed adjustment** | ⭐⭐⭐ |
| 08 | **Cross-Folder Remix** | Scene detect chính xác, loại black/flash + **Vector-based balance** | ⭐⭐⭐⭐ |
| 09 | **Meme Effects** | Âm thanh + hình ảnh meme + **precise position mapping** | ⭐⭐⭐ |
| 10 | **🆕 Twelve Labs Perception** | API client, video indexing, embeddings, Pegasus scene summary | ⭐⭐⭐⭐ |
| 11 | **🆕 Vector Search Engine** | ChromaDB setup, semantic search, hybrid tag+vector queries | ⭐⭐⭐ |
| 12 | **🆕 Audio Engineering** | J-cut, L-cut, smart BGM ducking, audio sync | ⭐⭐⭐⭐ |
| 13 | **🆕 Color & Visual Polish** | LUT grading, histogram match, xfade transitions | ⭐⭐⭐ |
| 14 | **🆕 Cost Optimizer** | API quota tracking, cache-first strategy, hash dedup | ⭐⭐ |

---

## Thứ Tự Học Khuyến Nghị v2.0

```
Skill 14 (Cost) ─► Skill 01 (Download) ─► Skill 05 (LLM+Gemini)
                                                    │
                                                    ▼
                                    Skill 10 (Twelve Labs) ─► Skill 11 (Vector DB)
                                                    │
                                                    ▼
                                              Skill 06 (Emotion)
                                                    │
                                                    ▼
                                              Skill 02 (Analyze)
                                                    │
                                                    ▼
                Skill 12 (Audio) ◄── Skill 04 (Remix) ◄── Skill 03 (Cut+Library)
                                          │
                                    ┌─────┼─────┐
                                    ▼     ▼     ▼
                                  07    09    13
                                  VO   Meme  Color
```

---

## Dependencies Giữa Skills

| Skill | Phụ thuộc |
|-------|-----------| 
| 01 Download | 14 (Cost Optimizer — hash dedup) |
| 02 Analyze | 05, 06, **10** (LLM + Emotion + Twelve Labs) |
| 03 Smart Cut | 02, 05, **11** (Vector DB cho clip library) |
| 04 Remix | 03, 05, **12** (Audio Engineering) |
| 05 LLM | Không có |
| 06 Emotion Filter | Không có (librosa, audio analysis) |
| 07 Voiceover | 04, 05 |
| 08 Cross-Folder | 03, 05, **11** |
| 09 Meme Effects | 04, 05 |
| 10 Twelve Labs | Không có (API key required) |
| 11 Vector Search | **10** (embeddings from Twelve Labs) |
| 12 Audio Engineering | Không có (FFmpeg) |
| 13 Color & Visual | Không có (FFmpeg LUTs) |
| 14 Cost Optimizer | Không có |

---

## Pipeline v2.0

```
Download → Normalize → Hash Check → Pre-cut → Emotion Filter
   01          01          14          01          06
                                                   │
                                                   ▼
Twelve Labs Index → Pegasus Tags → Whisper Transcript → LLM Analyze
       10               10              02                02
                                                           │
                                                           ▼
Vector Store → Clip Library 2s → Gemini Script → Vector Select → RAG Pick
     11              03              04              04           04
                                                                   │
                                                                   ▼
J/L-cut → Color Grade → BGM Duck → Voiceover → Meme → Final Render
  12          13          12          07         09        04
```

---

## Tài Liệu Liên Quan

- [README.md](../README.md) — Tổng quan dự án
- [ARCHITECTURE.md](ARCHITECTURE.md) — Kiến trúc hệ thống
- [API_REFERENCE.md](API_REFERENCE.md) — API reference
- [PROMPTS_GUIDE.md](PROMPTS_GUIDE.md) — Prompt engineering
- [DEPLOYMENT.md](DEPLOYMENT.md) — Hướng dẫn cài đặt
- [PROJECT_PLAN.md](../PROJECT_PLAN.md) — Kế hoạch phát triển v2.0
