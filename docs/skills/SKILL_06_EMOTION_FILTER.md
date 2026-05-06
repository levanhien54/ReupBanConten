# Skill 06: Phát Hiện & Loại Bỏ Đoạn Video Cảm Xúc Đều Đều

## Mục Tiêu
Phát hiện các đoạn video có cảm xúc đơn điệu (monotone), năng lượng thấp, không có biến đổi
→ Loại bỏ TRƯỚC KHI gửi cho LLM phân tích → Tiết kiệm token + tăng chất lượng remix.

## Tại Sao Cần Bước Này?
- LLM tốn token xử lý transcript dài, nếu loại đoạn nhàm chán trước → **tiết kiệm 30-50% token**
- Video remix chỉ giữ đoạn có cảm xúc mạnh → **chất lượng cao hơn**
- Giảm thời gian xử lý pipeline tổng thể

## Kiến Thức Cần Có
- Phân tích audio: `librosa` (pitch, energy, tempo)
- Speech emotion: `speechbrain` hoặc `transformers` (emotion classification)
- Statistical analysis: `numpy` (variance, std deviation)

---

## Pipeline Emotion Filter

```
Video Input
    │
    ▼
┌─────────────────────┐
│  Audio Extraction    │  FFmpeg tách audio từ video
│  (FFmpeg)           │
└─────────┬───────────┘
          │
    ┌─────┼─────────────────────┐
    ▼     ▼                     ▼
┌────────┐ ┌──────────────┐ ┌──────────────┐
│Pitch   │ │Energy/Volume │ │Speech Emotion│
│Analysis│ │Analysis      │ │Classification│
│(librosa)│ │(librosa)     │ │(speechbrain) │
└────┬───┘ └──────┬───────┘ └──────┬───────┘
     │            │                │
     └────────────┼────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Flatness Score  │  Tính điểm "đều đều" cho từng segment
         │ Calculator      │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ Filter Decision │  Score > threshold → LOẠI BỎ
         │                 │  Score < threshold → GIỮ LẠI
         └────────┬───────┘
                  │
                  ▼
         Filtered Segments → Gửi cho LLM
```

---

## Bước 1: Trích Xuất Audio Features

### Audio extraction
```python
import subprocess
import os

def extract_audio(video_path: str, output_path: str = None) -> str:
    """Tách audio từ video bằng FFmpeg."""
    if output_path is None:
        output_path = video_path.rsplit('.', 1)[0] + '_audio.wav'
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vn',                    # Bỏ video
        '-acodec', 'pcm_s16le',   # WAV format
        '-ar', '16000',           # 16kHz (tối ưu cho speech)
        '-ac', '1',               # Mono
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path
```

