from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from .transcriber import (
    LocalTranscriber,
    TranscriptSegment,
    TranscriptionCancelled,
    TranscriptionOptions,
)


class TranscriptionWorker(QObject):
    finished = Signal(object, str)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int)
    segmentReady = Signal(object)
    stageChanged = Signal(str)

    def __init__(self, file_path: str, options: TranscriptionOptions):
        super().__init__()
        self.file_path = file_path
        self.options = options
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        try:
            self.stageChanged.emit("Caricamento del modello…")
            transcriber = LocalTranscriber(self.options)
            if self._cancel_requested:
                raise TranscriptionCancelled()

            self.stageChanged.emit("Trascrizione in corso…")

            def report_progress(_segment_count: int, end: float, duration: float) -> None:
                if duration > 0:
                    self.progress.emit(max(1, min(99, int((end / duration) * 100))))

            def report_segment(segment: TranscriptSegment) -> None:
                self.segmentReady.emit(segment)

            result = transcriber.transcribe(
                self.file_path,
                progress_callback=report_progress,
                segment_callback=report_segment,
                should_cancel=lambda: self._cancel_requested,
            )
            self.progress.emit(100)
            self.finished.emit(result, transcriber.device)
        except TranscriptionCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
