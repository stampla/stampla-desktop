"""Palette and application stylesheet (safelight amber on graphite)."""

from string import Template

PALETTE = {
    "bg": "#16181d",
    "panel": "#1e2128",
    "panel2": "#23262e",
    "panel3": "#2a2e37",
    "line": "#2e323c",
    "line_soft": "#262a33",
    "text": "#e9e7e2",
    "muted": "#9a9da6",
    "faint": "#6f727c",
    "amber": "#e8a33d",
    "amber_soft": "#8a6526",
    "amber_ink": "#241a08",
    "ok": "#63b984",
    "warn": "#d9a03f",
    "crit": "#d96459",
    "info": "#7ba3c9",
}

QSS = Template("""
QMainWindow { background: $bg; }
QWidget { background: $bg; color: $text; font-size: 13px; }

/* text never paints its own background: cards stay one surface */
QLabel, QCheckBox { background: transparent; }

QStatusBar { background: $panel; color: $muted; border-top: 1px solid $line_soft; }
QStatusBar::item { border: none; }

/* ---- sidebar ----------------------------------------------------- */
QWidget#sidebarHost { background: $panel; border-right: 1px solid $line_soft; }
QLabel#wordmark {
    font-family: Menlo, monospace; font-size: 14px; font-weight: 700;
    color: $text; padding: 18px 16px 12px 16px; background: transparent;
}
QListWidget#sidebar {
    background: $panel; border: none; padding: 0 8px; outline: 0;
}
QListWidget#sidebar::item {
    padding: 9px 12px; border-radius: 6px; color: $muted; margin-bottom: 1px;
}
QListWidget#sidebar::item:hover { background: $panel2; color: $text; }
QListWidget#sidebar::item:selected {
    background: $panel2; color: $text;
    border-left: 2px solid $amber;
}

/* ---- typography --------------------------------------------------- */
QLabel#h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.2px; }
QLabel#sub { color: $muted; }
QLabel#faint { color: $faint; font-size: 12px; }
QLabel#emptyGlyph { color: $faint; font-family: Menlo, monospace; font-size: 30px; }
QLabel#emptyTitle { color: $muted; font-size: 15px; font-weight: 600; }
QLabel#emptyHint { color: $faint; }

/* ---- cards -------------------------------------------------------- */
QFrame#card {
    background: $panel;
    border: 1px solid $line_soft;
    border-radius: 8px;
}
QFrame#card[severity="ok"]   { border-left: 3px solid $ok; }
QFrame#card[severity="warn"] { border-left: 3px solid $warn; }
QFrame#card[severity="crit"] { border-left: 3px solid $crit; }
QFrame#card[severity="info"] { border-left: 3px solid $info; }
QFrame#card QWidget { background: transparent; }
QFrame#card QLineEdit, QFrame#card QPlainTextEdit, QFrame#card QComboBox { background: $bg; }
QFrame#card QPushButton { background: $panel2; }
QFrame#card QPushButton#primary { background: $amber; }
QFrame#card QPushButton#danger { background: transparent; }

QFrame#banner[verdict="safe"] {
    background: #1c2b22; border: 1px solid #356049; border-radius: 8px;
}
QFrame#banner[verdict="unsafe"] {
    background: #2e1f1e; border: 1px solid #6b3833; border-radius: 8px;
}
QFrame#banner QWidget { background: transparent; }

/* ---- status pills -------------------------------------------------- */
QLabel#pill {
    border-radius: 9px; padding: 2px 10px;
    font-size: 11px; font-weight: 700;
}
QLabel#pill[status="complete"] { background: #1c2b22; color: $ok; }
QLabel#pill[status="partial"]  { background: #2d2517; color: $warn; }
QLabel#pill[status="undone"]   { background: $panel2; color: $muted; }
QLabel#pill[status="pending"]  { background: #1d2733; color: $info; }

/* ---- controls ------------------------------------------------------ */
QPushButton {
    background: $panel2; border: 1px solid $line; border-radius: 6px;
    padding: 6px 15px; font-weight: 600;
}
QPushButton:hover { background: $panel3; border-color: $faint; }
QPushButton:pressed { background: $panel; }
QPushButton:disabled { color: $faint; background: $panel; border-color: $line_soft; }
QPushButton#primary { background: $amber; color: $amber_ink; border: none; }
QPushButton#primary:hover { background: #f0b155; }
QPushButton#primary:disabled { background: $panel2; color: $faint; }
QPushButton#danger { background: transparent; color: $muted; border: 1px solid $line; }
QPushButton#danger:hover { color: $crit; border-color: #5a3a37; background: transparent; }

QCheckBox { color: $muted; spacing: 7px; }
QCheckBox:hover { color: $text; }

QLineEdit, QPlainTextEdit, QComboBox {
    background: $bg; border: 1px solid $line; border-radius: 6px;
    padding: 5px 9px; selection-background-color: $amber_soft;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: $amber_soft; }
QLineEdit:disabled, QComboBox:disabled { color: $faint; background: $panel; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid $muted; margin-right: 7px;
}
QComboBox QAbstractItemView {
    background: $panel2; border: 1px solid $line; selection-background-color: $panel3;
    color: $text;
}

QPushButton#cliToggle {
    background: transparent; border: none; color: $faint;
    font-family: Menlo, monospace; font-weight: 700; padding: 4px 8px;
}
QPushButton#cliToggle:hover { color: $muted; background: transparent; }
QPushButton#cliToggle:checked { color: $amber; }
QFrame#cli { background: $panel; border: 1px solid $line_soft; border-radius: 8px; }
QFrame#cli QWidget { background: transparent; }
QFrame#cli QPushButton { background: $panel2; }
QPushButton#copy { padding: 2px 10px; font-size: 11px; font-weight: 600; }

QProgressBar {
    background: $panel2; border: 1px solid $line_soft; border-radius: 5px;
    max-height: 10px;
}
QProgressBar::chunk { background: $amber; border-radius: 4px; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: $line; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $faint; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: $line; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QMessageBox QLabel { color: $text; background: transparent; }
QToolTip { background: $panel2; color: $text; border: 1px solid $line; }
""").substitute(PALETTE)