### Phân tích pitch, energy, tempo
```python
import librosa
import numpy as np

class AudioFeatureExtractor:
    """Trích xuất audio features để phát hiện đoạn cảm xúc đều đều."""
    
    def __init__(self, sr: int = 16000, segment_duration: float = 3.0):
        """
        Args:
            sr: Sample rate
            segment_duration: Chia audio thành segments N giây
        """
        self.sr = sr
        self.segment_duration = segment_duration
    
    def extract_features(self, audio_path: str) -> list[dict]:
        """Trích xuất features cho từng segment."""
        y, sr = librosa.load(audio_path, sr=self.sr)
        total_duration = len(y) / sr
        
        segment_samples = int(self.segment_duration * sr)
        segments = []
        
        for i in range(0, len(y), segment_samples):
            chunk = y[i:i + segment_samples]
            if len(chunk) < sr:  # Skip nếu < 1 giây
                continue
            
            start_time = i / sr
            end_time = min((i + segment_samples) / sr, total_duration)
            
            features = {
                'start_time': round(start_time, 2),
                'end_time': round(end_time, 2),
                'duration': round(end_time - start_time, 2),
            }
            
            # 1. PITCH (F0) Analysis
            features.update(self._analyze_pitch(chunk, sr))
            
            # 2. ENERGY (RMS) Analysis
            features.update(self._analyze_energy(chunk, sr))
            
            # 3. TEMPO / RHYTHM Analysis
            features.update(self._analyze_tempo(chunk, sr))
            
            # 4. SPECTRAL Analysis
            features.update(self._analyze_spectral(chunk, sr))
            
            # 5. SILENCE Detection
            features.update(self._analyze_silence(chunk, sr))
            
            segments.append(features)
        
        return segments
    
    def _analyze_pitch(self, chunk: np.ndarray, sr: int) -> dict:
        """Phân tích pitch - giọng nói đều đều = pitch variance thấp."""
        f0, voiced_flag, _ = librosa.pyin(
            chunk, fmin=60, fmax=500, sr=sr
        )
        
        # Chỉ lấy voiced frames (có giọng nói)
        voiced_f0 = f0[voiced_flag] if voiced_flag is not None else f0[~np.isnan(f0)]
        
        if len(voiced_f0) < 3:
            return {
                'pitch_mean': 0.0,
                'pitch_std': 0.0,
                'pitch_range': 0.0,
                'pitch_variance_score': 0.0,  # Không có giọng = đều
                'voiced_ratio': 0.0,
            }
        
        return {
            'pitch_mean': float(np.mean(voiced_f0)),
            'pitch_std': float(np.std(voiced_f0)),
            'pitch_range': float(np.ptp(voiced_f0)),  # max - min
            'pitch_variance_score': float(np.std(voiced_f0) / (np.mean(voiced_f0) + 1e-6)),
            'voiced_ratio': float(len(voiced_f0) / len(f0)),
        }
    
    def _analyze_energy(self, chunk: np.ndarray, sr: int) -> dict:
        """Phân tích năng lượng - đều đều = energy ít biến đổi."""
        rms = librosa.feature.rms(y=chunk, frame_length=2048, hop_length=512)[0]
        
        if len(rms) < 2:
            return {'energy_mean': 0.0, 'energy_std': 0.0, 'energy_dynamic_range': 0.0}
        
        rms_db = librosa.amplitude_to_db(rms + 1e-10)
        
        return {
            'energy_mean': float(np.mean(rms_db)),
            'energy_std': float(np.std(rms_db)),
            'energy_dynamic_range': float(np.ptp(rms_db)),  # Dynamic range
            'energy_variance_score': float(np.std(rms_db) / (abs(np.mean(rms_db)) + 1e-6)),
        }
    
    def _analyze_tempo(self, chunk: np.ndarray, sr: int) -> dict:
        """Phân tích nhịp độ nói."""
        onset_env = librosa.onset.onset_strength(y=chunk, sr=sr)
        tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
        
        return {
            'tempo': float(tempo[0]) if len(tempo) > 0 else 0.0,
            'onset_density': float(np.mean(onset_env)),
        }
    
    def _analyze_spectral(self, chunk: np.ndarray, sr: int) -> dict:
        """Phân tích phổ - đều đều = spectral ít thay đổi."""
        spectral_centroid = librosa.feature.spectral_centroid(y=chunk, sr=sr)[0]
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=chunk, sr=sr)[0]
        
        return {
            'spectral_centroid_std': float(np.std(spectral_centroid)),
            'spectral_bandwidth_mean': float(np.mean(spectral_bandwidth)),
        }
    
    def _analyze_silence(self, chunk: np.ndarray, sr: int) -> dict:
        """Phát hiện tỷ lệ im lặng."""
        rms = librosa.feature.rms(y=chunk, frame_length=2048, hop_length=512)[0]
        silence_threshold = 0.01  # RMS threshold
        silent_frames = np.sum(rms < silence_threshold)
        
        return {
            'silence_ratio': float(silent_frames / len(rms)),
        }
```

---

## Bước 2: Tính Điểm "Đều Đều" (Flatness Score)

