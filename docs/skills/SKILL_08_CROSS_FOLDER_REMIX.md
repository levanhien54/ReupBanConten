# Skill 08: Chuyển Cảnh Chính Xác, Loại Khung Đen & Cross-Folder Remix

## Mục Tiêu
1. Phát hiện chuyển cảnh chính xác nhất (multi-method detection)
2. Loại bỏ khung hình đen/chớp nháy (black frame & flash removal)
3. Cắt video thành segments → lưu vào folder cùng tên video gốc
4. LLM nhận danh sách folders → trộn segments từ NHIỀU folder → video mới (cân bằng)

---

## Pipeline Tổng Quan

```
Video gốc A, B, C...
       │
       ▼
┌──────────────────────┐
│ 1. Scene Detection    │  Phát hiện chuyển cảnh (multi-method)
│    (chính xác nhất)   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. Black/Flash Filter │  Loại bỏ khung hình đen, chớp nháy
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. Cut → Folders      │  Cắt segments → folder theo tên video
│                        │
│  data/segments/        │
│  ├── VideoA/           │  Video A: segment_001.mp4, segment_002.mp4...
│  ├── VideoB/           │  Video B: segment_001.mp4, segment_002.mp4...
│  └── VideoC/           │  Video C: ...
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. LLM Cross-Folder   │  LLM chọn segments từ NHIỀU folders
│    Remix               │  Không lấy quá nhiều từ 1 folder
│                        │  Trộn đều → video mới
└──────────────────────┘
```

---

## Bước 1: Phát Hiện Chuyển Cảnh Chính Xác (Multi-Method)

```python
import cv2
import numpy as np
from scenedetect import detect, ContentDetector, ThresholdDetector, AdaptiveDetector
from scenedetect import open_video

class PreciseSceneDetector:
    """Phát hiện chuyển cảnh đa phương pháp để đạt độ chính xác cao nhất."""
    
    def __init__(self, 
                 content_threshold: float = 27.0,
                 adaptive_threshold: float = 3.5,
                 hist_threshold: float = 0.5,
                 min_scene_len: float = 1.0):
        self.content_threshold = content_threshold
        self.adaptive_threshold = adaptive_threshold
        self.hist_threshold = hist_threshold
        self.min_scene_len = min_scene_len
    
    def detect_all(self, video_path: str) -> list[dict]:
        """
        Phát hiện chuyển cảnh bằng 3 phương pháp, lấy consensus.
        
        Returns:
            list of {start_time, end_time, duration, confidence, method}
        """
        # Method 1: Content-based (thay đổi pixel/edge)
        content_scenes = self._detect_content(video_path)
        
        # Method 2: Adaptive (thích ứng với video có ánh sáng thay đổi)
        adaptive_scenes = self._detect_adaptive(video_path)
        
        # Method 3: Histogram comparison (so sánh phân bố màu)
        hist_scenes = self._detect_histogram(video_path)
        
        # Consensus: merge kết quả, ưu tiên điểm được ≥2 methods đồng ý
        merged = self._consensus_merge(
            content_scenes, adaptive_scenes, hist_scenes,
            tolerance=0.5  # 0.5 giây tolerance
        )
        
        return merged
    
    def _detect_content(self, video_path: str) -> list[float]:
        """PySceneDetect Content-based."""
        scenes = detect(video_path, ContentDetector(
            threshold=self.content_threshold,
            min_scene_len=int(self.min_scene_len * 30)
        ))
        return [s[0].get_seconds() for s in scenes]
    
    def _detect_adaptive(self, video_path: str) -> list[float]:
        """PySceneDetect Adaptive."""
        scenes = detect(video_path, AdaptiveDetector(
            adaptive_threshold=self.adaptive_threshold,
            min_scene_len=int(self.min_scene_len * 30)
        ))
        return [s[0].get_seconds() for s in scenes]
    
    def _detect_histogram(self, video_path: str) -> list[float]:
        """OpenCV histogram comparison - chính xác cho hard cuts."""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        prev_hist = None
        scene_cuts = []
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Tính histogram HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], 
                               [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            
            if prev_hist is not None:
                # So sánh với frame trước
                score = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                
                if score < self.hist_threshold:  # Khác biệt lớn = chuyển cảnh
                    time = frame_idx / fps
                    scene_cuts.append(time)
            
            prev_hist = hist
            frame_idx += 1
        
        cap.release()
        return scene_cuts
    
    def _consensus_merge(self, *scene_lists, tolerance: float = 0.5) -> list[dict]:
        """
        Merge kết quả từ nhiều methods.
        Điểm cắt được ≥2 methods đồng ý → confidence cao.
        """
        # Gom tất cả cut points
        all_cuts = []
        for method_idx, cuts in enumerate(scene_lists):
            method_name = ['content', 'adaptive', 'histogram'][method_idx]
            for t in cuts:
                all_cuts.append({'time': t, 'method': method_name})
        
        all_cuts.sort(key=lambda x: x['time'])
        
        # Cluster các cuts gần nhau
        clusters = []
        current_cluster = [all_cuts[0]] if all_cuts else []
        
        for cut in all_cuts[1:]:
            if cut['time'] - current_cluster[-1]['time'] <= tolerance:
                current_cluster.append(cut)
            else:
                clusters.append(current_cluster)
                current_cluster = [cut]
        if current_cluster:
            clusters.append(current_cluster)
        
        # Tạo scene boundaries với confidence
        scene_boundaries = []
        for cluster in clusters:
            methods_agreed = len(set(c['method'] for c in cluster))
            avg_time = np.mean([c['time'] for c in cluster])
            
            scene_boundaries.append({
                'cut_time': round(avg_time, 3),
                'confidence': methods_agreed / 3.0,  # 0.33, 0.67, 1.0
                'methods': list(set(c['method'] for c in cluster)),
                'methods_count': methods_agreed,
            })
        
        # Tạo segments từ boundaries
        segments = []
        prev_time = 0.0
        for i, boundary in enumerate(scene_boundaries):
            segments.append({
                'index': i,
                'start_time': round(prev_time, 3),
                'end_time': round(boundary['cut_time'], 3),
                'duration': round(boundary['cut_time'] - prev_time, 3),
                'confidence': boundary['confidence'],
                'methods': boundary['methods'],
            })
            prev_time = boundary['cut_time']
        
        return segments
```

