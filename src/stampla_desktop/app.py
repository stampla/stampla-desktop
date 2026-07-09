"""Application entry: the window, the view registry, startup.

The app is a renderer of the library's plans and reports: every view
is a dry run, and Apply goes through the same validated, journaled
engine as the CLI. Views are named after the commands they wrap.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from stampla.config import ConfigError
from PySide6 import QtCore, QtWidgets

from stampla_desktop import theme, verify
from stampla_desktop.base import Archive, Page, load_archive
from stampla_desktop.overview import OverviewPage


@dataclass(frozen=True)
class ViewSpec:
    label: str
    blurb: str
    factory: Callable[[MainWindow], Page]


#: the sidebar, in order; Overview derives its task cards from this
VIEWS: tuple[ViewSpec, ...] = (ViewSpec("Verify", verify.BLURB, verify.VerifyPage),)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, archive: Archive) -> None:
        super().__init__()
        self.archive = archive
        self.settings = QtCore.QSettings("stampla", "desktop")
        self.setWindowTitle(f"Stampla — {archive.root.name}")

        self.sidebar = QtWidgets.QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        self.stack = QtWidgets.QStackedWidget()

        tasks = [(spec.label, spec.blurb, index) for index, spec in enumerate(VIEWS, start=1)]
        self.sidebar.addItem(QtWidgets.QListWidgetItem("Overview"))
        self.stack.addWidget(OverviewPage(self, tasks))
        for spec in VIEWS:
            self.sidebar.addItem(QtWidgets.QListWidgetItem(spec.label))
            self.stack.addWidget(spec.factory(self))

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage(f"Archive: {archive.root}")

    def go(self, index: int) -> None:
        self.sidebar.setCurrentRow(index)

    def update_sidebar_label(self, page: Page, text: str) -> None:
        """Views report their state through their sidebar entry."""
        item = self.sidebar.item(self.stack.indexOf(page))
        if item is not None:
            item.setText(text)


def pick_config(settings: QtCore.QSettings) -> Path | None:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    last = str(settings.value("config", ""))
    if last and Path(last).is_file():
        return Path(last)
    chosen, _ = QtWidgets.QFileDialog.getOpenFileName(
        None, "Open archive configuration", "", "Archive config (*.toml)"
    )
    return Path(chosen) if chosen else None


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Stampla")
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)

    settings = QtCore.QSettings("stampla", "desktop")
    config_path = pick_config(settings)
    if config_path is None:
        return 0
    try:
        archive = load_archive(config_path.expanduser().resolve())
    except (ConfigError, OSError, ValueError) as error:
        QtWidgets.QMessageBox.critical(None, "Stampla", str(error))
        return 2
    settings.setValue("config", str(config_path.expanduser().resolve()))

    window = MainWindow(archive)
    window.resize(1100, 720)
    window.show()
    return app.exec()
