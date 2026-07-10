"""The Settings view: the archive configuration, without a text editor.

The TOML file stays the single source of truth — this view edits it in
place, preserving comments and layout (tomlkit), and nothing reaches
the disk without passing the library's own ``load_config`` first: a
broken configuration can never be written. The naming pattern is shown
but not editable here — changing what names *mean* renames every file
in the archive (a migration), which deserves the config file, the
documentation, and both eyes open.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import tomlkit
from stampla.config import ConfigError, load_config
from PySide6 import QtWidgets

from stampla_desktop import theme
from stampla_desktop.base import MONO, Archive, Page, card, rich_label

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

BLURB = "Edit the archive configuration — validated before every save, comments preserved."

MEDIA_KINDS = ("photo", "video")


class TreeRow:
    """One archive tree in the editable list."""

    def __init__(self, parent: QtWidgets.QWidget, path: str, media: str, layout: str) -> None:
        self.widget = QtWidgets.QWidget(parent)
        row = QtWidgets.QHBoxLayout(self.widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.path = QtWidgets.QLineEdit(path)
        self.path.setPlaceholderText("subfolder, e.g. Photos")
        self.media = QtWidgets.QComboBox()
        self.media.addItems(MEDIA_KINDS)
        self.media.setCurrentText(media)
        self.layout_edit = QtWidgets.QLineEdit(layout)
        self.layout_edit.setPlaceholderText("{yyyy}/{yyyy}-{mm}")
        self.remove = QtWidgets.QPushButton("Remove")
        self.remove.setObjectName("danger")
        row.addWidget(self.path, 2)
        row.addWidget(self.media, 1)
        row.addWidget(self.layout_edit, 2)
        row.addWidget(self.remove, 0)


class SettingsPage(Page):
    def __init__(self, window: MainWindow) -> None:
        super().__init__("Settings", window)
        self.subtitle.setText(
            "The configuration lives in a plain TOML file you can also edit by"
            " hand — this view reads and writes that same file, keeping your"
            " comments. Nothing is saved unless the whole configuration is valid."
        )
        self._mtime: float | None = None
        self.tree_rows: list[TreeRow] = []

        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        reload_button = QtWidgets.QPushButton("Reload from file")
        reload_button.clicked.connect(self.reload)
        open_button = QtWidgets.QPushButton("Open in editor")
        open_button.clicked.connect(self.open_in_editor)
        self.path_label = QtWidgets.QLabel(str(self.archive.config_path))
        self.path_label.setObjectName("faint")
        self.toolbar.addWidget(self.save_button)
        self.toolbar.addWidget(reload_button)
        self.toolbar.addWidget(open_button)
        self.toolbar.addWidget(self.path_label, 1)

        self.build_form()
        self.reload()

    # --- form ----------------------------------------------------------

    def build_form(self) -> None:
        self.error_label = rich_label("")
        self.error_label.setVisible(False)
        self.add_card(self.error_label)

        frame, layout = card()
        layout.addWidget(rich_label("<b>Archive</b>"))
        form = QtWidgets.QFormLayout()
        self.root_edit = QtWidgets.QLineEdit()
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self.browse_root)
        root_row = QtWidgets.QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(browse)
        form.addRow("Archive folder", root_row)
        self.timezone_edit = QtWidgets.QLineEdit()
        self.timezone_edit.setPlaceholderText("e.g. Europe/Warsaw")
        form.addRow("Timezone", self.timezone_edit)
        timezone_note = QtWidgets.QLabel(
            "Used only when a file carries a UTC-only timestamp (typically phone video)."
        )
        timezone_note.setObjectName("faint")
        timezone_note.setWordWrap(True)
        form.addRow("", timezone_note)
        layout.addLayout(form)
        self.add_card(frame)

        frame, layout = card()
        layout.addWidget(
            rich_label(
                "<b>Trees</b>&nbsp;&nbsp;"
                f'<span style="color:{theme.PALETTE["muted"]}">Subfolders of the archive,'
                " one per media kind. Layout tokens: {yyyy} {mm} {dd} {shoot}.</span>"
            )
        )
        self.trees_host = QtWidgets.QVBoxLayout()
        self.trees_host.setSpacing(6)
        layout.addLayout(self.trees_host)
        add_tree = QtWidgets.QPushButton("Add tree")
        add_tree.clicked.connect(lambda: self.add_tree_row("", "photo", "{yyyy}/{yyyy}-{mm}"))
        layout.addWidget(add_tree, 0, alignment=self.trees_host.alignment())
        self.add_card(frame)

        frame, layout = card()
        layout.addWidget(rich_label("<b>Import</b>"))
        form = QtWidgets.QFormLayout()
        self.ignore_edit = QtWidgets.QPlainTextEdit()
        self.ignore_edit.setPlaceholderText("one glob per line, e.g. NIKON001.DSC")
        self.ignore_edit.setFixedHeight(70)
        form.addRow("Ignore on card", self.ignore_edit)
        self.twins_check = QtWidgets.QCheckBox("Skip a JPEG when its RAW twin is in the same group")
        form.addRow("", self.twins_check)
        layout.addLayout(form)
        self.add_card(frame)

        frame, layout = card()
        layout.addWidget(
            rich_label(
                "<b>Lightroom / DAM</b>&nbsp;&nbsp;"
                f'<span style="color:{theme.PALETTE["muted"]}">Trees whose masters are'
                " renamed by the DAM (via the rename token), not directly.</span>"
            )
        )
        form = QtWidgets.QFormLayout()
        self.dam_trees_edit = QtWidgets.QLineEdit()
        self.dam_trees_edit.setPlaceholderText("comma-separated tree paths; empty = no DAM")
        form.addRow("DAM-managed trees", self.dam_trees_edit)
        layout.addLayout(form)
        self.add_card(frame)

        frame, layout = card()
        layout.addWidget(
            rich_label(
                "<b>Naming pattern</b>&nbsp;&nbsp;"
                f'<span style="color:{theme.PALETTE["warn"]}">shown, not editable here</span>'
            )
        )
        self.pattern_label = rich_label("")
        layout.addWidget(self.pattern_label)
        pattern_note = QtWidgets.QLabel(
            "Changing the pattern changes what every name means — a migration that"
            " renames the whole archive. If that is really what you want, edit the"
            " config file by hand with the design document open."
        )
        pattern_note.setObjectName("faint")
        pattern_note.setWordWrap(True)
        layout.addWidget(pattern_note)
        self.add_card(frame)

    def add_tree_row(self, path: str, media: str, layout_value: str) -> None:
        row = TreeRow(self, path, media, layout_value)
        row.remove.clicked.connect(lambda _=False, r=row: self.remove_tree_row(r))
        self.tree_rows.append(row)
        self.trees_host.addWidget(row.widget)

    def remove_tree_row(self, row: TreeRow) -> None:
        self.tree_rows.remove(row)
        row.widget.setParent(None)
        row.widget.deleteLater()

    def browse_root(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose the archive folder")
        if chosen:
            self.root_edit.setText(chosen)

    def open_in_editor(self) -> None:
        from PySide6 import QtCore, QtGui

        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.archive.config_path)))

    # --- load ----------------------------------------------------------

    def reload(self) -> None:
        """Populate the form from the file (not from memory)."""
        config_path = self.archive.config_path
        try:
            config = load_config(config_path)
            self._mtime = config_path.stat().st_mtime
        except (ConfigError, OSError, ValueError) as error:
            self.show_error(f"The file on disk does not load: {error}")
            return
        self.show_error(None)

        self.root_edit.setText(config.root or "")
        self.timezone_edit.setText(getattr(config, "timezone", "") or _timezone_of(config))
        for row in list(self.tree_rows):
            self.remove_tree_row(row)
        for tree in config.trees:
            self.add_tree_row(str(tree.path), tree.media, tree.layout)
        self.ignore_edit.setPlainText("\n".join(config.import_ignore))
        self.twins_check.setChecked(config.skip_jpeg_twins)
        self.dam_trees_edit.setText(", ".join(config.dam.trees) if config.dam else "")
        pattern = config.pattern
        self.pattern_label.setText(
            f'<span style="{MONO}">{pattern.name}: {pattern.datetime_format}'
            f" + {pattern.digest}:{pattern.digest_length}</span>"
        )
        self.status("Settings loaded from the file.")

    def check_external_edit(self) -> None:
        """Warn when the file changed on disk since the form was loaded."""
        try:
            current = self.archive.config_path.stat().st_mtime
        except OSError:
            return
        if self._mtime is not None and current != self._mtime:
            self.show_error(
                "The config file changed on disk since this form was loaded —"
                " Reload before editing, or your save will overwrite those changes."
            )

    # --- save ----------------------------------------------------------

    def save(self) -> None:
        config_path = self.archive.config_path
        try:
            document = tomlkit.parse(config_path.read_text(encoding="utf-8"))
        except OSError as error:
            self.show_error(f"Cannot read the config file: {error}")
            return

        document["root"] = self.root_edit.text().strip()
        dates = document.setdefault("dates", tomlkit.table())
        timezone = self.timezone_edit.text().strip()
        if timezone:
            dates["timezone"] = timezone
        if self.tree_rows:
            trees = tomlkit.aot()
            for row in self.tree_rows:
                entry = tomlkit.table()
                entry["path"] = row.path.text().strip()
                entry["media"] = row.media.currentText()
                entry["layout"] = row.layout_edit.text().strip()
                trees.append(entry)
            document["trees"] = trees
        else:
            # an empty array survives to validation (an empty AOT would vanish)
            document["trees"] = tomlkit.array()
        importer = document.setdefault("import", tomlkit.table())
        globs = [line.strip() for line in self.ignore_edit.toPlainText().splitlines()]
        importer["ignore"] = [g for g in globs if g]
        importer["skip_jpeg_twins"] = self.twins_check.isChecked()
        dam_trees = [t.strip() for t in self.dam_trees_edit.text().split(",") if t.strip()]
        if dam_trees:
            dam = document.setdefault("dam", tomlkit.table())
            dam["trees"] = dam_trees
        elif "dam" in document:
            del document["dam"]

        rendered = tomlkit.dumps(document)
        if timezone:
            try:
                ZoneInfo(timezone)
            except (KeyError, ValueError):
                self.show_error(f"Unknown timezone: {timezone!r} (expected e.g. Europe/Warsaw)")
                return

        # nothing reaches the real file unless the library accepts it whole
        scratch_fd, scratch_name = tempfile.mkstemp(suffix=".toml", dir=str(config_path.parent))
        scratch = Path(scratch_name)
        try:
            with os.fdopen(scratch_fd, "w", encoding="utf-8") as stream:
                stream.write(rendered)
            try:
                load_config(scratch)
            except (ConfigError, ValueError) as error:
                self.show_error(f"Not saved — the configuration would be invalid: {error}")
                return
            os.replace(scratch, config_path)
        finally:
            scratch.unlink(missing_ok=True)

        self._mtime = config_path.stat().st_mtime
        self.show_error(None)
        self.window_.reload_archive()
        self.status("Settings saved and validated — all views now use the new configuration.")

    def show_error(self, message: str | None) -> None:
        if message is None:
            self.error_label.setVisible(False)
            return
        self.error_label.setText(
            f'<span style="color:{theme.PALETTE["crit"]}"><b>{message}</b></span>'
        )
        self.error_label.setVisible(True)


def _timezone_of(config: object) -> str:
    """The configured timezone name, as written in the file."""
    tzinfo = getattr(config, "tzinfo", None)
    return str(tzinfo) if tzinfo is not None else ""


def reload_archive(window: MainWindow) -> Archive | None:
    """Re-read the config into a fresh Archive; None if it does not load."""
    try:
        config = load_config(window.archive.config_path)
    except (ConfigError, OSError, ValueError):
        return None
    root = Path(config.root).expanduser().resolve() if config.root else window.archive.root
    return Archive(window.archive.config_path, config, root)