---

## Bước 2: Loại Bỏ Khung Hình Đen & Chớp Nháy

```python
class BlackFlashFilter:
    """Phát hiện và loại bỏ segments có khung hình đen hoặc chớp nháy."""
    
    def __init__(self, 
                 black_threshold: float = 15.0,
                 black_ratio: float = 0.7,
                 flash_threshold: float = 100.0,
                 min_segment_duration: float = 0.5):
        """
        Args:
            black_threshold: Pixel intensity dưới mức này = đen (0-255)
            black_ratio: Tỷ lệ frames đen trong segment > ratio = loại
            flash_threshold: Chênh lệch brightness giữa 2 frames > threshold = flash
            min_segment_duration: Segment ngắn hơn N giây = loại
        """
        self.black_threshold = black_threshold
        self.black_ratio = black_ratio
        self.flash_threshold = flash_threshold
        self.min_segment_duration = min_segment_duration
    
    def analyze_segment(self, video_path: str, 
                         start: float, end: float) -> dict:
        """Phân tích 1 segment: có bị đen/flash không."""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        start_frame = int(start * fps)
        end_frame = int(end * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        brightness_values = []
        black_frames = 0
        flash_count = 0
        total_frames = 0
        prev_brightness = None
        
        for i in range(end_frame - start_frame):
            ret, frame = cap.read()
            if not ret:
                break
            
            # Tính brightness trung bình
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))
            brightness_values.append(brightness)
            
            # Check black frame
            if brightness < self.black_threshold:
                black_frames += 1
            
            # Check flash (thay đổi brightness đột ngột)
            if prev_brightness is not None:
                diff = abs(brightness - prev_brightness)
                if diff > self.flash_threshold:
                    flash_count += 1
            
            prev_brightness = brightness
            total_frames += 1
        
        cap.release()
        
        if total_frames == 0:
            return {'is_bad': True, 'reason': 'no_frames'}
        
        black_ratio = black_frames / total_frames
        flash_rate = flash_count / total_frames
        duration = end - start
        
        # Quyết định loại bỏ
        is_bad = False
        reasons = []
        
        if black_ratio > self.black_ratio:
            is_bad = True
            reasons.append(f'black_frames:{black_ratio:.0%}')
        
        if flash_rate > 0.15:  # > 15% frames bị flash
            is_bad = True
            reasons.append(f'flash:{flash_rate:.0%}')
        
        if duration < self.min_segment_duration:
            is_bad = True
            reasons.append(f'too_short:{duration:.1f}s')
        
        return {
            'is_bad': is_bad,
            'reasons': reasons,
            'black_ratio': round(black_ratio, 3),
            'flash_rate': round(flash_rate, 3),
            'flash_count': flash_count,
            'avg_brightness': round(float(np.mean(brightness_values)), 1),
            'brightness_std': round(float(np.std(brightness_values)), 1),
            'duration': round(duration, 3),
        }
    
    def filter_segments(self, video_path: str, 
                         segments: list[dict]) -> tuple[list, list]:
        """
        Lọc segments: loại bỏ đoạn đen/flash.
        
        Returns:
            (good_segments, bad_segments)
        """
        good = []
        bad = []
        
        for seg in segments:
            analysis = self.analyze_segment(
                video_path, seg['start_time'], seg['end_time']
            )
            seg['quality'] = analysis
            
            if analysis['is_bad']:
                bad.append(seg)
            else:
                good.append(seg)
        
        return good, bad
```

