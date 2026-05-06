"""Combat Studio page for the combat highlight pipeline."""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.config import AppConfig
from src.ui.combat_command import build_combat_cut_command
from src.ui.combat_results import format_combat_output_summary, load_combat_output_summaries
from src.ui.utils import Worker
from src.remixer.language_registry import language_code_from_label, language_label, supported_language_labels


class CombatStudioPage(QWidget):
    """Run the combat-cut workflow from the desktop UI."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._pool = QThreadPool()
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(
            self._build_role_note(
                "Purpose: one fight video -> combat hooks -> 9:16 clips -> "
                "commentary, subtitles, voiceover, final MP4. Use Analyzer only "
                "when you want reusable transcript/index prep before running this pipeline."
            )
        )
        layout.addWidget(self._build_inputs())
        layout.addWidget(self._build_options())

        self.btn_run = QPushButton("Run Combat Pipeline")
        self.btn_run.setStyleSheet(
            "background:#10B981;color:white;padding:12px;font-weight:bold;border-radius:6px;"
        )
        self.btn_run.clicked.connect(self._on_run)
        layout.addWidget(self.btn_run)

        audit_row = QHBoxLayout()
        self.btn_refresh_audit = QPushButton("Refresh Output Audit")
        self.btn_refresh_audit.clicked.connect(self._refresh_audit)
        self.btn_open_output = QPushButton("Open Output Folder")
        self.btn_open_output.clicked.connect(self._open_output_dir)
        audit_row.addWidget(self.btn_refresh_audit)
        audit_row.addWidget(self.btn_open_output)
        audit_row.addStretch(1)
        layout.addLayout(audit_row)

        layout.addWidget(self._build_results_table())

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setMinimumHeight(150)
        self.txt_output.setStyleSheet(
            "background:#020617;color:#A5F3FC;border:1px solid #1E293B;"
            "border-radius:8px;padding:10px;font-family:Consolas;"
        )
        layout.addWidget(self.txt_output)
        layout.addStretch(1)

        root.addWidget(scroll)

    def _build_role_note(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            "background:#0F172A;color:#CBD5E1;border:1px solid #334155;"
            "border-radius:6px;padding:8px;font-size:12px;"
        )
        return label

    def _build_inputs(self) -> QGroupBox:
        group = QGroupBox("Combat Source")
        group.setStyleSheet(_GROUP_STYLE)
        form = QFormLayout(group)

        self.txt_video = QLineEdit()
        self.txt_video.setPlaceholderText("Select fight video...")
        btn_video = QPushButton("Browse")
        btn_video.clicked.connect(self._choose_video)
        video_row = QHBoxLayout()
        video_row.addWidget(self.txt_video, 1)
        video_row.addWidget(btn_video)

        self.txt_transcript = QLineEdit()
        self.txt_transcript.setPlaceholderText("Optional transcript JSON")
        btn_transcript = QPushButton("Browse")
        btn_transcript.clicked.connect(self._choose_transcript)
        transcript_row = QHBoxLayout()
        transcript_row.addWidget(self.txt_transcript, 1)
        transcript_row.addWidget(btn_transcript)

        self.txt_output_dir = QLineEdit(self._config.storage.clips)
        btn_output = QPushButton("Browse")
        btn_output.clicked.connect(self._choose_output_dir)
        output_row = QHBoxLayout()
        output_row.addWidget(self.txt_output_dir, 1)
        output_row.addWidget(btn_output)

        form.addRow("Video:", video_row)
        form.addRow("Transcript:", transcript_row)
        form.addRow("Output:", output_row)
        return group

    def _build_options(self) -> QGroupBox:
        group = QGroupBox("Pipeline Options")
        group.setStyleSheet(_GROUP_STYLE)
        form = QFormLayout(group)

        self.spn_top = QSpinBox()
        self.spn_top.setRange(1, 50)
        self.spn_top.setValue(10)

        self.cmb_language = QComboBox()
        self.cmb_language.addItems(supported_language_labels())
        self.cmb_language.setCurrentText(language_label(self._config.voiceover.commentary.language))

        self.cmb_vertical = QComboBox()
        self.cmb_vertical.addItems(["blur", "copy"])

        self.chk_commentary = QCheckBox("Write commentary, subtitles, voiceover, final MP4")
        self.chk_commentary.setChecked(True)
        self.chk_whisper = QCheckBox("Auto-transcribe if transcript is missing")
        self.chk_api = QCheckBox("Use indexed semantic matches when configured")
        self.chk_transcript_only = QCheckBox("Transcript-only analysis")

        form.addRow("Top clips:", self.spn_top)
        form.addRow("Language:", self.cmb_language)
        form.addRow("Vertical mode:", self.cmb_vertical)
        form.addRow(self.chk_commentary)
        form.addRow(self.chk_whisper)
        form.addRow(self.chk_api)
        form.addRow(self.chk_transcript_only)
        return group

    def _build_results_table(self) -> QTableWidget:
        self.table_results = QTableWidget(0, 8)
        self.table_results.setHorizontalHeaderLabels(
            ["#", "Status", "Score", "Hook", "Video", "Audio", "Language", "Commentary Preview"]
        )
        header = self.table_results.horizontalHeader()
        for idx, mode in enumerate(
            [
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
            ]
        ):
            header.setSectionResizeMode(idx, mode)

        self.table_results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_results.setAlternatingRowColors(True)
        self.table_results.setMinimumHeight(170)
        self.table_results.setStyleSheet(
            """
            QTableWidget {
                background:#1E293B; alternate-background-color:#162032;
                border:1px solid #334155; border-radius:8px;
                color:#F8FAFC; gridline-color:#1E293B;
            }
            QTableWidget::item:selected { background:#2563EB; }
            QHeaderView::section {
                background:#0F172A; color:#93C5FD;
                padding:6px; border:none; font-weight:bold;
            }
            """
        )
        return self.table_results

    def _choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select fight video", "", "Video Files (*.mp4 *.mov *.mkv *.webm *.avi)")
        if path:
            self.txt_video.setText(path)

    def _choose_transcript(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select transcript JSON", "", "JSON Files (*.json)")
        if path:
            self.txt_transcript.setText(path)

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output directory")
        if path:
            self.txt_output_dir.setText(path)

    def _on_run(self) -> None:
        video_path = self.txt_video.text().strip()
        if not video_path or not os.path.exists(video_path):
            self.txt_output.setText("Select a valid video file first.")
            return

        self.btn_run.setEnabled(False)
        self.txt_output.setText("Running combat pipeline...\n")
        worker = Worker(self._run_pipeline)
        worker.signals.result.connect(self._on_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.btn_run.setEnabled(True))
        self._pool.start(worker)

    def _run_pipeline(self) -> str:
        cmd = build_combat_cut_command(
            input_path=self.txt_video.text().strip(),
            transcript_path=self.txt_transcript.text().strip(),
            output_dir=self.txt_output_dir.text().strip(),
            top=self.spn_top.value(),
            language=language_code_from_label(self.cmb_language.currentText()),
            vertical_mode=self.cmb_vertical.currentText(),
            write_commentary=self.chk_commentary.isChecked(),
            run_whisper=self.chk_whisper.isChecked(),
            transcript_only=self.chk_transcript_only.isChecked(),
            use_api=self.chk_api.isChecked(),
        )
        result = subprocess.run(cmd, cwd=os.getcwd(), capture_output=True, text=True, timeout=3600)
        output = result.stdout or ""
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
        if result.returncode != 0:
            raise RuntimeError(output or f"combat-cut failed with code {result.returncode}")
        return output

    def _on_done(self, output: str) -> None:
        audit_text = self._refresh_results_table()
        self.txt_output.setText(output + "\n\nOutput Audit:\n" + audit_text)

    def _refresh_audit(self) -> None:
        self.txt_output.setText("Output Audit:\n" + self._refresh_results_table())

    def _refresh_results_table(self) -> str:
        out_dir = self.txt_output_dir.text().strip()
        summaries = load_combat_output_summaries(out_dir)
        self._populate_results_table(summaries)
        return format_combat_output_summary(summaries)

    def _populate_results_table(self, summaries) -> None:
        self.table_results.setRowCount(len(summaries))
        for row, item in enumerate(summaries):
            status = "READY" if item.ready else "CHECK"
            video = f"{item.width}x{item.height}" if item.width and item.height else "-"
            audio = "yes" if item.has_audio else "no"
            cells = [
                str(row + 1),
                status,
                f"{item.score:.2f}",
                f"{item.hook_time:.2f}s",
                video,
                audio,
                item.language or "-",
                " ".join(item.commentary_text.split()) or "-",
            ]
            for col, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                if col == 7:
                    cell.setToolTip(item.commentary_text)
                elif col == 1:
                    cell.setToolTip(item.final_video_path or item.json_path)
                self.table_results.setItem(row, col, cell)
        self.table_results.resizeRowsToContents()

    def _open_output_dir(self) -> None:
        out_dir = self.txt_output_dir.text().strip()
        if os.name == "nt" and os.path.isdir(out_dir):
            try:
                os.startfile(out_dir)
            except Exception:
                pass

    def _on_error(self, err_tuple) -> None:
        self.txt_output.setText(str(err_tuple[1]))


_GROUP_STYLE = """
QGroupBox {
    color:#3B82F6;font-weight:bold;border:1px solid #334155;
    border-radius:8px;margin-top:8px;padding:10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; }
QLabel, QCheckBox { color:#94A3B8; }
QLineEdit, QComboBox, QSpinBox {
    padding:6px;background:#0F172A;color:#F8FAFC;
    border:1px solid #334155;border-radius:4px;
}
QPushButton {
    background:#1E293B;color:white;padding:7px 12px;border-radius:4px;
}
"""
