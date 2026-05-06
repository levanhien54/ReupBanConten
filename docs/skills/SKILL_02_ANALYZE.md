# Skill 02: AI Video Analysis (Whisper + LLM)

## Mục Tiêu
Phân tích nội dung video: trích transcript, phân tích chủ đề/mood/highlights bằng LLM.

## Kiến Thức Cần Có
- faster-whisper cho transcription
- Ollama / OpenAI API cho LLM
- Kỹ thuật prompt engineering
- Map-Reduce cho long content

---

## Bước 1: Trích Xuất Transcript (Whisper)

### Setup faster-whisper
```python
from faster_whisper import WhisperModel

class Transcriber:
    def __init__(self, model_size: str = "large-v3", device: str = "cuda"):
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type="float16" if device == "cuda" else "int8"
        )
    
    def transcribe(self, audio_path: str, language: str = None) -> dict:
        """Transcribe audio/video file với timestamps."""
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,           # Lọc khoảng im lặng
            word_timestamps=True,       # Timestamp từng từ
        )
        
        result_segments = []
        full_text_parts = []
        word_timestamps = []
        
        for segment in segments:
            result_segments.append({
                'start': round(segment.start, 2),
                'end': round(segment.end, 2),
                'text': segment.text.strip(),
            })
            full_text_parts.append(segment.text.strip())
            
            # Word-level timestamps
            if segment.words:
                for word in segment.words:
                    word_timestamps.append({
                        'word': word.word.strip(),
                        'start': round(word.start, 2),
                        'end': round(word.end, 2),
                        'probability': round(word.probability, 3),
                    })
        
        return {
            'full_text': ' '.join(full_text_parts),
            'segments': result_segments,
            'word_timestamps': word_timestamps,
            'language': info.language,
            'language_probability': round(info.language_probability, 3),
            'duration': info.duration,
        }
```

### Transcript có timestamp format
```python
def format_timestamped_transcript(segments: list[dict]) -> str:
    """Format transcript với timestamps cho LLM."""
    lines = []
    for seg in segments:
        start = format_time(seg['start'])
        end = format_time(seg['end'])
        lines.append(f"[{start} - {end}] {seg['text']}")
    return '\n'.join(lines)

def format_time(seconds: float) -> str:
    """Convert seconds to MM:SS.ms format."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins:02d}:{secs:05.2f}"
```

---

## Bước 2: Tích Hợp LLM

### Provider abstraction
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, temperature: float = 0.3) -> str:
        pass

class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        import ollama
        self.client = ollama.AsyncClient(host=base_url)
        self.model = model
    
    async def generate(self, prompt: str, temperature: float = 0.3) -> str:
        response = await self.client.generate(
            model=self.model,
            prompt=prompt,
            options={'temperature': temperature, 'num_predict': 4096}
        )
        return response['response']

class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def generate(self, prompt: str, temperature: float = 0.3) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=4096,
        )
        return response.choices[0].message.content
```

---

## Bước 3: Phân Tích Nội Dung

### LLM Analyzer
```python
import json
import re

class LLMAnalyzer:
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.prompt_template = self._load_prompt('analyze_content')
    
    async def analyze(self, transcript: dict, metadata: dict) -> dict:
        """Phân tích video bằng LLM."""
        
        # Format transcript
        formatted = format_timestamped_transcript(transcript['segments'])
        
        # Build prompt
        prompt = self.prompt_template.format(
            transcript=formatted,
            title=metadata.get('title', ''),
            description=metadata.get('description', '')[:500],
            duration=transcript.get('duration', 0),
        )
        
        # Call LLM
        response = await self.provider.generate(prompt, temperature=0.3)
        
        # Parse JSON response
        return self._parse_json(response)
    
    def _parse_json(self, response: str) -> dict:
        """Parse JSON từ LLM response."""
        # Thử parse trực tiếp
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Tìm JSON trong markdown code block
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Tìm {...}
        match = re.search(r'(\{[\s\S]*\})', response)
        if match:
            return json.loads(match.group(1))
        
        raise ValueError(f"Cannot parse JSON: {response[:200]}")
    
    def _load_prompt(self, name: str) -> str:
        """Load prompt template từ file."""
        path = f"config/prompts/{name}.txt"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
```

---

## Bước 4: Map-Reduce cho Video Dài

```python
class MapReduceAnalyzer:
    """Phân tích video dài bằng kỹ thuật map-reduce."""
    
    def __init__(self, provider: LLMProvider, chunk_size: int = 3000):
        self.provider = provider
        self.chunk_size = chunk_size
    
    async def analyze_long(self, transcript: dict, metadata: dict) -> dict:
        """Phân tích video dài bằng map-reduce."""
        full_text = transcript['full_text']
        
        # Nếu đủ ngắn, phân tích trực tiếp
        if len(full_text) < self.chunk_size:
            analyzer = LLMAnalyzer(self.provider)
            return await analyzer.analyze(transcript, metadata)
        
        # MAP: Chia thành chunks và tóm tắt từng chunk
        chunks = self._split_chunks(transcript['segments'])
        summaries = []
        
        for i, chunk in enumerate(chunks):
            summary = await self._summarize_chunk(chunk, i, len(chunks))
            summaries.append(summary)
        
        # REDUCE: Tổng hợp tất cả summaries
        return await self._reduce_summaries(summaries, metadata)
    
    def _split_chunks(self, segments: list[dict]) -> list[list[dict]]:
        """Chia segments thành chunks có kích thước phù hợp."""
        chunks = []
        current_chunk = []
        current_length = 0
        
        for seg in segments:
            seg_length = len(seg['text'])
            if current_length + seg_length > self.chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_length = 0
            current_chunk.append(seg)
            current_length += seg_length
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    async def _summarize_chunk(self, chunk: list[dict], 
                                index: int, total: int) -> dict:
        """Tóm tắt 1 chunk."""
        formatted = format_timestamped_transcript(chunk)
        prompt = f"""Tóm tắt đoạn transcript {index+1}/{total} trong 3-5 points.
Giữ lại timestamps quan trọng.

Transcript:
{formatted}

Trả về JSON:
{{"summary_points": [...], "key_timestamps": [...], "dominant_mood": "...", "energy_range": [min, max]}}"""
        
        response = await self.provider.generate(prompt, temperature=0.3)
        return json.loads(response)
    
    async def _reduce_summaries(self, summaries: list[dict], 
                                 metadata: dict) -> dict:
        """Tổng hợp các summaries thành phân tích cuối."""
        prompt = f"""Tổng hợp các phân tích sau thành 1 phân tích hoàn chỉnh.

Video: {metadata.get('title', '')}

Summaries:
{json.dumps(summaries, ensure_ascii=False, indent=2)}

Trả về JSON hoàn chỉnh với: topics, mood, category, summary, key_moments, overall_energy, viral_potential"""
        
        response = await self.provider.generate(prompt, temperature=0.3)
        return json.loads(response)
```

---

## Test

```python
# test_analyzer.py
import asyncio

async def test_transcribe():
    t = Transcriber(model_size="base", device="cpu")
    result = t.transcribe("test_audio.mp3")
    assert result['full_text']
    assert len(result['segments']) > 0

async def test_llm_analyze():
    provider = OllamaProvider(model="llama3")
    analyzer = LLMAnalyzer(provider)
    
    transcript = {'segments': [{'start': 0, 'end': 5, 'text': 'Hello world'}]}
    metadata = {'title': 'Test', 'description': 'Test video'}
    
    result = await analyzer.analyze(transcript, metadata)
    assert 'topics' in result
    assert 'mood' in result
```