---

## Bước 3: Cắt Segments → Folder Theo Tên Video

```python
import os
import subprocess
import re

class SegmentOrganizer:
    """Cắt video thành segments và tổ chức vào folders."""
    
    def __init__(self, output_base: str = "./data/segments"):
        self.output_base = output_base
    
    def process_video(self, video_path: str, 
                       segments: list[dict]) -> dict:
        """
        Cắt 1 video thành segments, lưu vào folder cùng tên.
        
        Args:
            video_path: Path video gốc
            segments: Danh sách segments đã lọc (good only)
            
        Returns:
            {folder_name, folder_path, segments: [{path, metadata}]}
        """
        # Tạo folder name từ tên video (sanitize)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        folder_name = self._sanitize_name(video_name)
        folder_path = os.path.join(self.output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # Cắt từng segment
        results = []
        for i, seg in enumerate(segments):
            output_file = f"segment_{i+1:03d}.mp4"
            output_path = os.path.join(folder_path, output_file)
            
            # Cắt bằng FFmpeg (re-encode cho chính xác)
            self._cut_segment(
                video_path, 
                seg['start_time'], 
                seg['end_time'],
                output_path
            )
            
            results.append({
                'file_path': output_path,
                'file_name': output_file,
                'index': i + 1,
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'duration': seg['duration'],
                'confidence': seg.get('confidence', 1.0),
                'source_video': video_name,
                'folder': folder_name,
            })
        
        return {
            'folder_name': folder_name,
            'folder_path': folder_path,
            'source_video': video_path,
            'total_segments': len(results),
            'segments': results,
        }
    
    def process_batch(self, video_paths: list[str]) -> list[dict]:
        """Xử lý nhiều video → nhiều folders."""
        detector = PreciseSceneDetector()
        bf_filter = BlackFlashFilter()
        all_folders = []
        
        for vpath in video_paths:
            video_name = os.path.basename(vpath)
            print(f"\n📹 Processing: {video_name}")
            
            # 1. Detect scenes
            segments = detector.detect_all(vpath)
            print(f"  🎬 Detected {len(segments)} scenes")
            
            # 2. Filter black/flash
            good, bad = bf_filter.filter_segments(vpath, segments)
            print(f"  ✅ Good: {len(good)} | ❌ Bad: {len(bad)}")
            
            # 3. Cut & organize
            if good:
                result = self.process_video(vpath, good)
                all_folders.append(result)
                print(f"  📁 Folder: {result['folder_name']}/ "
                      f"({result['total_segments']} segments)")
        
        return all_folders
    
    def _cut_segment(self, video_path: str, start: float, 
                      end: float, output_path: str):
        """Cắt segment bằng FFmpeg."""
        duration = end - start
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', video_path,
            '-t', str(duration),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-avoid_negative_ts', '1',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize tên folder."""
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', '_', name)
        name = name[:80]  # Giới hạn chiều dài
        return name
```

---

## Bước 4: LLM Cross-Folder Remix (Trộn Cân Bằng)

