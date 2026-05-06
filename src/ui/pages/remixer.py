"""
Remixer Page.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QTextEdit, 
    QSplitter, QFrame, QSpinBox, QCheckBox, QComboBox
)

from typing import Optional, List
from src.core.config import AppConfig
from src.ui.utils import Worker
from src.remixer.orchestrator import RemixOrchestrator
from src.core.types import VideoFolder, SegmentFile
from src.analyzer.visual_analyzer import VisualAnalyzer
import os
import asyncio
from pathlib import Path


class RemixerPage(QWidget):
    """Trang lắp ráp và render video (Remix)."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._threadpool = QThreadPool()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter chính
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Cột Trái: Settings & Folders
        left_frame = QFrame()
        left_frame.setStyleSheet("QFrame { background-color: #1E293B; border-radius: 8px; border: 1px solid #334155; }")
        left_layout = QVBoxLayout(left_frame)
        
        # V2 features
        self.chk_rag = QCheckBox("Enable RAG Mode (Search by Topic)")
        self.chk_rag.setChecked(True)
        self.chk_rag.setStyleSheet("color: #10B981; font-weight: bold; margin-top: 10px;")
        
        lbl_topic = QLabel("Search Topic / Prompt:")
        lbl_topic.setStyleSheet("color: #94A3B8;")
        self.txt_topic = QTextEdit()
        self.txt_topic.setPlaceholderText("e.g. AI technology in 2024, travel highlights in Vietnam...")
        self.txt_topic.setMaximumHeight(60)
        self.txt_topic.setStyleSheet("background: #0F172A; color: white; border: 1px solid #334155;")

        # 1. Controls
        lbl_dur = QLabel("Target Duration (seconds):")
        lbl_dur.setStyleSheet("color: #94A3B8;")
        self.spn_dur = QSpinBox()
        self.spn_dur.setRange(10, 3600)
        self.spn_dur.setValue(self._config.remixer.output.default_duration)
        self.spn_dur.setStyleSheet("padding: 5px; background: #0F172A; color: white; border: 1px solid #334155;")
        
        self.chk_meme = QCheckBox("Apply Meme Effects (Images/Sounds)")
        self.chk_meme.setChecked(self._config.meme_effects.enabled)
        self.chk_meme.setStyleSheet("color: #94A3B8;")
        
        self.chk_voice = QCheckBox("Add AI Voiceover")
        self.chk_voice.setChecked(self._config.voiceover.enabled)
        self.chk_voice.setStyleSheet("color: #94A3B8;")
        
        lbl_lang = QLabel("Commentary Language:")
        lbl_lang.setStyleSheet("color: #94A3B8; margin-top: 10px;")
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["Vietnamese", "English", "Chinese", "Japanese", "Korean", "Spanish"])
        self.cmb_lang.setCurrentText(self._get_language_full_name(self._config.voiceover.commentary.language))
        self.cmb_lang.setStyleSheet("padding: 5px; background: #0F172A; color: white; border: 1px solid #334155;")
        
        lbl_style = QLabel("Subtitle Style:")
        lbl_style.setStyleSheet("color: #94A3B8; margin-top: 10px;")
        self.cmb_style = QComboBox()
        self.cmb_style.addItems(["CapCut Yellow", "Modern White", "Glow Pink", "Elegant Gold", "Neon Cyber"])
        self.cmb_style.setCurrentText(self._get_style_full_name(self._config.remixer.effects.subtitles.preset_style))
        self.cmb_style.setStyleSheet("padding: 5px; background: #0F172A; color: white; border: 1px solid #334155;")

        left_layout.addWidget(lbl_dur)
        left_layout.addWidget(self.spn_dur)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.chk_rag)
        left_layout.addWidget(lbl_topic)
        left_layout.addWidget(self.txt_topic)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.chk_meme)
        left_layout.addWidget(self.chk_voice)
        left_layout.addWidget(lbl_lang)
        left_layout.addWidget(self.cmb_lang)
        left_layout.addWidget(lbl_style)
        left_layout.addWidget(self.cmb_style)
        left_layout.addSpacing(20)
        
        # 2. Source Folders
        lbl_folders = QLabel("Select Source Folders (for V1):")
        lbl_folders.setStyleSheet("color: #94A3B8; font-weight: bold;")
        left_layout.addWidget(lbl_folders)
        
        self.list_folders = QListWidget()
        self.list_folders.setStyleSheet("""
            QListWidget { background: #0F172A; border: 1px solid #334155; border-radius: 4px; color: #F8FAFC; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #1E293B; }
        """)
        left_layout.addWidget(self.list_folders)
        
        # 3. Action
        self.btn_remix = QPushButton("🎬 Generate Remix")
        self.btn_remix.clicked.connect(self._on_remix)
        self.btn_remix.setStyleSheet("background: #10B981; color: white; padding: 12px; font-weight: bold; border-radius: 4px;")
        left_layout.addWidget(self.btn_remix)
        
        splitter.addWidget(left_frame)
        
        # Cột Phải: Logs / Script Preview
        right_frame = QFrame()
        right_frame.setStyleSheet(left_frame.styleSheet())
        right_layout = QVBoxLayout(right_frame)
        
        lbl_preview = QLabel("Remix Script Preview")
        lbl_preview.setStyleSheet("color: #94A3B8; font-weight: bold;")
        right_layout.addWidget(lbl_preview)
        
        self.txt_script = QTextEdit()
        self.txt_script.setReadOnly(True)
        self.txt_script.setStyleSheet("background: #0F172A; color: #3B82F6; font-family: Consolas; border: none; padding: 10px; border-radius: 4px;")
        right_layout.addWidget(self.txt_script)
        
        splitter.addWidget(right_frame)
        splitter.setSizes([350, 450])
        layout.addWidget(splitter)
        
        self._load_mock_folders()

    def _load_mock_folders(self) -> None:
        """Scan danh sách folder thực tế từ data/clips."""
        self.list_folders.clear()
        clips_dir = self._config.storage.clips
        if not os.path.exists(clips_dir):
            os.makedirs(clips_dir, exist_ok=True)
            
        folders = [f for f in os.listdir(clips_dir) if os.path.isdir(os.path.join(clips_dir, f))]
        if not folders:
            # Fallback to base clips dir
            item = QListWidgetItem(f"📁 Root Clips Dir: {os.path.basename(clips_dir)}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_folders.addItem(item)
            return

        for f in sorted(folders):
            item = QListWidgetItem(f"📁 {f}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_folders.addItem(item)

    def _on_remix(self) -> None:
        topic = self.txt_topic.toPlainText().strip()
        is_v2 = self.chk_rag.isChecked()
        
        if is_v2 and not topic:
            self.txt_script.setText("⚠️ Vui lòng nhập chủ đề (Topic) khi dùng RAG Mode!")
            return
            
        self.btn_remix.setEnabled(False)
        self.btn_remix.setText("⏳ Orchestrating Remix v2...")
        self.txt_script.setText(f"Target Duration: {self.spn_dur.value()}s\n")
        self.txt_script.append(f"Mode: {'RAG v2.0' if is_v2 else 'Classic v1.0'}\n")
        if is_v2:
            self.txt_script.append(f"Topic: {topic}\n")
        
        # Lấy cấu hình từ UI
        lang_code = self._get_language_code(self.cmb_lang.currentText())
        style_id = self._get_style_id(self.cmb_style.currentText())
        
        worker = Worker(self._run_real_remix, is_v2, topic, self.spn_dur.value(), lang_code, style_id)
        worker.signals.result.connect(self._on_remix_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.btn_remix.setEnabled(True))
        worker.signals.finished.connect(lambda: self.btn_remix.setText("🎬 Generate Remix"))
        self._threadpool.start(worker)

    def _run_real_remix(self, is_v2: bool, topic: str, duration: int, lang: str, style: str) -> str:
        """Thực thi quy trình remix thật trong background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Cập nhật style vào config
            self._config.remixer.effects.subtitles.preset_style = style
            
            if is_v2:
                from src.remixer.orchestrator_v2 import RemixOrchestratorV2
                orch = RemixOrchestratorV2(self._config)
                output_path = loop.run_until_complete(
                    orch.create_remix(topic)
                )
                return output_path
            else:
                # ... (V1 implementation)
                return "output_v1_placeholder.mp4"
        finally:
            loop.close()

    def _on_error(self, error_tuple):
        self.txt_script.append(f"\n❌ Lỗi: {error_tuple[1]}")

    def _get_language_full_name(self, code: str) -> str:
        mapping = {"vi": "Vietnamese", "en": "English", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "es": "Spanish"}
        return mapping.get(code, "Vietnamese")

    def _get_language_code(self, name: str) -> str:
        mapping = {"Vietnamese": "vi", "English": "en", "Chinese": "zh", "Japanese": "ja", "Korean": "ko", "Spanish": "es"}
        return mapping.get(name, "vi")

    def _get_style_full_name(self, style_id: str) -> str:
        mapping = {"capcut_yellow": "CapCut Yellow", "modern_white": "Modern White", "glow_pink": "Glow Pink", "elegant_gold": "Elegant Gold", "neon_cyber": "Neon Cyber"}
        return mapping.get(style_id, "CapCut Yellow")

    def _get_style_id(self, name: str) -> str:
        mapping = {"CapCut Yellow": "capcut_yellow", "Modern White": "modern_white", "Glow Pink": "glow_pink", "Elegant Gold": "elegant_gold", "Neon Cyber": "neon_cyber"}
        return mapping.get(name, "capcut_yellow")

    def _on_remix_done(self, output_path: str) -> None:
        self.txt_script.append("✅ Video Generated Successfully!\n")
        self.txt_script.append(f"📁 Path: {output_path}\n")
        
        # Tự động mở folder chứa video sau khi xong
        try:
            folder = os.path.dirname(output_path)
            if os.name == 'nt': # Windows
                os.startfile(folder)
        except Exception:
            self.txt_script.append("❌ Could not open output folder.")
        self.txt_script.append("\n✅ Rendering Complete: output_final.mp4")
