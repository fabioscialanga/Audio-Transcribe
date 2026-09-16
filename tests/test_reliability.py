import sys
import time
from threading import Event, Timer

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.whisper_cpp import _run_command
from app.transcriber import TranscriptionCancelled, TranscriptionResult, TranscriptSegment
from app.main_window import MainWindow


def test_cancel_silent_process(tmp_path):
    cancelled = Event()
    timer = Timer(0.3, cancelled.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(TranscriptionCancelled):
            _run_command([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, cancelled.is_set)
    finally:
        timer.cancel()
    assert time.monotonic() - started < 8


def test_process_failure_preserves_error_details(tmp_path):
    with pytest.raises(RuntimeError, match="missing model"):
        _run_command([sys.executable, "-c", "print('missing model'); raise SystemExit(2)"], tmp_path)


def test_process_drains_large_output(tmp_path):
    received = []
    _run_command([sys.executable, "-c", "for i in range(1000): print(i)"], tmp_path, on_line=received.append)
    assert len(received) == 1000


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("AudioTranscribeTests")
    app.setApplicationName("Reliability")
    window = MainWindow()
    yield window
    window.text_output.document().setModified(False)
    window.close()


def test_running_locks_editing_and_export(window):
    window.text_output.setPlainText("Testo già ricevuto")
    window._set_running(True)
    assert window.text_output.isReadOnly()
    assert not window.clear_button.isEnabled()
    assert not window.export_button.isEnabled()
    window._set_running(False)
    assert window.export_button.isEnabled()


def test_subtitle_export_rejects_unaligned_edits(window, monkeypatch):
    window.result = TranscriptionResult("Originale", [TranscriptSegment(0, 1, "Originale")])
    window.text_output.setPlainText("Correzione")
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    window.export_result(".srt")
    assert messages and "timestamp" in messages[0]
    assert window.result.text == "Originale"
