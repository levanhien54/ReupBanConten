# 📋 Project Plan - ReupBanConten v2.0
## Kế Hoạch Phát Triển — AI Video Remixing Agent

> Tối ưu 3 yếu tố: **Tính sáng tạo** (Gemini) · **Hiểu sâu video** (Twelve Labs) · **Hiệu quả kinh tế** (Database/Local)

---

## 🔄 Pipeline Tổng Thể

```
GĐ1: Tiền xử lý       GĐ2: AI Perception      GĐ3: Kho Tri Thức
────────────────       ─────────────────       ─────────────────
Nén 720p/20fps  ──►    Twelve Labs Index  ──►   PostgreSQL (Meta)
SHA-256 Hash           Pegasus Scene Tag       ChromaDB (Vector)
Auto Pre-cut           Whisper Transcript      Clip Library 2s

GĐ4: Đạo Diễn AI       GĐ5: Render
─────────────────       ──────────
Gemini Script    ──►    J-cut / L-cut
Vector Search           Xfade + LUT Color
RAG Clip Select         BGM Smart Ducking
```

---

## Phase 1: Tiền Xử Lý & Định Danh (Tuần 1-2)

### Sprint 1.1 — Normalizer + Hash (Ngày 1-3)
- [x] `src/preprocessor/normalizer.py` — Nén 720p/20fps (FFmpeg)
- [x] `src/preprocessor/hasher.py` — SHA-256 dedup
- [x] Cập nhật settings.yaml + database schema

### Sprint 1.2 — Smart Pre-cut (Ngày 4-7)
- [x] `src/preprocessor/pre_cutter.py` — Loại silence/black frames
- [x] CLI: `preprocess --input video.mp4`
- [x] Test pipeline: normalize → hash → pre_cut

**Milestone 1**: Video nén, hash, loại rác tự động ✅

---

## Phase 2: AI Perception (Tuần 3-5)

### Sprint 2.1 — Twelve Labs (Ngày 8-12)
- [x] `src/analyzer/twelve_labs_client.py` — Marengo indexing
- [x] Upload + embeddings + rate limit handling

### Sprint 2.2 — Pegasus Scene Analysis (Ngày 13-17)
- [x] Scene summary + auto tags (mood, action, object)
- [x] Map kết quả vào clips table

### Sprint 2.3 — Gemini Provider (Ngày 18-22)
- [x] `src/llm/gemini_provider.py` — Gemini 1.5 Flash
- [x] Hook → Meat → CTA prompt templates
- [x] Tích hợp vào LLMFactory + FallbackProvider

### Sprint 2.4 — Enhanced Transcript (Ngày 23-25)
- [x] Word-level timestamp chính xác ms
- [x] Cache transcript JSON

**Milestone 2**: Embeddings + scene tags + transcript ms ✅

---

## Phase 3: Kho Tri Thức (Tuần 6-8)

### Sprint 3.1 — PostgreSQL (Ngày 26-30)
- [x] `src/core/database_pg.py` — PostgreSQL adapter (giữ SQLite fallback)
- [x] Migration script + connection pooling

### Sprint 3.2 — Vector Database (Ngày 31-35)
- [x] `src/core/vector_store.py` — ChromaDB semantic search
- [x] store/search embeddings, hybrid tag+vector queries

### Sprint 3.3 — Clip Library 2s (Ngày 36-40)
- [x] `src/cutter/clip_library.py` — Đơn vị clip 2 giây
- [x] Cắt thông minh: không cắt giữa câu thoại
- [x] Offset ±0.3s để giữ trọn vẹn ý nghĩa

**Milestone 3**: Kho >1000 clip 2s, semantic searchable ✅

---

## Phase 4: Đạo Diễn AI (Tuần 9-11)

### Sprint 4.1 — Script Engine (Ngày 41-45)
- [x] Strategy "viral-short": Hook(5s) → Meat(45s) → CTA(10s)
- [x] Gemini prompt engineering

### Sprint 4.2 — Vector Clip Selection (Ngày 46-50)
- [x] `src/remixer/clip_selector.py` — query → vector → top clips
- [x] Visual match: cùng độ sáng, hướng chuyển động

### Sprint 4.3 — RAG Logic (Ngày 51-55)
- [x] Gemini chọn clips mượt nhất từ candidates
- [x] Validate: không trùng clip, duration ≈ target

**Milestone 4**: AI tự viết kịch bản → tự chọn clip ✅

---

## Phase 5: Render & Hoàn Thiện (Tuần 12-14)

### Sprint 5.1 — Audio Engineering (Ngày 56-60)
- [x] `src/remixer/audio_engine.py` — J-cut, L-cut
- [x] Smart BGM ducking: hạ nhạc khi có giọng nói

### Sprint 5.2 — Visual Polish (Ngày 61-65)
- [x] `src/remixer/color_grading.py` — LUT presets
- [x] Xfade transitions, auto color match

### Sprint 5.3 — Final Render (Ngày 66-70)
- [x] Full pipeline: clips → audio → color → BGM → subtitle → output
- [x] Hardware acceleration (NVENC/QSV)
- [x] Preview mode (480p) + Final mode (1080x1920)

**Milestone 5**: Video chuyên nghiệp, sẵn sàng upload ✅

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Twelve Labs pricing change | TB | Cao | LLaVA local fallback |
| Gemini rate limit | Thấp | TB | Ollama/OpenAI fallback |
| ChromaDB scale >100K | TB | TB | Migration → Milvus |
| yt-dlp bị block | Cao | Cao | Auto-update, cookies, proxy |
| Copyright detection | TB | Cao | Transformation + unique remix |

---

## KPIs v2.0

| Metric | Target |
|--------|--------|
| Download success rate | > 95% |
| Clip search accuracy | > 85% |
| Remix coherence | 9/10 |
| Cost per remix (after 100 vids) | < $0.10 |
| Pipeline time (10 videos) | < 15 min |
| Clip library reuse rate | > 60% |
| Audio continuity | Seamless (J/L-cut) |