```python
class EmotionFlatnessScorer:
    """Tính điểm cảm xúc đều đều cho từng segment."""
    
    # Weights cho từng feature (tổng = 1.0)
    WEIGHTS = {
        'pitch_variance': 0.30,      # Quan trọng nhất - giọng monotone
        'energy_dynamic': 0.25,       # Năng lượng không đổi
        'spectral_change': 0.15,      # Âm sắc không đổi
        'silence': 0.15,              # Quá nhiều im lặng
        'onset_density': 0.15,        # Ít thay đổi nhịp
    }
    
    # Thresholds (calibrate theo từng dataset)
    THRESHOLDS = {
        'pitch_variance_low': 0.05,    # Pitch std/mean < 0.05 = monotone
        'energy_dynamic_low': 5.0,     # Dynamic range < 5dB = flat
        'silence_high': 0.6,           # > 60% im lặng
        'onset_density_low': 0.5,      # Onset quá thưa
    }
    
    def calculate_flatness(self, segment: dict) -> dict:
        """
        Tính flatness score cho 1 segment.
        Score 0.0 = rất biến đổi (giữ lại)
        Score 1.0 = rất đều đều (loại bỏ)
        """
        scores = {}
        
        # 1. Pitch monotone score
        pv = segment.get('pitch_variance_score', 0)
        if segment.get('voiced_ratio', 0) < 0.1:
            scores['pitch'] = 0.8  # Gần như không có giọng
        elif pv < self.THRESHOLDS['pitch_variance_low']:
            scores['pitch'] = 1.0 - (pv / self.THRESHOLDS['pitch_variance_low'])
        else:
            scores['pitch'] = max(0, 0.3 - pv)  # Càng biến đổi càng thấp
        
        # 2. Energy flatness score
        dr = segment.get('energy_dynamic_range', 0)
        if dr < self.THRESHOLDS['energy_dynamic_low']:
            scores['energy'] = 1.0 - (dr / self.THRESHOLDS['energy_dynamic_low'])
        else:
            scores['energy'] = max(0, 0.2 - dr / 30.0)
        
        # 3. Spectral change score
        sc_std = segment.get('spectral_centroid_std', 0)
        scores['spectral'] = max(0, 1.0 - sc_std / 500.0)
        
        # 4. Silence score
        sr = segment.get('silence_ratio', 0)
        scores['silence'] = sr if sr > self.THRESHOLDS['silence_high'] else sr * 0.3
        
        # 5. Onset density score
        od = segment.get('onset_density', 0)
        if od < self.THRESHOLDS['onset_density_low']:
            scores['onset'] = 1.0 - (od / self.THRESHOLDS['onset_density_low'])
        else:
            scores['onset'] = 0.0
        
        # Weighted average
        flatness = (
            scores['pitch'] * self.WEIGHTS['pitch_variance'] +
            scores['energy'] * self.WEIGHTS['energy_dynamic'] +
            scores['spectral'] * self.WEIGHTS['spectral_change'] +
            scores['silence'] * self.WEIGHTS['silence'] +
            scores['onset'] * self.WEIGHTS['onset_density']
        )
        
        return {
            **segment,
            'flatness_score': round(min(1.0, max(0.0, flatness)), 3),
            'flatness_details': {k: round(v, 3) for k, v in scores.items()},
            'is_flat': flatness > 0.6,  # Threshold mặc định
        }
```

---

## Bước 3: Speech Emotion Classification (Nâng Cao)

```python
class SpeechEmotionClassifier:
    """Phân loại cảm xúc giọng nói bằng SpeechBrain / Transformers."""
    
    def __init__(self, model_name: str = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"):
        from transformers import pipeline
        self.classifier = pipeline(
            "audio-classification",
            model=model_name,
            device=0  # GPU, dùng -1 cho CPU
        )
    
    def classify_segment(self, audio_path: str, start: float, end: float) -> dict:
        """Phân loại cảm xúc cho 1 đoạn audio."""
        import soundfile as sf
        
        # Đọc đoạn audio
        y, sr = sf.read(audio_path, start=int(start * 16000), 
                         stop=int(end * 16000))
        
        results = self.classifier(y)
        
        # Top emotion
        top = results[0]
        emotions = {r['label']: r['score'] for r in results}
        
        # "Neutral" emotion = đều đều
        neutral_score = emotions.get('neutral', 0) + emotions.get('calm', 0)
        
        return {
            'emotion': top['label'],
            'emotion_confidence': top['score'],
            'all_emotions': emotions,
            'is_neutral': neutral_score > 0.6,
            'emotion_intensity': 1.0 - neutral_score,
        }
```

