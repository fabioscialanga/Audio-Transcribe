APP_STYLE = """
QWidget {
    background: #0b1020;
    color: #e8ecf5;
    font-family: "Segoe UI";
    font-size: 13px;
}
QMainWindow { background: #0b1020; }
QLabel, QCheckBox { background: transparent; }
QLabel#brandMark {
    background: #786cff;
    border-radius: 12px;
    color: white;
    font-size: 24px;
    font-weight: 700;
}
QLabel#title { font-size: 26px; font-weight: 700; color: #ffffff; }
QLabel#subtitle, QLabel#muted, QLabel#dropSubtitle { color: #8f9bb3; }
QLabel#computeBadge {
    background: #131d30;
    border: 1px solid #293852;
    border-radius: 8px;
    color: #aeb8cc;
    padding: 6px 10px;
}
QLabel#computeBadge[device="gpu"] { color: #8fe2b4; border-color: #285844; }
QLabel#computeBadge[device="cpu"] { color: #aeb8cc; }
QLabel#sectionTitle { font-size: 14px; font-weight: 650; color: #f7f8fc; }
QLabel#fileName { font-size: 14px; font-weight: 650; color: #f6f7fb; }
QFrame#card, QFrame#fileCard {
    background: #12192b;
    border: 1px solid #202b43;
    border-radius: 14px;
}
QFrame#dropArea {
    background: #10182b;
    border: 2px dashed #3d4d70;
    border-radius: 16px;
}
QFrame#dropArea:hover, QFrame#dropArea[dragActive="true"] {
    background: #151d38;
    border-color: #8b7cff;
}
QLabel#dropIcon { color: #9a8cff; font-size: 31px; font-weight: 300; }
QLabel#dropTitle { color: #f7f8fc; font-size: 15px; font-weight: 650; }
QLineEdit, QComboBox, QSpinBox {
    background: #0d1425;
    border: 1px solid #293650;
    border-radius: 9px;
    color: #e8ecf5;
    padding: 5px 10px;
    selection-background-color: #7165e8;
}
QTextEdit {
    background: #0d1425;
    border: 1px solid #293650;
    border-radius: 9px;
    color: #e8ecf5;
    padding: 10px 12px;
    selection-background-color: #7165e8;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus { border-color: #8b7cff; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #151d30;
    border: 1px solid #34415d;
    selection-background-color: #655bd1;
    outline: none;
}
QPushButton {
    background: #1a2438;
    border: 1px solid #2b3852;
    border-radius: 9px;
    color: #e9edf7;
    min-height: 20px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover { background: #24314a; border-color: #40506d; }
QPushButton:pressed { background: #151d2e; }
QPushButton:disabled { color: #66718a; background: #131b2b; border-color: #202a3d; }
QPushButton#primaryButton {
    background: #786cff;
    border-color: #786cff;
    color: #ffffff;
    font-size: 14px;
    padding: 10px 18px;
}
QPushButton#primaryButton:hover { background: #8a7fff; border-color: #8a7fff; }
QPushButton#primaryButton:disabled { background: #24294d; border-color: #30375e; color: #737d99; }
QPushButton#dangerButton { color: #ff9eaa; }
QProgressBar {
    background: #182136;
    border: none;
    border-radius: 4px;
    max-height: 8px;
    min-height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background: #8074ff; border-radius: 4px; }
QCheckBox { spacing: 8px; color: #c7cfde; }
QSplitter::handle { background: transparent; width: 8px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #33415d; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #0b1020; color: #8995ac; }
QToolTip { background: #202a40; color: white; border: 1px solid #3b4863; padding: 5px; }
"""
