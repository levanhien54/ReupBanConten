"""
Emotion Filter — Lọc bỏ các đoạn video/âm thanh có cảm xúc đều đều.
Sử dụng librosa.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any

import numpy as np

from src.core.config import EmotionFilterConfig
from src.core.logging import get_logger, log_duration
from src.core.types import EmotionFeatures, FilterResult

logger = get_logger(__name__)


class EmotionFilter:
    """Phát hiện và lọc các đoạn cảm xúc đơn điệu."""

    def __init__(self, config: EmotionFilterConfig) -> None:
        self._config = config
        self._sr = 16000

    def extract_audio(self, video_path: str, output_path: str) -> str:
        """Tách audio từ video."""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(self._sr),
            "-ac", "1",
            output_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to extract audio: {e.stderr.decode()}")
            raise
        return output_path

    @log_duration(msg_template="Emotion filtering {func_name}")
    def filter_video(self, video_path: str) -> FilterResult:
        """Phân tích và lọc video."""
        if not self._config.enabled:
            return FilterResult()

        try:
            import librosa
        except ImportError:
            logger.warning("librosa not installed. Emotion filter disabled.")
            return FilterResult()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.wav")
            self.extract_audio(video_path, audio_path)

            try:
                y, sr = librosa.load(audio_path, sr=self._sr)
            except Exception as e:
                logger.error(f"Failed to load audio with librosa: {e}")
                return FilterResult()

            total_duration = len(y) / sr
            segment_samples = int(self._config.segment_duration * sr)
            
            scored_segments = []

            for i in range(0, len(y), segment_samples):
                chunk = y[i:i + segment_samples]
                if len(chunk) < sr:
                    continue

                start_time = i / sr
                end_time = min((i + segment_samples) / sr, total_duration)

                features = self._analyze_chunk(chunk, sr)
                features["start_time"] = round(start_time, 2)
                features["end_time"] = round(end_time, 2)
                features["duration"] = round(end_time - start_time, 2)
                
                scored_features = self._calculate_score(features)
                scored_segments.append(EmotionFeatures(**scored_features))

            kept = [s for s in scored_segments if not s.is_flat]
            removed = [s for s in scored_segments if s.is_flat]

            return FilterResult(
                kept_segments=self._merge_adjacent(kept),
                removed_segments=self._merge_adjacent(removed),
                total_segments=len(scored_segments),
                kept_count=len(kept),
                removed_count=len(removed),
                kept_ratio=len(kept) / max(len(scored_segments), 1),
                avg_flatness=float(np.mean([s.flatness_score for s in scored_segments])) if scored_segments else 0.0,
            )

    def _analyze_chunk(self, chunk: np.ndarray, sr: int) -> dict[str, Any]:
        """Trích xuất features từ 1 chunk audio."""
        import librosa
        features = {}

        # Pitch
        f0, voiced_flag, _ = librosa.pyin(chunk, fmin=60, fmax=500, sr=sr)
        voiced_f0 = f0[voiced_flag] if voiced_flag is not None else f0[~np.isnan(f0)]
        
        if len(voiced_f0) >= 3:
            features["pitch_mean"] = float(np.mean(voiced_f0))
            features["pitch_std"] = float(np.std(voiced_f0))
            features["pitch_range"] = float(np.ptp(voiced_f0))
            features["pitch_variance_score"] = float(np.std(voiced_f0) / (np.mean(voiced_f0) + 1e-6))
            features["voiced_ratio"] = float(len(voiced_f0) / len(f0))
        else:
            features.update({"pitch_mean": 0.0, "pitch_std": 0.0, "pitch_range": 0.0, "pitch_variance_score": 0.0, "voiced_ratio": 0.0})

        # Energy
        rms = librosa.feature.rms(y=chunk, frame_length=2048, hop_length=512)[0]
        if len(rms) >= 2:
            rms_db = librosa.amplitude_to_db(rms + 1e-10)
            features["energy_mean"] = float(np.mean(rms_db))
            features["energy_std"] = float(np.std(rms_db))
            features["energy_dynamic_range"] = float(np.ptp(rms_db))
            features["energy_variance_score"] = float(np.std(rms_db) / (abs(np.mean(rms_db)) + 1e-6))
            features["silence_ratio"] = float(np.sum(rms < 0.01) / len(rms))
        else:
            features.update({"energy_mean": 0.0, "energy_std": 0.0, "energy_dynamic_range": 0.0, "energy_variance_score": 0.0, "silence_ratio": 0.0})

        # Spectral
        try:
            sc = librosa.feature.spectral_centroid(y=chunk, sr=sr)[0]
            sb = librosa.feature.spectral_bandwidth(y=chunk, sr=sr)[0]
            features["spectral_centroid_std"] = float(np.std(sc))
            features["spectral_bandwidth_mean"] = float(np.mean(sb))
        except Exception:
            features.update({"spectral_centroid_std": 0.0, "spectral_bandwidth_mean": 0.0})

        # Tempo / Onset
        try:
            onset_env = librosa.onset.onset_strength(y=chunk, sr=sr)
            tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
            features["tempo"] = float(tempo[0]) if len(tempo) > 0 else 0.0
            features["onset_density"] = float(np.mean(onset_env))
        except Exception:
            features.update({"tempo": 0.0, "onset_density": 0.0})

        return features

    def _calculate_score(self, features: dict[str, Any]) -> dict[str, Any]:
        """Tính điểm flatness."""
        weights = {
            "pitch": 0.30,
            "energy": 0.25,
            "spectral": 0.15,
            "silence": 0.15,
            "onset": 0.15,
        }
        
        # Calculate individual scores
        scores = {}
        
        pv = features.get("pitch_variance_score", 0)
        if features.get("voiced_ratio", 0) < 0.1:
            scores["pitch"] = 0.8
        elif pv < 0.05:
            scores["pitch"] = 1.0 - (pv / 0.05)
        else:
            scores["pitch"] = max(0.0, 0.3 - pv)
            
        dr = features.get("energy_dynamic_range", 0)
        if dr < 5.0:
            scores["energy"] = 1.0 - (dr / 5.0)
        else:
            scores["energy"] = max(0.0, 0.2 - dr / 30.0)
            
        sc_std = features.get("spectral_centroid_std", 0)
        scores["spectral"] = max(0.0, 1.0 - sc_std / 500.0)
        
        sr = features.get("silence_ratio", 0)
        scores["silence"] = sr if sr > 0.6 else sr * 0.3
        
        od = features.get("onset_density", 0)
        if od < 0.5:
            scores["onset"] = 1.0 - (od / 0.5)
        else:
            scores["onset"] = 0.0
            
        flatness = (
            scores["pitch"] * weights["pitch"] +
            scores["energy"] * weights["energy"] +
            scores["spectral"] * weights["spectral"] +
            scores["silence"] * weights["silence"] +
            scores["onset"] * weights["onset"]
        )
        
        features["flatness_score"] = round(min(1.0, max(0.0, flatness)), 3)
        features["is_flat"] = features["flatness_score"] > self._config.flatness_threshold
        
        return features

    def _merge_adjacent(self, segments: list[EmotionFeatures], gap: float = 0.5) -> list[EmotionFeatures]:
        if not segments:
            return []
        
        merged = [segments[0].model_copy()]
        for seg in segments[1:]:
            prev = merged[-1]
            if seg.start_time - prev.end_time <= gap:
                prev.end_time = seg.end_time
                prev.duration = prev.end_time - prev.start_time
                prev.flatness_score = min(prev.flatness_score, seg.flatness_score)
            else:
                merged.append(seg.model_copy())
        
        return merged
