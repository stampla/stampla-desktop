"""Application entry: the window, the view registry, startup.

The app is a renderer of the library's plans and reports: every view
is a dry run, and Apply goes through the same validated, journaled
engine as the CLI. Views are named after the commands they wrap.
"""

from __future__ import annotations

import shutil
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from stampla.config import ConfigError, load_config

from stampla_desktop import (
    history,
    import_view,
    organize,
    relocate,
    rename,
    settings,
    theme,
    verify,
)
from stampla_desktop.base import Archive, Page, load_archive
from stampla_desktop.overview import OverviewPage


@dataclass(frozen=True)
class ViewSpec:
    label: str
    blurb: str
    factory: Callable[[MainWindow], Page]


#: the sidebar, in order; Overview derives its task cards from this
VIEWS: tuple[ViewSpec, ...] = (
    ViewSpec("Import", import_view.BLURB, import_view.ImportPage),
    ViewSpec("Organize", organize.BLURB, organize.OrganizePage),
    ViewSpec("Verify", verify.BLURB, verify.VerifyPage),
    ViewSpec("Rename", rename.BLURB, rename.RenamePage),
    ViewSpec("Relocate", relocate.BLURB, relocate.RelocatePage),
    ViewSpec("History", history.BLURB, history.HistoryPage),
    ViewSpec("Settings", settings.BLURB, settings.SettingsPage),
)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, archive: Archive) -> None:
        super().__init__()
        self.archive = archive
        self.settings = QtCore.QSettings("stampla", "desktop")
        self._cli_pages: list[Page] = []
        self.setWindowTitle(f"Stampla — {archive.root.name}")

        self.sidebar = QtWidgets.QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.stack = QtWidgets.QStackedWidget()

        host = QtWidgets.QWidget()
        host.setObjectName("sidebarHost")
        host.setFixedWidth(190)
        host_layout = QtWidgets.QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        wordmark = QtWidgets.QLabel('<span style="color:#e8a33d">stamp</span>la')
        wordmark.setObjectName("wordmark")
        wordmark.setTextFormat(QtCore.Qt.TextFormat.RichText)
        host_layout.addWidget(wordmark)
        host_layout.addWidget(self.sidebar)

        tasks = [(spec.label, spec.blurb, index) for index, spec in enumerate(VIEWS, start=1)]
        self.sidebar.addItem(QtWidgets.QListWidgetItem("Overview"))
        self.stack.addWidget(OverviewPage(self, tasks))
        for spec in VIEWS:
            self.sidebar.addItem(QtWidgets.QListWidgetItem(spec.label))
            self.stack.addWidget(spec.factory(self))

        self.sidebar.currentRowChanged.connect(self._row_changed)
        self.sidebar.setCurrentRow(0)
        self.set_cli(bool(self.settings.value("show_cli", False, type=bool)))

        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(host)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage(f"Archive: {archive.root}")

    def _row_changed(self, row: int) -> None:
        """Switch views and freshen the status bar, so it never lies for the new view."""
        self.stack.setCurrentIndex(row)
        page = self.stack.widget(row)
        if isinstance(page, Page) and not getattr(page, "busy", False):
            self.statusBar().showMessage(page.resting_status())

    def go(self, index: int) -> None:
        self.sidebar.setCurrentRow(index)

    def update_sidebar_label(self, page: Page, text: str) -> None:
        """Views report their state through their sidebar entry."""
        item = self.sidebar.item(self.stack.indexOf(page))
        if item is not None:
            item.setText(text)

    def refresh_history(self) -> None:
        """Applying views tell History that the record grew."""
        for index in range(self.stack.count()):
            widget = self.stack.widget(index)
            if isinstance(widget, history.HistoryPage):
                widget.refresh()

    def reload_archive(self) -> None:
        """Settings saved: every view sees the new configuration at once."""
        fresh = settings.reload_archive(self)
        if fresh is None:
            self.statusBar().showMessage(
                "The saved configuration no longer loads — check Settings."
            )
            return
        self.archive = fresh
        self.setWindowTitle(f"Stampla — {fresh.root.name}")
        self.statusBar().showMessage(f"Archive: {fresh.root}")
        for index in range(self.stack.count()):
            widget = self.stack.widget(index)
            if isinstance(widget, OverviewPage):
                widget.refresh()
        for page in self._cli_pages:
            page.cli_panel.refresh()

    def register_cli(self, page: Page) -> None:
        self._cli_pages.append(page)

    def set_cli(self, visible: bool) -> None:
        """Show or hide the terminal equivalents everywhere at once."""
        for page in self._cli_pages:
            page.cli_toggle.setChecked(visible)
            page.cli_panel.setVisible(visible)
            if visible:
                page.cli_panel.refresh()
        self.settings.setValue("show_cli", visible)