```python
import json
import random

# === PROMPT TEMPLATE ===
CROSS_FOLDER_REMIX_PROMPT = """Bạn là đạo diễn video sáng tạo. Tạo kịch bản remix từ segments của NHIỀU video khác nhau.

## QUY TẮC QUAN TRỌNG:
1. KHÔNG lấy quá {max_per_folder} segments từ cùng 1 folder
2. PHẢI trộn đều giữa các folders (ít nhất {min_folders} folders)
3. Segments liền kề KHÔNG được từ cùng 1 folder (trộn xen kẽ)
4. Tổng thời lượng gần {target_duration}s
5. Chọn segments có nội dung/mood phù hợp khi đặt cạnh nhau

## Danh sách Folders & Segments:
{folders_description}

## Trả về JSON:
{{
  "title": "Tên video remix",
  "sequence": [
    {{
      "folder": "TênFolder",
      "segment": "segment_001.mp4",
      "reason": "Tại sao chọn segment này ở vị trí này",
      "transition": "crossfade|cut|fade"
    }}
  ],
  "folder_usage": {{
    "FolderA": 3,
    "FolderB": 2,
    "FolderC": 3
  }},
  "estimated_duration": 58.5,
  "balance_score": 0.85
}}

CHỈ trả về JSON."""


class CrossFolderRemixer:
    """LLM-guided remix trộn segments từ nhiều folders cân bằng."""
    
    def __init__(self, llm_provider, 
                 max_per_folder: int = 3,
                 min_folders: int = 3):
        self.llm = llm_provider
        self.max_per_folder = max_per_folder
        self.min_folders = min_folders
    
    async def generate_remix_script(self, folders: list[dict],
                                      target_duration: float = 60.0) -> dict:
        """
        LLM tạo kịch bản remix cross-folder.
        
        Args:
            folders: Output từ SegmentOrganizer.process_batch()
            target_duration: Thời lượng mong muốn
        """
        # Format folders cho prompt
        desc = self._format_folders(folders)
        
        prompt = CROSS_FOLDER_REMIX_PROMPT.format(
            max_per_folder=self.max_per_folder,
            min_folders=min(self.min_folders, len(folders)),
            target_duration=target_duration,
            folders_description=desc,
        )
        
        response = await self.llm.generate(prompt, temperature=0.5)
        script = json.loads(response)
        
        # Validate cân bằng
        script = self._validate_balance(script, folders)
        
        return script
    
    def _format_folders(self, folders: list[dict]) -> str:
        """Format danh sách folders cho LLM prompt."""
        lines = []
        for folder in folders:
            lines.append(f"\n### 📁 {folder['folder_name']}/ "
                        f"(nguồn: {os.path.basename(folder['source_video'])})")
            for seg in folder['segments']:
                lines.append(
                    f"  - {seg['file_name']} | "
                    f"{seg['duration']:.1f}s | "
                    f"confidence: {seg.get('confidence', 1.0):.2f}"
                )
        return '\n'.join(lines)
    
    def _validate_balance(self, script: dict, folders: list[dict]) -> dict:
        """Validate và sửa nếu script không cân bằng."""
        folder_counts = {}
        for step in script.get('sequence', []):
            f = step.get('folder', '')
            folder_counts[f] = folder_counts.get(f, 0) + 1
        
        # Check violations
        violations = []
        for f, count in folder_counts.items():
            if count > self.max_per_folder:
                violations.append(f"'{f}': {count} > max {self.max_per_folder}")
        
        if violations:
            script['_warnings'] = violations
            script['_balanced'] = False
        else:
            script['_balanced'] = True
        
        # Tính balance score
        if folder_counts:
            counts = list(folder_counts.values())
            avg = np.mean(counts)
            std = np.std(counts)
            script['balance_score'] = round(1.0 - (std / (avg + 1e-6)), 3)
        
        return script
    
    def build_video(self, script: dict, folders: list[dict],
                     output_path: str) -> str:
        """Ghép video từ script cross-folder."""
        from moviepy import VideoFileClip, concatenate_videoclips
        
        # Map folder_name → segments
        folder_map = {}
        for folder in folders:
            seg_map = {s['file_name']: s for s in folder['segments']}
            folder_map[folder['folder_name']] = seg_map
        
        clips = []
        for step in script.get('sequence', []):
            folder_name = step['folder']
            seg_name = step['segment']
            
            seg_info = folder_map.get(folder_name, {}).get(seg_name)
            if seg_info is None:
                print(f"  ⚠️ Not found: {folder_name}/{seg_name}, skipping")
                continue
            
            clip = VideoFileClip(seg_info['file_path'])
            clips.append(clip)
        
        if not clips:
            raise ValueError("No valid clips to assemble")
        
        # Concatenate
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=30,
        )
        
        # Cleanup
        for c in clips:
            c.close()
        final.close()
        
        return output_path
```

