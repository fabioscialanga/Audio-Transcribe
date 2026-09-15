from PySide6.QtCore import QObject, Signal, Slot

from .transcriber import LocalTranscriber, TranscriptionOptions


class TranscriptionWorker(QObject):
    finished = Signal(str, str)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, file_path: str, options: TranscriptionOptions):
        super().__init__()
        self.file_path = file_path
        self.options = options

    @Slot()
    def run(self):
        try:
            transcriber = LocalTranscriber(self.options)

            def report_progress(_segment_count, end, duration):
                if duration and duration > 0:
                    pct = max(0, min(99, int((end / duration) * 100)))
                    self.progress.emit(pct)

            text, _info = transcriber.transcribe(
                self.file_path,
                progress_callback=report_progress,
            )
            self.progress.emit(100)
            self.finished.emit(text, transcriber.device)
        except Exception as exc:
            self.failed.emit(str(exc))