#: written verbatim into a new archive's config; the ``{root}`` placeholder
#: is the only field filled in. Layout tokens are literal braces, so this is
#: a plain string (no ``str.format``) to keep every ``{ }`` correct TOML.
DEFAULT_CONFIG_TEMPLATE = """\
# Stampla archive configuration.
#
# This plain TOML file is the single source of truth for your archive.
# The Settings view reads and writes this same file, keeping your comments —
# you can also edit it here by hand.

root = "{root}"

# Trees are the subfolders of the archive, one per media kind.
# Layout tokens are literal braces: {yyyy} {mm} {dd} {shoot}.
[[trees]]
path = "Photos"
media = "photo"
layout = "{yyyy}/{yyyy}-{mm}"

[[trees]]
path = "Video"
media = "video"
layout = "{yyyy}/{yyyy}-{mm}"

# Import options (uncomment to use):
# [import]
# ignore = ["NIKON001.DSC"]      # globs skipped when reading a card
# skip_jpeg_twins = true         # skip a JPEG when its RAW twin is present

# Timezone used only for UTC-only timestamps (typically phone video):
# [dates]
# timezone = "Europe/Warsaw"
"""


def open_existing_config() -> Path | None:
    chosen, _ = QtWidgets.QFileDialog.getOpenFileName(
        None, "Open archive configuration", "", "Archive config (*.toml)"
    )
    return Path(chosen) if chosen else None


def create_archive_config() -> Path | None:
    """Set up a fresh archive: a folder and a validated default config in it."""
    chosen = QtWidgets.QFileDialog.getExistingDirectory(
        None, "Choose the folder that holds (or will hold) your archive"
    )
    if not chosen:
        return None
    folder = Path(chosen)
    config_path = folder / "stampla.toml"
    if config_path.exists():
        QtWidgets.QMessageBox.warning(
            None,
            "Stampla",
            f"{config_path} already exists — open it instead of creating a new one.",
        )
        return None

    config_path.write_text(DEFAULT_CONFIG_TEMPLATE.replace("{root}", str(folder)), encoding="utf-8")
    try:
        load_config(config_path)
    except (ConfigError, OSError, ValueError) as error:
        config_path.unlink(missing_ok=True)
        QtWidgets.QMessageBox.warning(
            None, "Stampla", f"Could not create a valid configuration: {error}"
        )
        return None
    return config_path


def first_run_dialog() -> Path | None:
    """Offer to open an existing archive or create a new one."""
    box = QtWidgets.QMessageBox()
    box.setWindowTitle("Stampla")
    box.setText("Open an existing archive configuration, or set up a new archive.")
    open_button = box.addButton("Open configuration…", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    create_button = box.addButton(
        "Create new archive…", QtWidgets.QMessageBox.ButtonRole.ActionRole
    )
    box.addButton("Cancel", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked is open_button:
        return open_existing_config()
    if clicked is create_button:
        return create_archive_config()
    return None


def exiftool_warning() -> str | None:
    """A user-facing explanation when ExifTool is absent, or None."""
    if shutil.which("exiftool"):
        return None
    hint = (
        "brew install exiftool"
        if sys.platform == "darwin"
        else "see https://exiftool.org/install.html"
    )
    return (
        "ExifTool is not installed, and reading capture times needs it —"
        " Import, Organize, Verify and Rename will fail until it is.\n\n"
        f"Install it ({hint}), then start Stampla again."
    )


def pick_config(settings: QtCore.QSettings) -> Path | None:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    last = str(settings.value("config", ""))
    if last and Path(last).is_file():
        return Path(last)
    return first_run_dialog()


def main() -> int:
    # Ctrl+C from a terminal: Python's KeyboardInterrupt never fires inside
    # the Qt event loop, so restore the default handler and just terminate.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Stampla")
    app.setApplicationDisplayName("Stampla")
    app.setWindowIcon(QtGui.QIcon(str(Path(__file__).parent / "resources" / "icon.png")))
    app.setStyle("Fusion")
    # An explicit real family: platforms without a themed default fall back
    # to the fictional "Sans Serif", which triggers a slow alias lookup
    app.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.GeneralFont))
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
    warning = exiftool_warning()
    if warning is not None:
        QtWidgets.QMessageBox.warning(window, "Stampla", warning)
    return app.exec()