---

## Bước 4: Emotion Filter Pipeline

```python
class EmotionFilter:
    """Pipeline chính: lọc đoạn cảm xúc đều đều."""
    
    def __init__(self, flatness_threshold: float = 0.6,
                 segment_duration: float = 3.0,
                 use_speech_emotion: bool = False):
        self.threshold = flatness_threshold
        self.extractor = AudioFeatureExtractor(segment_duration=segment_duration)
        self.scorer = EmotionFlatnessScorer()
        self.use_speech_emotion = use_speech_emotion
        
        if use_speech_emotion:
            self.emotion_classifier = SpeechEmotionClassifier()
    
    def filter_video(self, video_path: str) -> dict:
        """
        Lọc video, trả về danh sách segments giữ/bỏ.
        
        Returns:
            {
                'kept_segments': [...],      # Đoạn có cảm xúc → GIỮ
                'removed_segments': [...],   # Đoạn đều đều → BỎ
                'stats': {...}
            }
        """
        # 1. Tách audio
        audio_path = extract_audio(video_path)
        
        # 2. Trích features cho từng segment
        segments = self.extractor.extract_features(audio_path)
        
        # 3. Tính flatness score
        scored_segments = []
        for seg in segments:
            scored = self.scorer.calculate_flatness(seg)
            
            # Optional: speech emotion classification
            if self.use_speech_emotion and scored.get('voiced_ratio', 0) > 0.3:
                emotion = self.emotion_classifier.classify_segment(
                    audio_path, seg['start_time'], seg['end_time']
                )
                scored.update(emotion)
                
                # Kết hợp: nếu emotion=neutral → tăng flatness
                if emotion.get('is_neutral', False):
                    scored['flatness_score'] = min(1.0, 
                        scored['flatness_score'] * 0.6 + 0.4)
            
            scored_segments.append(scored)
        
        # 4. Phân loại giữ/bỏ
        kept = [s for s in scored_segments if s['flatness_score'] < self.threshold]
        removed = [s for s in scored_segments if s['flatness_score'] >= self.threshold]
        
        # 5. Merge adjacent kept segments (tránh cắt quá vụn)
        kept = self._merge_adjacent(kept)
        
        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        total = len(scored_segments)
        return {
            'kept_segments': kept,
            'removed_segments': removed,
            'stats': {
                'total_segments': total,
                'kept_count': len(kept),
                'removed_count': len(removed),
                'kept_ratio': len(kept) / total if total > 0 else 0,
                'avg_flatness': np.mean([s['flatness_score'] for s in scored_segments]),
            }
        }
    
    def _merge_adjacent(self, segments: list[dict], gap: float = 0.5) -> list[dict]:
        """Merge segments liền nhau (gap < 0.5s)."""
        if not segments:
            return []
        
        merged = [segments[0].copy()]
        for seg in segments[1:]:
            prev = merged[-1]
            if seg['start_time'] - prev['end_time'] <= gap:
                # Merge
                prev['end_time'] = seg['end_time']
                prev['duration'] = prev['end_time'] - prev['start_time']
                prev['flatness_score'] = min(prev['flatness_score'], seg['flatness_score'])
            else:
                merged.append(seg.copy())
        
        return merged
    
    def get_filtered_transcript(self, transcript_segments: list[dict],
                                 kept_segments: list[dict]) -> list[dict]:
        """Lọc transcript chỉ giữ phần thuộc kept_segments."""
        filtered = []
        for tseg in transcript_segments:
            for kseg in kept_segments:
                # Overlap check
                if (tseg['start'] < kseg['end_time'] and 
                    tseg['end'] > kseg['start_time']):
                    filtered.append(tseg)
                    break
        return filtered
```

---

