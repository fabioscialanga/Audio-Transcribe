from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .drop_area import DropArea
from .transcriber import TranscriptionOptions
from .worker import TranscriptionWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_path = None
        self.thread = None
        self.worker = None

        self.setWindowTitle("Audio Transcribe")
        self.resize(980, 760)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Audio Transcribe")
        title.setObjectName("title")
        subtitle = QLabel("Trascina un audio. Ottieni il testo. Tutto in locale.")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.drop_area = DropArea()
        self.drop_area.fileDropped.connect(self.load_file)
        self.drop_area.mousePressEvent = self._select_file
        layout.addWidget(self.drop_area)

        self.file_label = QLabel("Nessun file selezionato")
        layout.addWidget(self.file_label)

        settings_row = QHBoxLayout()

        settings_row.addWidget(QLabel("Modello:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["medium", "large-v3", "small"])
        self.model_combo.setCurrentText("medium")
        settings_row.addWidget(self.model_combo)

        settings_row.addWidget(QLabel("Lingua:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems(["it", "en", "fr", "de", "es"])
        self.language_combo.setCurrentText("it")
        settings_row.addWidget(self.language_combo)

        settings_row.addStretch(1)
        layout.addLayout(settings_row)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText(
            "Glossario opzionale: ALYANTE, FISDE, TeamSystem, nomi propri..."
        )
        layout.addWidget(self.prompt_input)

        self.transcribe_button = QPushButton("TRASCRIVI")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.transcribe_button.setEnabled(False)
        layout.addWidget(self.transcribe_button)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QLabel("Pronto")
        layout.addWidget(self.status_label)

        self.text_output = QTextEdit()
        self.text_output.setPlaceholderText("La trascrizione comparirà qui...")
        layout.addWidget(self.text_output, 1)

        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copia")
        self.copy_button.clicked.connect(self.copy_text)
        self.export_button = QPushButton("Esporta TXT")
        self.export_button.clicked.connect(self.export_txt)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.export_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.setStyleSheet("""
            QWidget {
                font-family: Segoe UI;
                font-size: 14px;
                background: #111318;
                color: #f4f5f7;
            }
            #title {
                font-size: 30px;
                font-weight: 700;
            }
            #subtitle {
                color: #a7acb7;
                font-size: 15px;
            }
            #dropArea {
                border: 2px dashed #586174;
                border-radius: 14px;
                background: #171a21;
                color: #c9ced8;
                font-size: 17px;
                padding: 24px;
            }
            QPushButton {
                padding: 10px 16px;
                border-radius: 8px;
                background: #252b36;
            }
            QPushButton:disabled {
                color: #737988;
            }
            QTextEdit, QLineEdit, QComboBox {
                background: #171a21;
                border: 1px solid #303644;
                border-radius: 8px;
                padding: 8px;
            }
            QProgressBar {
                min-height: 20px;
                border-radius: 8px;
                background: #1c2028;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background: #6f7cff;
            }
        """)

    def _select_file(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona audio o video",
            "",
            "Audio/Video (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.mp4 *.mov *.mkv *.webm)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        self.file_path = file_path
        self.file_label.setText(Path(file_path).name)
        self.transcribe_button.setEnabled(True)
        self.status_label.setText("File pronto per la trascrizione")

    def start_transcription(self):
        if not self.file_path:
            return

        self.transcribe_button.setEnabled(False)
        self.progress.setValue(0)
        self.text_output.clear()
        self.status_label.setText("Caricamento modello e trascrizione in corso...")

        options = TranscriptionOptions(
            model_name=self.model_combo.currentText(),
            language=self.language_combo.currentText(),
            initial_prompt=self.prompt_input.text().strip(),
        )

        self.thread = QThread()
        self.worker = TranscriptionWorker(self.file_path, options)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)

        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_finished(self, text, device):
        self.text_output.setPlainText(text)
        self.status_label.setText(
            f"Trascrizione completata. Motore utilizzato: {device.upper()}"
        )
        self.transcribe_button.setEnabled(True)

    def on_failed(self, message):
        self.status_label.setText("Errore durante la trascrizione")
        self.transcribe_button.setEnabled(True)
        QMessageBox.critical(self, "Errore", message)

    def copy_text(self):
        text = self.text_output.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)
            self.status_label.setText("Testo copiato negli appunti")

    def export_txt(self):
        text = self.text_output.toPlainText()
        if not text:
            return

        default_name = "trascrizione.txt"
        if self.file_path:
            default_name = f"{Path(self.file_path).stem}_trascrizione.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta trascrizione",
            default_name,
            "File di testo (*.txt)"
        )
        if file_path:
            Path(file_path).write_text(text, encoding="utf-8")
            self.status_label.setText(f"Salvato: {file_path}")
