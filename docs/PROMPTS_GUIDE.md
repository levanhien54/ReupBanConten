# 🎯 Prompt Engineering Guide - ReupBanConten

Tài liệu này mô tả chiến lược prompt cho từng bước trong pipeline.

---

## Nguyên Tắc Chung

1. **Luôn yêu cầu output JSON** — dễ parse, ổn định
2. **Cho ví dụ (few-shot)** — LLM hiểu rõ format mong muốn
3. **Giới hạn scope** — 1 prompt = 1 nhiệm vụ cụ thể
4. **Temperature thấp (0.2-0.4)** — cho kết quả nhất quán
5. **Fallback prompt** — prompt đơn giản hơn nếu prompt chính thất bại

---

## Prompt 1: Phân Tích Nội Dung Video

**File**: `config/prompts/analyze_content.txt`  
**Dùng tại**: `analyzer/llm_analyzer.py`

```
Bạn là chuyên gia phân tích nội dung video. Phân tích transcript sau đây và trả về JSON.

## Transcript:
{transcript}

## Metadata:
- Tiêu đề: {title}
- Mô tả: {description}
- Thời lượng: {duration}s

## Yêu cầu:
Trả về JSON với cấu trúc:
{
  "topics": ["chủ đề 1", "chủ đề 2"],
  "mood": "happy|sad|exciting|calm|funny|dramatic|neutral",
  "category": "entertainment|education|gaming|music|comedy|lifestyle|news|tech|sports",
  "summary": "Tóm tắt nội dung trong 2-3 câu",
  "language": "vi|en|other",
  "has_speech": true|false,
  "key_moments": [
    {
      "start_time": 0.0,
      "end_time": 10.5,
      "description": "Mô tả đoạn này",
      "energy_score": 0.8,
      "is_highlight": true
    }
  ],
  "overall_energy": 0.7,
  "viral_potential": 0.6
}

CHỈ trả về JSON, không thêm text nào khác.
```

---

## Prompt 2: Chọn Highlight Clips

**File**: `config/prompts/select_highlights.txt`  
**Dùng tại**: `cutter/smart_clipper.py`

```
Bạn là editor video chuyên nghiệp. Dựa trên phân tích sau, chọn các đoạn HAY NHẤT để cắt thành clips ngắn.

## Phân tích video:
{analysis_json}

## Transcript có timestamp:
{timestamped_transcript}

## Quy tắc:
- Mỗi clip tối thiểu {min_duration}s, tối đa {max_duration}s
- Ưu tiên đoạn có energy cao, nội dung hấp dẫn
- Tránh cắt giữa câu nói
- Chọn điểm cắt tự nhiên (pause, chuyển cảnh)
- Chọn tối đa {max_clips} clips

## Trả về JSON:
{
  "clips": [
    {
      "start_time": 5.2,
      "end_time": 18.7,
      "reason": "Đoạn climax, energy cao nhất",
      "highlight_score": 0.95,
      "tags": ["exciting", "peak", "action"],
      "mood": "exciting",
      "energy_level": "peak",
      "content_type": "action"
    }
  ]
}

CHỈ trả về JSON.
```

---

## Prompt 3: Tạo Kịch Bản Remix

**File**: `config/prompts/create_remix_script.txt`  
**Dùng tại**: `remixer/script_generator.py`

```
Bạn là đạo diễn video sáng tạo. Tạo kịch bản remix từ các clips có sẵn.

## Chiến lược remix: {strategy}
## Thời lượng mong muốn: {target_duration}s

## Danh sách clips có sẵn:
{clips_json}

## Chiến lược chi tiết:
- topic-based: Nhóm clips cùng chủ đề
- energy-flow: Sắp xếp low → high → low energy
- narrative: Tạo câu chuyện mạch lạc
- random-creative: Trộn sáng tạo với transitions đa dạng
- best-of: Chỉ top highlights

## Trả về JSON:
{
  "title": "Tên video remix",
  "description": "Mô tả ngắn",
  "sequence": [
    {
      "clip_id": 1,
      "transition_in": "fade",
      "transition_duration": 0.5,
      "speed_factor": 1.0,
      "notes": "Mở đầu nhẹ nhàng"
    }
  ],
  "estimated_duration": 58.5,
  "mood_flow": "calm → exciting → peak → calm",
  "suggested_music_mood": "upbeat electronic"
}

CHỈ trả về JSON.
```

---

## Prompt 4: Map-Reduce Summary (cho video dài)

**File**: `config/prompts/summarize_chunk.txt`

```
Tóm tắt đoạn transcript sau trong 3-5 bullet points.
Giữ lại các timestamps quan trọng.

## Transcript đoạn {chunk_index}/{total_chunks}:
{chunk_text}

Trả về JSON:
{
  "summary_points": ["point 1", "point 2"],
  "key_timestamps": [
    {"time": 15.3, "event": "Điểm thú vị"}
  ],
  "dominant_mood": "exciting",
  "energy_range": [0.3, 0.9]
}
```

---

## Xử Lý Response LLM

### Parse JSON an toàn

```python
import json
import re

def safe_parse_llm_json(response: str) -> dict:
    """Parse JSON từ LLM response, xử lý các trường hợp lỗi."""
    # Thử parse trực tiếp
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # Tìm JSON block trong markdown
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Tìm {...} hoặc [...]
    json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Cannot parse JSON from LLM response: {response[:200]}")
```

### Retry Strategy

```python
MAX_RETRIES = 3
FALLBACK_TEMPS = [0.3, 0.5, 0.7]

async def llm_with_retry(prompt, provider, retries=MAX_RETRIES):
    for i in range(retries):
        try:
            response = await provider.generate(
                prompt, 
                temperature=FALLBACK_TEMPS[i]
            )
            return safe_parse_llm_json(response)
        except (ValueError, TimeoutError) as e:
            if i == retries - 1:
                raise
            logger.warning(f"Retry {i+1}/{retries}: {e}")
```
