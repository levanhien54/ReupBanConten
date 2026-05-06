"""
Analyzer Page.
"""
from __future__ import annotations

import json
import os
import asyncio
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QTextEdit, QSplitter, QFrame, QFileDialog, QGroupBox
)

from src.core.config import AppConfig
from src.core.database import get_database, VideoRepository, ClipRepository
from src.core.logging import get_logger
from src.ui.utils import Worker
from src.llm.provider import LLMFactory
from src.analyzer.llm_analyzer import LLMAnalyzer
from src.core.types import VideoMetadata

logger = get_logger(__name__)

class AnalyzerPage(QWidget):
    """Trang phân tích video."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._threadpool = QThreadPool()
        db = get_database()
        self._video_repo = VideoRepository(db)
        self._clip_repo = ClipRepository(db)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._folder_path = ""
        self._clips: list[dict] = []
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(
            self._build_role_note(
                "Purpose: prepare and inspect assets. Use this tab for Whisper transcripts, "
                "LLM/visual analysis, and Twelve Labs indexing before clips are reused by "
                "Combat Studio or Remixer."
            )
        )
        
        # ── Folder Selection ──
        grp_folder = QGroupBox("📁 Nguồn Dữ Liệu")
        grp_folder.setStyleSheet("color: #3B82F6; font-weight: bold;")
        f_layout = QHBoxLayout(grp_folder)
        
        self.lbl_folder = QLabel("Chưa chọn thư mục (data/downloads hoặc data/clips)")
        self.lbl_folder.setStyleSheet("color: #94A3B8; font-weight: normal; font-size: 12px;")
        
        btn_choose = QPushButton("📁 Chọn Thư Mục...")
        btn_choose.setStyleSheet("background: #1E293B; color: white; padding: 6px; border-radius: 4px;")
        btn_choose.clicked.connect(self._choose_folder)
        
        f_layout.addWidget(self.lbl_folder, 1)
        f_layout.addWidget(btn_choose)
        layout.addWidget(grp_folder)
        
        # ── Action Controls ──
        ctrl_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self._load_videos)
        self.btn_refresh.setStyleSheet("background: #1E293B; color: white; padding: 8px; border-radius: 4px;")
        
        self.btn_analyze = QPushButton("🧠 LLM Analysis")
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_analyze.setStyleSheet("background: #1E293B; color: white; padding: 8px 15px; border-radius: 4px;")
        self.btn_analyze.setEnabled(False)

        self.btn_index = QPushButton("🚀 AI Index (Twelve Labs)")
        self.btn_index.clicked.connect(self._on_index_v2)
        self.btn_index.setStyleSheet("background: #3B82F6; color: white; padding: 8px 20px; font-weight: bold; border-radius: 4px;")
        self.btn_index.setEnabled(False)
        
        self.btn_whisper = QPushButton("🎤 Whisper Transcribe")
        self.btn_whisper.clicked.connect(self._on_whisper)
        self.btn_whisper.setStyleSheet("background: #8B5CF6; color: white; padding: 8px 15px; border-radius: 4px;")
        self.btn_whisper.setEnabled(False)

        self.btn_visual = QPushButton("👁️ Visual Analysis")
        self.btn_visual.clicked.connect(self._on_visual_analysis)
        self.btn_visual.setStyleSheet("background: #EC4899; color: white; padding: 8px 15px; border-radius: 4px;")
        self.btn_visual.setEnabled(False)

        ctrl_layout.addWidget(self.btn_refresh)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_whisper)
        ctrl_layout.addWidget(self.btn_visual)
        ctrl_layout.addWidget(self.btn_analyze)
        ctrl_layout.addWidget(self.btn_index)
        layout.addLayout(ctrl_layout)
        
        # Splitter cho Layout chính
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Danh sách video (Bên trái)
        left_frame = QFrame()
        left_frame.setStyleSheet("QFrame { background-color: #1E293B; border-radius: 8px; border: 1px solid #334155; }")
        left_layout = QVBoxLayout(left_frame)
        lbl_list = QLabel("Downloaded Videos")
        lbl_list.setStyleSheet("color: #94A3B8; font-weight: bold;")
        left_layout.addWidget(lbl_list)
        
        self.list_videos = QListWidget()
        self.list_videos.setStyleSheet("""
            QListWidget { background: transparent; border: none; color: #F8FAFC; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #334155; }
            QListWidget::item:selected { background: #3B82F6; border-radius: 4px; }
        """)
        self.list_videos.itemSelectionChanged.connect(self._on_video_selected)
        left_layout.addWidget(self.list_videos)
        splitter.addWidget(left_frame)
        
        # Kết quả phân tích (Bên phải)
        right_frame = QFrame()
        right_frame.setStyleSheet(left_frame.styleSheet())
        right_layout = QVBoxLayout(right_frame)
        lbl_res = QLabel("Analysis Results")
        lbl_res.setStyleSheet("color: #94A3B8; font-weight: bold;")
        right_layout.addWidget(lbl_res)
        
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setStyleSheet("background: #0F172A; color: #10B981; font-family: Consolas; border: none; padding: 10px; border-radius: 4px;")
        right_layout.addWidget(self.txt_result)
        splitter.addWidget(right_frame)
        
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)
        
        self._load_videos()

    def _build_role_note(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            "background:#0F172A;color:#CBD5E1;border:1px solid #334155;"
            "border-radius:6px;padding:8px;font-size:12px;"
        )
        return label

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa Clips / Video")
        if path:
            self._folder_path = path
            self.lbl_folder.setText(path)
            self._load_videos()

    def _load_videos(self) -> None:
        self.list_videos.clear()
        self._clips.clear()
        
        if not self._folder_path or not os.path.exists(self._folder_path):
            self.list_videos.addItem("Vui lòng chọn thư mục chứa video ở trên.")
            return

        # Scan for mp4 and corresponding srt
        for f in sorted(os.listdir(self._folder_path)):
            if f.endswith(".mp4"):
                mp4_path = os.path.join(self._folder_path, f)
                base_name = f[:-4]
                
                # Check for SRT (same name or with .vi.srt / .en.srt)
                srt_path = ""
                for srt_ext in [".srt", ".vi.srt", ".en.srt"]:
                    test_srt = os.path.join(self._folder_path, base_name + srt_ext)
                    if os.path.exists(test_srt):
                        srt_path = test_srt
                        break
                
                # if not found exact match, maybe base name split by _
                if not srt_path:
                    parts = base_name.split("_")
                    if len(parts) > 0:
                        test_srt = os.path.join(self._folder_path, parts[0] + ".vi.srt")
                        if os.path.exists(test_srt):
                            srt_path = test_srt

                self._clips.append({
                    "mp4": mp4_path,
                    "srt": srt_path,
                    "name": f
                })
                
                srt_label = "📄 Có SRT" if srt_path else "⚠️ Ko có phụ đề"
                self.list_videos.addItem(f"🎬 {f}  [{srt_label}]")
                
        if not self._clips:
            self.list_videos.addItem("Không tìm thấy file .mp4 nào trong thư mục này.")

    def _on_video_selected(self) -> None:
        if self.list_videos.selectedItems() and self._clips:
            idx = self.list_videos.currentRow()
            if 0 <= idx < len(self._clips):
                clip = self._clips[idx]
                self.btn_analyze.setEnabled(True)
                self.btn_index.setEnabled(True)
                self.btn_whisper.setEnabled(True)
                self.btn_visual.setEnabled(True)
                self.txt_result.setText(f"Đã chọn: {clip['name']}\n")
                if clip["srt"]:
                    self.txt_result.append(f"Tìm thấy phụ đề: {os.path.basename(clip['srt'])}\n")
                    self.txt_result.append("Sẵn sàng phân tích với LLM.")
                else:
                    self.txt_result.append("Không tìm thấy file phụ đề (.srt). Phân tích sẽ bị giới hạn.\n")
        else:
            self.btn_analyze.setEnabled(False)
            self.btn_index.setEnabled(False)
            self.btn_whisper.setEnabled(False)
            self.btn_visual.setEnabled(False)

    def _on_index_v2(self) -> None:
        idx = self.list_videos.currentRow()
        if idx < 0 or idx >= len(self._clips):
            return
            
        clip = self._clips[idx]
        self.txt_result.setText(f"🚀 Đang đẩy video lên Twelve Labs Index: {clip['name']}...\n\n")
        self.btn_index.setEnabled(False)
        self.btn_index.setText("⏳ Indexing...")
        
        worker = Worker(self._run_v2_indexing, clip)
        worker.signals.result.connect(self._on_index_done)
        worker.signals.error.connect(lambda e: self.txt_result.append(f"❌ LỖI INDEX: {e[1]}"))
        worker.signals.finished.connect(lambda: self.btn_index.setEnabled(True))
        worker.signals.finished.connect(lambda: self.btn_index.setText("🚀 AI Index (Twelve Labs)"))
        self._threadpool.start(worker)

    def _run_v2_indexing(self, clip: dict) -> str:
        """Thực thi Twelve Labs Indexing + Summary."""
        from src.analyzer.twelve_labs_client import TwelveLabsClient
        tl = TwelveLabsClient()
        if not tl.is_available():
            return "Error: Twelve Labs API Key is missing."

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 1. Upload & Index
            index_name = self._config.analyzer.twelve_labs.index_name
            video_id = loop.run_until_complete(tl.upload_video(index_name, clip["mp4"]))
            
            # 2. Pegasus Summary
            summary = loop.run_until_complete(tl.generate_summary(video_id))
            return json.dumps({"video_id": video_id, "summary": summary})
        finally:
            loop.close()

    def _on_index_done(self, result_json: str) -> None:
        if result_json.startswith("Error"):
            self.txt_result.append(f"❌ {result_json}\n")
            return
            
        data = json.loads(result_json)
        self.txt_result.append("✅ Twelve Labs Indexing Hoàn Tất!\n")
        self.txt_result.append(f"🆔 Video ID: {data['video_id']}\n")
        self.txt_result.append(f"📝 Tóm tắt Pegasus:\n{data['summary']}\n")

    def _on_analyze(self) -> None:
        idx = self.list_videos.currentRow()
        if idx < 0 or idx >= len(self._clips):
            return
            
        clip = self._clips[idx]
        self.txt_result.setText(f"🔄 Đang khởi tạo AI Pipeline cho: {clip['name']}...\n\n")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("⏳ Analyzing...")
        
        worker = Worker(self._run_llm_analysis, clip)
        worker.signals.result.connect(self._on_analyze_done)
        worker.signals.error.connect(lambda e: self.txt_result.append(f"❌ LỖI: {e[1]}\n{e[2]}"))
        worker.signals.finished.connect(lambda: self.btn_analyze.setEnabled(True))
        worker.signals.finished.connect(lambda: self.btn_analyze.setText("🧠 AI Analyze Selected"))
        self._threadpool.start(worker)

    def _run_llm_analysis(self, clip: dict) -> str:
        """Chạy thực tế với LLMFactory."""
        # 1. Đọc SRT text
        transcript_text = ""
        if clip["srt"] and os.path.exists(clip["srt"]):
            with open(clip["srt"], "r", encoding="utf-8") as f:
                transcript_text = f.read()
                
        if not transcript_text:
            transcript_text = "Không có lời thoại / không có phụ đề."
            
        # 2. Khởi tạo LLM Provider từ config
        provider_name = self._config.analyzer.llm.provider
        llm = LLMFactory.create_with_fallback(primary=provider_name)
        
        analyzer = LLMAnalyzer(self._config.analyzer, llm)
        
        # 3. Tạo fake metadata để truyền vào analyzer (hiện tại metadata chỉ cần title)
        meta = VideoMetadata(
            video_id=os.path.basename(clip["mp4"]),
            title=clip["name"],
            description="Phân tích nội dung clip cắt / video reup",
            duration=0.0
        )
        
        # 4. Chạy asyncio event loop do _llm là async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(analyzer.analyze(transcript_text, meta))
            return result.model_dump_json(indent=2)
        finally:
            loop.close()
        
    def _on_analyze_done(self, result: str) -> None:
        self.txt_result.append("✅ Phân Tích Hoàn Tất!\n")
        self.txt_result.append("="*40 + "\n")
        
        try:
            data = json.loads(result)
            self.txt_result.append(f"📺 Chủ đề: {', '.join(data.get('topics', []))}")
            self.txt_result.append(f"🎭 Cảm xúc: {data.get('mood', 'neutral')}")
            self.txt_result.append(f"⚡ Energy: {data.get('overall_energy', 0.5):.2f}/1.0")
            self.txt_result.append(f"🔥 Viral Potential: {data.get('viral_potential', 0.5):.2f}/1.0")
            self.txt_result.append(f"\n📝 Tóm tắt:\n{data.get('summary', '')}")
            
            moments = data.get('key_moments', [])
            if moments:
                self.txt_result.append(f"\n🎯 Key Moments ({len(moments)}):")
                for i, m in enumerate(moments):
                    highlight = "⭐" if m.get("is_highlight") else "  "
                    self.txt_result.append(
                        f"  {highlight} [{m.get('start_time', 0.0):.1f}s - {m.get('end_time', 0.0):.1f}s] "
                        f"Energy {m.get('energy_score', 0.0):.1f}: {m.get('description', '')}"
                    )
        except Exception:
            self.txt_result.append("Raw JSON:\n" + result)

    def _on_whisper(self) -> None:
        idx = self.list_videos.currentRow()
        if idx < 0: return
        clip = self._clips[idx]
        self.txt_result.setText(f"🎤 Đang chạy Whisper Transcribe: {clip['name']}...\n")
        self.btn_whisper.setEnabled(False)
        worker = Worker(self._run_whisper_task, clip)
        worker.signals.result.connect(lambda res: self.txt_result.append(f"✅ Transcribe xong! File: {res}\n"))
        worker.signals.error.connect(lambda e: self.txt_result.append(f"❌ LỖI WHISPER: {e[1]}"))
        worker.signals.finished.connect(lambda: self.btn_whisper.setEnabled(True))
        worker.signals.finished.connect(self._load_videos) # Refresh to show SRT status
        self._threadpool.start(worker)

    def _run_whisper_task(self, clip: dict) -> str:
        from src.analyzer.transcriber import Transcriber
        transcriber = Transcriber(self._config.analyzer.whisper)
        srt_path = transcriber.transcribe(clip["mp4"])
        return srt_path

    def _on_visual_analysis(self) -> None:
        idx = self.list_videos.currentRow()
        if idx < 0: return
        clip = self._clips[idx]
        self.txt_result.setText(f"👁️ Đang chạy Visual Analysis (AI Vision): {clip['name']}...\n")
        self.btn_visual.setEnabled(False)
        worker = Worker(self._run_visual_task, clip)
        worker.signals.result.connect(lambda res: self.txt_result.append(f"✅ Visual Analysis xong!\n{res}\n"))
        worker.signals.error.connect(lambda e: self.txt_result.append(f"❌ LỖI VISUAL: {e[1]}"))
        worker.signals.finished.connect(lambda: self.btn_visual.setEnabled(True))
        self._threadpool.start(worker)

    def _run_visual_task(self, clip: dict) -> str:
        from src.analyzer.visual_analyzer import VisualAnalyzer
        analyzer = VisualAnalyzer(self._config.analyzer.visual)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(analyzer.analyze_video(clip["mp4"]))
            return json.dumps([r.model_dump() for r in results], indent=2)
        finally:
            loop.close()
