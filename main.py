import sys
from pathlib import Path

try:
    import truststore

    truststore.inject_into_ssl()
except (ImportError, NotImplementedError):
    # Older Windows/Python combinations can still use certifi's CA bundle.
    pass

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.styles import APP_STYLE


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Audio Transcribe")
    app.setApplicationDisplayName("Audio Transcribe")
    app.setOrganizationName("Fabio Scialanga")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    icon_path = resource_path("assets/icon.svg")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
