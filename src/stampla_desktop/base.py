"""Shared page scaffolding and small UI helpers.

Every view is a :class:`Page`: a title, a toolbar, and a scrollable
body of cards. Pages that run long library calls add work controls —
a progress bar fed by the worker's events and a Stop button that
cancels at the library's next safe point.

GUI and CLI are meant to be used interchangeably, so every action can
show its exact terminal equivalent: a quiet ``>_`` toggle reveals a
panel of copyable commands, and confirmation dialogs carry the command
under Show Details.
"""

from __future__ import annotations

import html
import shlex
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from stampla.config import Config, ConfigError, load_config
from stampla.progress import ProgressEvent
from PySide6 import QtCore, QtWidgets

from stampla_desktop import theme

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

MONO = "font-family: Menlo, monospace; font-size: 12px;"


@dataclass(frozen=True)
class Archive:
    config_path: Path
    config: Config
    root: Path


def load_archive(config_path: Path) -> Archive:
    config = load_config(config_path)
    if not config.root:
        raise ConfigError(f"{config_path}: no archive root set")
    return Archive(config_path, config, Path(config.root).expanduser().resolve())


def clear_layout(layout: QtWidgets.QLayout) -> None:
    while (item := layout.takeAt(0)) is not None:
        if widget := item.widget():
            # unparent immediately: a merely take()n widget keeps painting
            # at its old geometry until the deferred delete runs
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif child := item.layout():
            clear_layout(child)


def card() -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    frame = QtWidgets.QFrame()
    frame.setObjectName("card")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    return frame, layout


def rich_label(text: str, wrap: bool = True) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setTextFormat(QtCore.Qt.TextFormat.RichText)
    label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(wrap)
    return label


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def when(stamp: str) -> str:
    """A journal's UTC creation stamp, rendered in local time."""
    try:
        moment = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return stamp
    return moment.astimezone().strftime("%Y-%m-%d %H:%M")


def diff_html(old: str, new: str) -> str:
    """``new`` with the span that differs from ``old`` in amber."""
    prefix = 0
    while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < min(len(old), len(new)) - prefix
        and old[len(old) - 1 - suffix] == new[len(new) - 1 - suffix]
    ):
        suffix += 1
    head, mid, tail = new[:prefix], new[prefix : len(new) - suffix], new[len(new) - suffix :]
    return (
        f'<span style="color:{theme.PALETTE["faint"]}">{html.escape(head)}</span>'
        f'<span style="color:{theme.PALETTE["amber"]}">{html.escape(mid)}</span>'
        f'<span style="color:{theme.PALETTE["faint"]}">{html.escape(tail)}</span>'
    )


def cli(*args: object) -> str:
    """The exact terminal command for an action."""
    return "stampla " + shlex.join(str(arg) for arg in args)


def confirm(
    parent: QtWidgets.QWidget,
    title: str,
    question: str,
    note: str,
    command: str | None = None,
) -> bool:
    """Yes/Cancel dialog; the terminal equivalent sits under Show Details."""
    box = QtWidgets.QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(question)
    box.setInformativeText(note)
    if command is not None:
        box.setDetailedText(f"Terminal equivalent:\n\n$ {command}")
    box.setStandardButtons(
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel
    )
    box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Cancel)
    return box.exec() == QtWidgets.QMessageBox.StandardButton.Yes


