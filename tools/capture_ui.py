"""Create an off-screen UI preview used during visual regression checks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from app.main_window import MainWindow
from app.styles import APP_STYLE


app = QApplication([])
app.setApplicationName("Audio Transcribe")
app.setOrganizationName("Fabio Scialanga")
app.setStyle("Fusion")
app.setStyleSheet(APP_STYLE)
window = MainWindow()
window.resize(1400, 860)
sample = Path("build/smoke.wav")
if "--with-file" in sys.argv and sample.exists():
    window.load_file(str(sample.resolve()))
window.show()
app.processEvents()
QTest.qWait(250)
output = Path("build/ui-preview.png")
output.parent.mkdir(parents=True, exist_ok=True)
window.grab().save(str(output))
print(output.resolve())
window.close()
