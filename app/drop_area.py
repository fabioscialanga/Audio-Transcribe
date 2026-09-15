from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel


SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
    ".mp4", ".mov", ".mkv", ".webm"
}


class DropArea(QLabel):
    fileDropped = Signal(str)

    def __init__(self):
        super().__init__("Trascina qui un file audio o video\noppure fai clic per selezionarlo")
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setAlignment(0x84)
        self.setMinimumHeight(180)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        path = event.mimeData().urls()[0].toLocalFile()
        self.fileDropped.emit(path)
        event.acceptProposedAction()