## Bước 5: Tích Hợp Vào Pipeline Chính

```python
# TRƯỚC KHI GỬI CHO LLM:
async def analyze_with_emotion_filter(video_path: str, 
                                        transcriber, llm_analyzer):
    """Pipeline: Emotion Filter → Whisper → LLM (chỉ phần hay)."""
    
    # 1. LỌC CẢM XÚC TRƯỚC
    emotion_filter = EmotionFilter(flatness_threshold=0.6)
    filter_result = emotion_filter.filter_video(video_path)
    
    print(f"📊 Emotion Filter: Giữ {filter_result['stats']['kept_count']}/"
          f"{filter_result['stats']['total_segments']} segments "
          f"({filter_result['stats']['kept_ratio']*100:.0f}%)")
    
    # 2. Transcribe toàn bộ
    transcript = transcriber.transcribe(video_path)
    
    # 3. Lọc transcript → chỉ giữ phần có cảm xúc
    filtered_transcript = emotion_filter.get_filtered_transcript(
        transcript['segments'],
        filter_result['kept_segments']
    )
    
    # 4. GỬI CHO LLM chỉ phần đã lọc (tiết kiệm token!)
    filtered_text = ' '.join([s['text'] for s in filtered_transcript])
    analysis = await llm_analyzer.analyze(
        {'segments': filtered_transcript, 'full_text': filtered_text},
        video_metadata
    )
    
    # 5. Đính kèm filter info vào analysis
    analysis['emotion_filter'] = filter_result['stats']
    analysis['filtered_segments'] = filter_result['kept_segments']
    
    return analysis
```

---

## Cấu Hình

```yaml
# Thêm vào config/settings.yaml
emotion_filter:
  enabled: true
  flatness_threshold: 0.6    # 0.0-1.0 (cao = strict, loại nhiều hơn)
  segment_duration: 3.0       # Chia video thành chunks N giây
  use_speech_emotion: false   # Dùng ML classifier (chậm hơn, chính xác hơn)
  
  # Feature weights
  weights:
    pitch_variance: 0.30
    energy_dynamic: 0.25
    spectral_change: 0.15
    silence: 0.15
    onset_density: 0.15
  
  # Thresholds
  thresholds:
    pitch_variance_low: 0.05
    energy_dynamic_low: 5.0
    silence_high: 0.6
    onset_density_low: 0.5
```

---

## Dependencies Bổ Sung

```
# Thêm vào requirements.txt
librosa>=0.10.0              # Audio analysis
soundfile>=0.12.0            # Audio I/O
# speechbrain>=1.0.0         # Speech emotion (optional, heavy)
# transformers>=4.40.0       # HuggingFace models (optional)
```

---

## Test

```python
def test_emotion_filter():
    ef = EmotionFilter(flatness_threshold=0.6)
    result = ef.filter_video("test_video.mp4")
    
    assert 'kept_segments' in result
    assert 'removed_segments' in result
    assert result['stats']['total_segments'] > 0
    assert all(s['flatness_score'] < 0.6 for s in result['kept_segments'])
    assert all(s['flatness_score'] >= 0.6 for s in result['removed_segments'])

def test_flatness_scorer():
    scorer = EmotionFlatnessScorer()
    
    # Đoạn monotone
    flat_seg = {'pitch_variance_score': 0.02, 'energy_dynamic_range': 3.0,
                'spectral_centroid_std': 50, 'silence_ratio': 0.1,
                'onset_density': 0.3, 'voiced_ratio': 0.5}
    result = scorer.calculate_flatness(flat_seg)
    assert result['flatness_score'] > 0.5  # Phải bị đánh giá là flat
    
    # Đoạn sôi động
    lively_seg = {'pitch_variance_score': 0.2, 'energy_dynamic_range': 20.0,
                  'spectral_centroid_std': 400, 'silence_ratio': 0.05,
                  'onset_density': 2.0, 'voiced_ratio': 0.8}
    result = scorer.calculate_flatness(lively_seg)
    assert result['flatness_score'] < 0.3  # Phải bị đánh giá là lively
```
