from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg",
}


class DropArea(QFrame):
    fileDropped = Signal(str)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(132)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(7)

        icon = QLabel("＋")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Trascina qui un file audio o video")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("oppure fai clic per sfogliare  ·  MP3, WAV, M4A, MP4 e altri")
        subtitle.setObjectName("dropSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(subtitle)

    @staticmethod
    def _valid_path(event) -> str | None:
        if not event.mimeData().hasUrls():
            return None
        urls = event.mimeData().urls()
        if len(urls) != 1:
            return None
        path = Path(urls[0].toLocalFile())
        return str(path) if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS else None

    def dragEnterEvent(self, event):
        if self._valid_path(event):
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        path = self._valid_path(event)
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if path:
            self.fileDropped.emit(path)
            event.acceptProposedAction()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
