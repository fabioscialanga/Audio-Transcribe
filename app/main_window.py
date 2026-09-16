from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .drop_area import DropArea, SUPPORTED_EXTENSIONS
from .exporters import export_content
from .transcriber import (
    TranscriptSegment, TranscriptionOptions, TranscriptionResult, detect_compute_device,
)
from .worker import TranscriptionWorker


LANGUAGES = [
    ("Rilevamento automatico", None), ("Italiano", "it"), ("Inglese", "en"),
    ("Francese", "fr"), ("Tedesco", "de"), ("Spagnolo", "es"),
    ("Portoghese", "pt"), ("Olandese", "nl"), ("Polacco", "pl"),
    ("Giapponese", "ja"), ("Cinese", "zh"),
]

MODEL_INFO = {
    "tiny": "Più rapido · ~75 MB", "base": "Rapido · ~145 MB",
    "small": "Consigliato · ~470 MB", "medium": "Alta qualità · ~1,5 GB",
    "large-v3": "Massima qualità · ~3 GB",
}

WHISPER_CPP_MODEL_INFO = {
    "tiny": "Massima velocità · quantizzato · ~32 MB",
    "base": "Consigliato · quantizzato · ~60 MB",
    "small": "Qualità superiore · quantizzato · ~190 MB",
}


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024
    return ""