class CliPanel(QtWidgets.QFrame):
    """The terminal equivalents of a page's actions, with Copy."""

    def __init__(self, page: Page, provider: Callable[[], list[tuple[str, str]]]) -> None:
        super().__init__()
        self.setObjectName("cli")
        self.page = page
        self.provider = provider
        self.rows = QtWidgets.QVBoxLayout(self)
        self.rows.setContentsMargins(12, 10, 12, 10)
        self.rows.setSpacing(6)
        self.setVisible(False)

    def refresh(self) -> None:
        clear_layout(self.rows)
        faint = theme.PALETTE["faint"]
        for label, command in self.provider():
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            tag = QtWidgets.QLabel(label)
            tag.setObjectName("faint")
            layout.addWidget(tag)
            layout.addWidget(
                rich_label(
                    f'<span style="color:{faint}">$</span>'
                    f' <span style="{MONO}">{html.escape(command)}</span>'
                ),
                1,
            )
            copy_button = QtWidgets.QPushButton("Copy")
            copy_button.setObjectName("copy")
            copy_button.clicked.connect(lambda _=False, c=command: self.copy(c))
            layout.addWidget(copy_button, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            self.rows.addWidget(row)

    def copy(self, command: str) -> None:
        QtWidgets.QApplication.clipboard().setText(command)
        self.page.status(f"Copied — paste into a terminal: {command}")


class Page(QtWidgets.QWidget):
    """Header + toolbar + scrollable body, shared by all views."""

    #: a view's resting one-line status, shown when it becomes visible idle
    ready_status: str = ""

    def __init__(self, title: str, window: MainWindow) -> None:
        super().__init__()
        self.window_ = window
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 22)
        outer.setSpacing(12)

        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("h1")
        self.subtitle = QtWidgets.QLabel("")
        self.subtitle.setObjectName("sub")
        self.subtitle.setWordWrap(True)
        outer.addWidget(self.title)
        outer.addWidget(self.subtitle)

        self.toolbar = QtWidgets.QHBoxLayout()
        self.toolbar.setSpacing(10)
        outer.addLayout(self.toolbar)

        body_host = QtWidgets.QWidget()
        self.body = QtWidgets.QVBoxLayout(body_host)
        self.body.setContentsMargins(0, 6, 0, 0)
        self.body.setSpacing(12)
        self.body.addStretch()

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body_host)
        outer.addWidget(scroll, 1)
        self._outer = outer

    @property
    def archive(self) -> Archive:
        return self.window_.archive

    def status(self, message: str) -> None:
        self.window_.statusBar().showMessage(message)

    def resting_status(self) -> str:
        """The one-line status a view shows when it becomes visible and idle."""
        return self.ready_status or f"Archive: {self.archive.root}"

    def show_empty(self, glyph: str, title: str, hint: str) -> None:
        """Replace the body with a centered glyph/title/hint placeholder."""
        self.clear_body()
        block = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(block)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        for text, name in ((glyph, "emptyGlyph"), (title, "emptyTitle"), (hint, "emptyHint")):
            label = QtWidgets.QLabel(text)
            label.setObjectName(name)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
            label.setWordWrap(True)
            layout.addWidget(label)
        # body already ends with a stretch; a leading stretch centers the block
        self.body.insertStretch(0)
        self.body.insertWidget(1, block, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

    def add_card(self, widget: QtWidgets.QWidget) -> None:
        self.body.insertWidget(self.body.count() - 1, widget)

    def clear_body(self) -> None:
        clear_layout(self.body)
        self.body.addStretch()

    def add_work_controls(self) -> None:
        """A progress bar and Stop button for pages that run long work."""
        self.cancel = threading.Event()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.setObjectName("danger")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self._stop_clicked)
        self.toolbar.addWidget(self.progress_bar)
        self.toolbar.addWidget(self.stop_button)

    def _stop_clicked(self) -> None:
        self.cancel.set()
        self.stop_button.setEnabled(False)
        self.status("Stopping at the next safe point…")

    def work_started(self) -> None:
        self.cancel.clear()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.stop_button.setEnabled(True)
        self.stop_button.setVisible(True)

    def work_finished(self) -> None:
        self.progress_bar.setVisible(False)
        self.stop_button.setVisible(False)

    def show_progress(self, event: ProgressEvent) -> None:
        if event.total:
            self.progress_bar.setRange(0, event.total)
            self.progress_bar.setValue(event.done)
        else:
            self.progress_bar.setRange(0, 0)  # amount of work not known yet
        counted = f" of {event.total}" if event.total else ""
        name = f" — {event.path.name}" if event.path is not None else ""
        self.status(f"{event.phase}: {event.done}{counted}{name}")

    def add_cli(self, provider: Callable[[], list[tuple[str, str]]]) -> None:
        """A quiet ``>_`` toggle revealing the actions' terminal commands."""
        self.cli_panel = CliPanel(self, provider)
        self._outer.insertWidget(3, self.cli_panel)
        self.cli_toggle = QtWidgets.QPushButton(">_")
        self.cli_toggle.setObjectName("cliToggle")
        self.cli_toggle.setCheckable(True)
        self.cli_toggle.setToolTip("Show the terminal command for these actions")
        self.cli_toggle.clicked.connect(self.window_.set_cli)
        self.toolbar.addWidget(self.cli_toggle)
        self.window_.register_cli(self)
