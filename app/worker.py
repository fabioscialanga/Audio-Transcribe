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
            if self.options.engine == "whisper_cpp":
                from .whisper_cpp import WhisperCppTranscriber

                transcriber = WhisperCppTranscriber(self.options)
            else:
                self.stageChanged.emit("Caricamento del modello…")
                transcriber = LocalTranscriber(self.options)
            if self._cancel_requested:
                raise TranscriptionCancelled()

            if self.options.engine != "whisper_cpp":
                self.stageChanged.emit("Trascrizione in corso…")

            def report_progress(_segment_count: int, end: float, duration: float) -> None:
                if duration > 0:
                    self.progress.emit(max(1, min(99, int((end / duration) * 100))))

            def report_segment(segment: TranscriptSegment) -> None:
                self.segmentReady.emit(segment)

            kwargs = {
                "progress_callback": report_progress,
                "segment_callback": report_segment,
                "should_cancel": lambda: self._cancel_requested,
            }
            if self.options.engine == "whisper_cpp":
                kwargs["stage_callback"] = self.stageChanged.emit
            result = transcriber.transcribe(self.file_path, **kwargs)
            if self._cancel_requested:
                raise TranscriptionCancelled()
            self.progress.emit(100)
            self.finished.emit(result, transcriber.device)
        except TranscriptionCancelled:
            self.cancelled.emit()
        except MemoryError as exc:
            error_msg = (
                "Memoria insufficiente per la trascrizione.\n\n"
                "Soluzioni:\n"
                "• Usa whisper.cpp con un modello più piccolo (tiny o base)\n"
                "• Chiudi altre applicazioni\n"
                "• Dividi l'audio in file più piccoli"
            )
            self.failed.emit(error_msg)
        except Exception as exc:
            error_str = str(exc)
            # Detect memory allocation errors from NumPy/ONNX
            if "allocate" in error_str.lower() and ("gib" in error_str.lower() or "mib" in error_str.lower()):
                error_msg = (
                    "Memoria insufficiente per la trascrizione.\n\n"
                    "Soluzioni:\n"
                    "• Usa whisper.cpp con un modello più piccolo (tiny o base)\n"
                    "• Chiudi altre applicazioni\n"
                    "• Dividi l'audio in file più piccoli"
                )
                self.failed.emit(error_msg)
            else:
                self.failed.emit(error_str)