def _format_duration(seconds: float) -> str:
    total = max(0, round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_path: str | None = None
        self.thread: QThread | None = None
        self.worker: TranscriptionWorker | None = None
        self.result: TranscriptionResult | None = None
        self.settings = QSettings()

        self.setWindowTitle("Audio Transcribe")
        self.setMinimumSize(1040, 760)
        self.resize(1120, 780)
        self._build_ui()
        self._restore_settings()
        self._set_running(False)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(26, 22, 26, 18)
        page.setSpacing(18)

        header = QHBoxLayout()
        brand = QLabel("A")
        brand.setObjectName("brandMark")
        brand.setFixedSize(46, 46)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading = QVBoxLayout()
        heading.setSpacing(1)
        title = QLabel("Audio Transcribe")
        title.setObjectName("title")
        subtitle = QLabel("Trascrizioni accurate, private e completamente locali")
        subtitle.setObjectName("subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addWidget(brand)
        header.addSpacing(4)
        header.addLayout(heading)
        header.addStretch()
        self.compute_badge = QLabel("Rilevamento hardware…")
        self.compute_badge.setObjectName("computeBadge")
        self.compute_badge.setToolTip("Il motore viene scelto automaticamente e può ripiegare sulla CPU se CUDA non è utilizzabile")
        header.addWidget(self.compute_badge)
        header.addSpacing(10)
        privacy = QLabel("●  Nessun upload")
        privacy.setObjectName("muted")
        privacy.setToolTip("Audio e trascrizioni restano su questo computer")
        header.addWidget(privacy)
        page.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_output_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([430, 650])
        page.addWidget(splitter, 1)
        self.statusBar().showMessage("Pronto · seleziona un file per iniziare")
        QTimer.singleShot(0, self._update_compute_badge)

    def _build_input_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(13)

        self.drop_area = DropArea()
        self.drop_area.fileDropped.connect(self.load_file)
        self.drop_area.clicked.connect(self.select_file)
        layout.addWidget(self.drop_area)

        self.file_card = QFrame()
        self.file_card.setObjectName("fileCard")
        file_layout = QHBoxLayout(self.file_card)
        file_layout.setContentsMargins(14, 10, 10, 10)
        info = QVBoxLayout()
        info.setSpacing(2)
        self.file_label = QLabel()
        self.file_label.setObjectName("fileName")
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_meta = QLabel()
        self.file_meta.setObjectName("muted")
        info.addWidget(self.file_label)
        info.addWidget(self.file_meta)
        file_layout.addLayout(info, 1)
        self.open_folder_button = QPushButton("Cartella")
        self.open_folder_button.setToolTip("Mostra il file in Esplora file")
        self.open_folder_button.clicked.connect(self.open_file_folder)
        file_layout.addWidget(self.open_folder_button)
        layout.addWidget(self.file_card)
        self.file_card.hide()

        settings_card = QFrame()
        settings_card.setObjectName("card")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 14, 16, 16)
        settings_layout.setSpacing(11)
        section = QLabel("IMPOSTAZIONI")
        section.setObjectName("sectionTitle")
        settings_layout.addWidget(section)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        grid.addWidget(QLabel("Motore"), 0, 0)
        grid.addWidget(QLabel("Modello"), 0, 1)
        grid.addWidget(QLabel("Lingua"), 0, 2)
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("whisper.cpp · rapido", "whisper_cpp")
        self.engine_combo.addItem("faster-whisper · compatibilità", "faster_whisper")
        self.engine_combo.currentIndexChanged.connect(self._update_engine_options)
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self._update_model_hint)
        self.language_combo = QComboBox()
        for label, code in LANGUAGES:
            self.language_combo.addItem(label, code)
        grid.addWidget(self.engine_combo, 1, 0)
        grid.addWidget(self.model_combo, 1, 1)
        grid.addWidget(self.language_combo, 1, 2)
        self.model_hint = QLabel()
        self.model_hint.setObjectName("muted")
        grid.addWidget(self.model_hint, 2, 0, 1, 3)

        grid.addWidget(QLabel("Operazione"), 3, 0)
        grid.addWidget(QLabel("Precisione"), 3, 1)
        self.task_combo = QComboBox()
        self.task_combo.addItem("Trascrivi", "transcribe")
        self.task_combo.addItem("Traduci in inglese", "translate")
        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(1, 10)
        self.beam_spin.setValue(5)
        self.beam_spin.setSuffix(" beam")
        self.beam_spin.setToolTip("Valori più alti migliorano la ricerca ma rallentano l'elaborazione")
        grid.addWidget(self.task_combo, 4, 0)
        grid.addWidget(self.beam_spin, 4, 1)
        settings_layout.addLayout(grid)

        self.vad_check = QCheckBox("Ignora automaticamente silenzi e rumori")
        self.vad_check.setChecked(True)
        settings_layout.addWidget(self.vad_check)
        settings_layout.addWidget(QLabel("Glossario e contesto (opzionale)"))
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Nomi propri, sigle, termini tecnici…")
        self.prompt_input.setClearButtonEnabled(True)
        settings_layout.addWidget(self.prompt_input)
        for control in (self.engine_combo, self.model_combo, self.language_combo, self.task_combo,
                        self.beam_spin, self.prompt_input):
            control.setMinimumHeight(38)
        layout.addWidget(settings_card)

        controls = QHBoxLayout()
        self.transcribe_button = QPushButton("Avvia trascrizione")
        self.transcribe_button.setObjectName("primaryButton")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.cancel_button = QPushButton("Annulla")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self.cancel_transcription)
        controls.addWidget(self.transcribe_button, 1)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.progress_label = QLabel("In attesa di un file")
        self.progress_label.setObjectName("muted")
        layout.addWidget(self.progress_label)
        layout.addStretch()
        return panel

    def _build_output_panel(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 14, 17, 16)
        layout.setSpacing(11)
        top = QHBoxLayout()
        title = QLabel("TRASCRIZIONE")
        title.setObjectName("sectionTitle")
        self.metrics_label = QLabel("0 parole")
        self.metrics_label.setObjectName("muted")
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.metrics_label)
        layout.addLayout(top)

        self.text_output = QTextEdit()
        self.text_output.setAcceptRichText(False)
        self.text_output.setPlaceholderText(
            "Il testo apparirà qui durante la trascrizione.\n\n"
            "Potrai correggerlo liberamente e poi copiarlo o esportarlo."
        )
        self.text_output.textChanged.connect(self._update_word_count)
        layout.addWidget(self.text_output, 1)

        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copia testo")
        self.copy_button.clicked.connect(self.copy_text)
        self.export_button = QPushButton("Esporta")
        export_menu = QMenu(self.export_button)
        for label, extension in (
            ("Documento di testo (.txt)", ".txt"), ("Sottotitoli SubRip (.srt)", ".srt"),
            ("Sottotitoli WebVTT (.vtt)", ".vtt"), ("Dati completi (.json)", ".json"),
        ):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, ext=extension: self.export_result(ext))
            export_menu.addAction(action)
        self.export_button.setMenu(export_menu)
        self.clear_button = QPushButton("Pulisci")
        self.clear_button.clicked.connect(self.clear_output)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.export_button)
        actions.addStretch()
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)
        self._update_word_count()
        return card

    def _restore_settings(self) -> None:
        has_saved_engine = self.settings.contains("engine")
        engine = self.settings.value("engine", "whisper_cpp")
        self.engine_combo.setCurrentIndex(max(0, self.engine_combo.findData(engine)))
        self._update_engine_options()
        saved_model = self.settings.value("model", "base") if has_saved_engine else "base"
        self.model_combo.setCurrentText(saved_model)
        language = self.settings.value("language", "")
        index = self.language_combo.findData(language or None)
        self.language_combo.setCurrentIndex(max(0, index))
        self.task_combo.setCurrentIndex(max(0, self.task_combo.findData(self.settings.value("task", "transcribe"))))
        saved_beam = int(self.settings.value("beam", 5)) if has_saved_engine else 3
        self.beam_spin.setValue(saved_beam)
        self.vad_check.setChecked(self.settings.value("vad", True, type=bool))
        self.prompt_input.setText(self.settings.value("prompt", ""))
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self._update_model_hint(self.model_combo.currentText())

    def _save_settings(self) -> None:
        self.settings.setValue("engine", self.engine_combo.currentData())
        self.settings.setValue("model", self.model_combo.currentText())
        self.settings.setValue("language", self.language_combo.currentData() or "")
        self.settings.setValue("task", self.task_combo.currentData())
        self.settings.setValue("beam", self.beam_spin.value())
        self.settings.setValue("vad", self.vad_check.isChecked())
        self.settings.setValue("prompt", self.prompt_input.text())
        self.settings.setValue("geometry", self.saveGeometry())

    def _update_model_hint(self, model: str) -> None:
        info = WHISPER_CPP_MODEL_INFO if self.engine_combo.currentData() == "whisper_cpp" else MODEL_INFO
        self.model_hint.setText(info.get(model, ""))

    def _update_engine_options(self) -> None:
        if not hasattr(self, "model_combo"):
            return
        previous = self.model_combo.currentText()
        info = WHISPER_CPP_MODEL_INFO if self.engine_combo.currentData() == "whisper_cpp" else MODEL_INFO
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model, hint in info.items():
            self.model_combo.addItem(model, model)
            self.model_combo.setItemData(self.model_combo.count() - 1, hint, Qt.ItemDataRole.ToolTipRole)
        preferred = previous if previous in info else ("base" if "base" in info else next(iter(info)))
        self.model_combo.setCurrentText(preferred)
        self.model_combo.blockSignals(False)
        self._update_model_hint(preferred)
        self._update_compute_badge()

    def _update_compute_badge(self) -> None:
        if hasattr(self, "engine_combo") and self.engine_combo.currentData() == "whisper_cpp":
            self.compute_badge.setText("●  CPU · whisper.cpp BLAS")
            self.compute_badge.setProperty("device", "cpu")
            self.compute_badge.style().unpolish(self.compute_badge)
            self.compute_badge.style().polish(self.compute_badge)
            return
        device, compute_type = detect_compute_device()
        if device == "cuda":
            self.compute_badge.setText("●  GPU NVIDIA · CUDA FP16")
            self.compute_badge.setProperty("device", "gpu")
        else:
            self.compute_badge.setText("●  CPU · INT8")
            self.compute_badge.setProperty("device", "cpu")
        self.compute_badge.style().unpolish(self.compute_badge)
        self.compute_badge.style().polish(self.compute_badge)

    def select_file(self) -> None:
        filters = "Audio e video (" + " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS)) + ")"
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleziona audio o video", "", filters)
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            QMessageBox.warning(self, "Formato non supportato", "Seleziona un file audio o video supportato.")
            return
        self.file_path = str(path)
        self.result = None
        self.file_label.setText(path.name)
        self.file_label.setToolTip(str(path))
        self.file_meta.setText(f"{path.suffix.upper().lstrip('.')}  ·  {_human_size(path.stat().st_size)}")
        self.file_card.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label.setText("Pronto per la trascrizione")
        self.statusBar().showMessage(f"File selezionato: {path.name}")
        self._set_running(False)

    def open_file_folder(self) -> None:
        if self.file_path:
            QDesktopServices.openUrl(Path(self.file_path).parent.as_uri())

    def start_transcription(self) -> None:
        if not self.file_path or self.thread:
            return
        self.result = None
        self.text_output.clear()
        self.progress.setRange(0, 0)
        self.progress_label.setText("Preparazione…")
        self._save_settings()
        self._set_running(True)

        options = TranscriptionOptions(
            engine=self.engine_combo.currentData(), model_name=self.model_combo.currentText(),
            language=self.language_combo.currentData(),
            task=self.task_combo.currentData(), initial_prompt=self.prompt_input.text().strip(),
            beam_size=self.beam_spin.value(), vad_filter=self.vad_check.isChecked(),
        )
        self.thread = QThread(self)
        self.worker = TranscriptionWorker(self.file_path, options)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.stageChanged.connect(self._on_stage_changed)
        self.worker.progress.connect(self._on_progress)
        self.worker.segmentReady.connect(self._append_segment)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(self.on_cancelled)
        for signal in (self.worker.finished, self.worker.failed, self.worker.cancelled):
            signal.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.worker.cancelled.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _set_running(self, running: bool) -> None:
        self.transcribe_button.setEnabled(bool(self.file_path) and not running)
        self.cancel_button.setVisible(running)
        for widget in (self.drop_area, self.engine_combo, self.model_combo, self.language_combo, self.task_combo,
                       self.beam_spin, self.vad_check, self.prompt_input):
            widget.setEnabled(not running)

    def _on_stage_changed(self, stage: str) -> None:
        self.progress_label.setText(stage)
        self.statusBar().showMessage(stage)

    def _on_progress(self, value: int) -> None:
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(value)
        self.progress_label.setText(f"Trascrizione in corso · {value}%")

    def _append_segment(self, segment: TranscriptSegment) -> None:
        cursor = self.text_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self.text_output.toPlainText():
            cursor.insertText(" ")
        cursor.insertText(segment.text)
        self.text_output.setTextCursor(cursor)
        self.text_output.ensureCursorVisible()

    def cancel_transcription(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.progress_label.setText("Annullamento in corso…")

    def on_finished(self, result: TranscriptionResult, device: str) -> None:
        self.result = result
        self.text_output.setPlainText(result.text)
        confidence = f" · confidenza {result.language_probability:.0%}" if result.language_probability else ""
        filtered = (
            f" · {result.filtered_repetitions} ripetizioni filtrate"
            if result.filtered_repetitions else ""
        )
        self.progress_label.setText(
            f"Completata · {result.language.upper() or 'AUTO'}{confidence}{filtered} · {_format_duration(result.duration)}"
        )
        self.statusBar().showMessage(f"Trascrizione completata usando {device.upper()}", 8000)
        self._set_running(False)

    def on_failed(self, message: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label.setText("Trascrizione non riuscita")
        self.statusBar().showMessage("Si è verificato un errore")
        self._set_running(False)
        QMessageBox.critical(self, "Errore di trascrizione",
                             f"Non è stato possibile completare la trascrizione.\n\n{message}")

    def on_cancelled(self) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label.setText("Trascrizione annullata")
        self.statusBar().showMessage("Operazione annullata", 5000)
        self._set_running(False)

    def _thread_finished(self) -> None:
        self.thread = None
        self.worker = None
        self.cancel_button.setEnabled(True)

    def _update_word_count(self) -> None:
        text = self.text_output.toPlainText().strip()
        words = len(text.split()) if text else 0
        self.metrics_label.setText(f"{words} parole  ·  {len(text)} caratteri")
        for widget in (self.copy_button, self.export_button, self.clear_button):
            widget.setEnabled(bool(text))

    def copy_text(self) -> None:
        text = self.text_output.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)
            self.statusBar().showMessage("Testo copiato negli appunti", 4000)

    def export_result(self, extension: str) -> None:
        text = self.text_output.toPlainText().strip()
        if not text:
            return
        if self.result is None:
            self.result = TranscriptionResult(text=text)
        else:
            self.result.text = text
        stem = Path(self.file_path).stem if self.file_path else "trascrizione"
        filters = {".txt": "Documento di testo (*.txt)", ".srt": "Sottotitoli SubRip (*.srt)",
                   ".vtt": "Sottotitoli WebVTT (*.vtt)", ".json": "File JSON (*.json)"}
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta trascrizione", f"{stem}_trascrizione{extension}", filters[extension]
        )
        if not path:
            return
        output_path = Path(path)
        if output_path.suffix.lower() != extension:
            output_path = output_path.with_suffix(extension)
        encoding = "utf-8-sig" if extension == ".txt" else "utf-8"
        output_path.write_text(export_content(self.result, extension), encoding=encoding)
        self.statusBar().showMessage(f"Esportato: {output_path}", 7000)

    def clear_output(self) -> None:
        self.result = None
        self.text_output.clear()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label.setText("Pronto per una nuova trascrizione" if self.file_path else "In attesa di un file")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()
        if self.thread and self.thread.isRunning():
            choice = QMessageBox.question(
                self, "Trascrizione in corso", "Vuoi annullare la trascrizione e chiudere l'app?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self.worker:
                self.worker.cancel()
            event.ignore()
            self.thread.finished.connect(self.close)
            QTimer.singleShot(0, lambda: self.progress_label.setText("Chiusura in corso…"))
            return
        event.accept()