---

## Bước 5: Full Pipeline

```python
async def cross_folder_pipeline(video_paths: list[str],
                                  output_path: str,
                                  llm_provider,
                                  target_duration: float = 60.0,
                                  max_per_folder: int = 3):
    """
    Pipeline đầy đủ:
    Videos → Scene Detect → Filter Black/Flash → Cut to Folders → LLM Remix
    """
    print("=" * 60)
    print("🎬 CROSS-FOLDER REMIX PIPELINE")
    print("=" * 60)
    
    # 1. Cắt tất cả video → folders
    organizer = SegmentOrganizer(output_base="./data/segments")
    folders = organizer.process_batch(video_paths)
    
    total_segs = sum(f['total_segments'] for f in folders)
    print(f"\n📊 Tổng: {len(folders)} folders, {total_segs} segments")
    
    # 2. LLM tạo kịch bản cross-folder
    print(f"\n🧠 LLM đang tạo kịch bản remix...")
    remixer = CrossFolderRemixer(
        llm_provider, 
        max_per_folder=max_per_folder
    )
    script = await remixer.generate_remix_script(folders, target_duration)
    
    print(f"  📝 Script: {len(script.get('sequence', []))} segments")
    print(f"  ⚖️ Balance: {script.get('balance_score', 0):.0%}")
    if script.get('folder_usage'):
        for f, count in script['folder_usage'].items():
            print(f"     {f}: {count} segments")
    
    # 3. Build video
    print(f"\n🎥 Đang ghép video...")
    result = remixer.build_video(script, folders, output_path)
    
    print(f"\n✅ Video remix: {result}")
    return result
```

---

## Cấu Hình

```yaml
# Thêm vào config/settings.yaml
scene_detection_precise:
  content_threshold: 27.0       # PySceneDetect content
  adaptive_threshold: 3.5       # PySceneDetect adaptive
  hist_threshold: 0.5           # Histogram correlation
  min_scene_len: 1.0            # Giây
  consensus_tolerance: 0.5      # Giây - merge cuts gần nhau

black_flash_filter:
  black_threshold: 15.0         # Pixel intensity (0-255)
  black_ratio: 0.7              # > 70% frames đen = loại
  flash_threshold: 100.0        # Brightness jump > 100 = flash
  min_segment_duration: 0.5     # Segment < 0.5s = loại

cross_folder_remix:
  max_segments_per_folder: 3    # Không quá N segments/folder
  min_folders_used: 3           # Phải dùng ít nhất N folders
  no_adjacent_same_folder: true # 2 segments liền không cùng folder
  segments_base_dir: "./data/segments"
```

---

## Test

```python
def test_black_frame_detection():
    bf = BlackFlashFilter(black_threshold=15.0)
    # Test với segment chứa nhiều frame đen
    result = bf.analyze_segment("test_black_video.mp4", 0, 3)
    assert result['is_bad'] == True
    assert result['black_ratio'] > 0.5

def test_consensus_merge():
    detector = PreciseSceneDetector()
    # 3 methods đều detect cut tại ~5.0s → confidence = 1.0
    merged = detector._consensus_merge(
        [5.0, 10.0],       # content
        [5.1, 15.0],       # adaptive
        [4.9, 10.1],       # histogram
        tolerance=0.5
    )
    assert any(s['confidence'] == 1.0 for s in merged)

def test_cross_folder_balance():
    remixer = CrossFolderRemixer(None, max_per_folder=3)
    script = {
        'sequence': [
            {'folder': 'A'}, {'folder': 'B'}, {'folder': 'C'},
            {'folder': 'A'}, {'folder': 'B'}, {'folder': 'C'},
        ]
    }
    validated = remixer._validate_balance(script, [])
    assert validated['_balanced'] == True
```
