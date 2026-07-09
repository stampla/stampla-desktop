"""Palette and application stylesheet (safelight amber on graphite)."""

from string import Template

PALETTE = {
    "bg": "#16181d",
    "panel": "#1e2128",
    "panel2": "#23262e",
    "line": "#2e323c",
    "text": "#e9e7e2",
    "muted": "#8f929c",
    "faint": "#6a6d77",
    "amber": "#e8a33d",
    "amber_ink": "#241a08",
    "ok": "#63b984",
    "warn": "#d9a03f",
    "crit": "#d96459",
    "info": "#7ba3c9",
}

QSS = Template("""
QMainWindow, QWidget { background: $bg; color: $text; font-size: 13px; }
QStatusBar { background: $panel; color: $muted; }
QStatusBar::item { border: none; }

QListWidget#sidebar {
    background: $panel; border: none; border-right: 1px solid $line;
    padding: 8px 6px; outline: 0;
}
QListWidget#sidebar::item { padding: 9px 12px; border-radius: 6px; color: $muted; }
QListWidget#sidebar::item:hover { background: $panel2; }
QListWidget#sidebar::item:selected {
    background: $panel2; color: $text;
    border-left: 2px solid $amber;
}

QLabel#h1 { font-size: 19px; font-weight: 700; }
QLabel#sub { color: $muted; }
QLabel#faint { color: $faint; font-size: 12px; }

QFrame#card { background: $panel; border: 1px solid $line; border-radius: 8px; }

QPushButton {
    background: $panel2; border: 1px solid $line; border-radius: 6px;
    padding: 6px 14px; font-weight: 600;
}
QPushButton:hover { border-color: $faint; }
QPushButton:disabled { color: $faint; background: $panel; }
QPushButton#primary { background: $amber; color: $amber_ink; border: none; }
QPushButton#primary:disabled { background: $panel2; color: $faint; }
QPushButton#danger { background: transparent; color: $crit; border: 1px solid #5a3a37; }

QCheckBox { color: $muted; }

QPushButton#cliToggle {
    background: transparent; border: none; color: $faint;
    font-family: Menlo, monospace; font-weight: 700; padding: 4px 8px;
}
QPushButton#cliToggle:hover { color: $muted; }
QPushButton#cliToggle:checked { color: $amber; }
QFrame#cli { background: $panel; border: 1px solid $line; border-radius: 8px; }
QPushButton#copy { padding: 2px 10px; font-size: 11px; font-weight: 600; }
QProgressBar {
    background: $panel2; border: 1px solid $line; border-radius: 5px;
    max-height: 10px;
}
QProgressBar::chunk { background: $amber; border-radius: 4px; }

QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: $line; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMessageBox QLabel { color: $text; }
""").substitute(PALETTE)
