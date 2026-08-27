"""The Settings view: the archive configuration, without a text editor.

The TOML file stays the single source of truth — this view edits it in
place, preserving comments and layout (tomlkit), and nothing reaches
the disk without passing the library's own ``load_config`` first: a
broken configuration can never be written. Editing the naming pattern
changes what every name *means*, so saving one starts a migration: the
old pattern is kept as recognized, and files named under it are
reported as pending until renamed.
"""

from __future__ import annotations

import hashlib
import html
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import tomlkit
from PySide6 import QtWidgets
from stampla.config import ConfigError, load_config
from stampla.pattern import MAX_PREFIX_LENGTH, NamingPattern, PatternError

from stampla_desktop import theme
from stampla_desktop.base import MONO, Archive, Page, card, rich_label

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

BLURB = "Edit the archive configuration — validated before every save, comments preserved."

MEDIA_KINDS = ("photo", "video")

#: algorithms that also support image-data hashing (ExifTool ImageDataHash)
DIGESTS = ("md5", "sha256", "sha512")

#: a stable, obviously-fake digest for the example name in the preview
SAMPLE_DIGEST = hashlib.sha512(b"stampla").hexdigest()

SAMPLE_CAPTURE = datetime(2026, 6, 10, 16, 10, 45)


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
    ready_status = "Changes are validated before they reach the file."

    def __init__(self, window: MainWindow) -> None:
        super().__init__("Settings", window)
        self.subtitle.setText(
            "The configuration lives in a plain TOML file you can also edit by"
            " hand — this view reads and writes that same file, keeping your"
            " comments. Nothing is saved unless the whole configuration is valid."
        )
        self._mtime: float | None = None
        self._loaded_pattern: NamingPattern | None = None
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
                f'<span style="color:{theme.PALETTE["muted"]}">How every file in the'
                " archive is named.</span>"
            )
        )
        form = QtWidgets.QFormLayout()
        self.pattern_name_edit = QtWidgets.QLineEdit()
        self.pattern_name_edit.setPlaceholderText("e.g. sha256-12")
        form.addRow("Name", self.pattern_name_edit)
        self.pattern_format_edit = QtWidgets.QLineEdit()
        self.pattern_format_edit.setPlaceholderText("%Y%m%d_%H%M%S")
        form.addRow("Timestamp", self.pattern_format_edit)
        format_note = QtWidgets.QLabel(
            "Must use each of %Y %m %d %H %M %S once, in that order — that is what"
            " keeps names sorting by capture time. Separating characters are yours"
            " to choose, as long as they are safe in filenames."
        )
        format_note.setObjectName("faint")
        format_note.setWordWrap(True)
        form.addRow("", format_note)
        self.pattern_separator_edit = QtWidgets.QLineEdit()
        self.pattern_separator_edit.setMaximumWidth(80)
        form.addRow("Separator", self.pattern_separator_edit)
        digest_row = QtWidgets.QHBoxLayout()
        self.pattern_digest_combo = QtWidgets.QComboBox()
        self.pattern_digest_combo.addItems(DIGESTS)
        self.pattern_length_spin = QtWidgets.QSpinBox()
        self.pattern_length_spin.setRange(4, 32)
        digest_row.addWidget(self.pattern_digest_combo, 0)
        digest_row.addWidget(QtWidgets.QLabel("first"), 0)
        digest_row.addWidget(self.pattern_length_spin, 0)
        digest_row.addWidget(QtWidgets.QLabel("characters"), 0)
        digest_row.addStretch(1)
        form.addRow("Fingerprint", digest_row)
        self.pattern_image_hash_edit = QtWidgets.QLineEdit()
        self.pattern_image_hash_edit.setPlaceholderText(
            "comma-separated extensions, e.g. jpg, dng, tif"
        )
        form.addRow("Image-data hash", self.pattern_image_hash_edit)
        image_hash_note = QtWidgets.QLabel(
            "Formats your DAM edits in place: hash only the image data, so names"
            " survive keyword and rating writes."
        )
        image_hash_note.setObjectName("faint")
        image_hash_note.setWordWrap(True)
        form.addRow("", image_hash_note)
        self.pattern_preview = rich_label("")
        form.addRow("Example", self.pattern_preview)
        layout.addLayout(form)
        pattern_note = QtWidgets.QLabel(
            "Changing the pattern changes what every name means. Saving a change"
            " starts a migration: the old pattern stays recognized, files named"
            " under it are reported as pending, and Rename migrates them."
        )
        pattern_note.setObjectName("faint")
        pattern_note.setWordWrap(True)
        layout.addWidget(pattern_note)
        self.add_card(frame)

        self.pattern_digest_combo.currentTextChanged.connect(self._digest_changed)
        for signal in (
            self.pattern_name_edit.textChanged,
            self.pattern_format_edit.textChanged,
            self.pattern_separator_edit.textChanged,
            self.pattern_image_hash_edit.textChanged,
        ):
            signal.connect(self.update_pattern_preview)
        self.pattern_length_spin.valueChanged.connect(self.update_pattern_preview)

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

    # --- pattern editor -------------------------------------------------

    def _digest_changed(self, digest: str) -> None:
        hex_length = hashlib.new(digest).digest_size * 2
        self.pattern_length_spin.setMaximum(hex_length)
        self.update_pattern_preview()

    def pattern_from_form(self) -> NamingPattern:
        """The pattern the form describes; raises PatternError when invalid."""
        extensions = [
            ext.strip().lstrip(".").lower()
            for ext in self.pattern_image_hash_edit.text().split(",")
        ]
        return NamingPattern(
            name=self.pattern_name_edit.text().strip(),
            datetime_format=self.pattern_format_edit.text(),
            digest=self.pattern_digest_combo.currentText(),
            digest_length=self.pattern_length_spin.value(),
            separator=self.pattern_separator_edit.text(),
            image_hash=frozenset(ext for ext in extensions if ext),
        )

    def update_pattern_preview(self) -> None:
        try:
            pattern = self.pattern_from_form()
        except (PatternError, ValueError) as error:
            self.pattern_preview.setText(
                f'<span style="color:{theme.PALETTE["crit"]}">{html.escape(str(error))}</span>'
            )
            return
        example = pattern.build_prefix(SAMPLE_CAPTURE, SAMPLE_DIGEST) + ".nef"
        note = ""
        if self.dam_trees_edit.text().strip() and pattern.prefix_length > MAX_PREFIX_LENGTH:
            note = (
                f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["crit"]}">'
                f"{pattern.prefix_length} characters — too long for the DAM rename"
                f" token, which must fit 32; at most {MAX_PREFIX_LENGTH} while"
                " DAM-managed trees are configured</span>"
            )
        self.pattern_preview.setText(f'<span style="{MONO}">{html.escape(example)}</span>{note}')

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
        self._loaded_pattern = pattern
        self.pattern_name_edit.setText(pattern.name)
        self.pattern_format_edit.setText(pattern.datetime_format)
        self.pattern_separator_edit.setText(pattern.separator)
        self.pattern_digest_combo.setCurrentText(pattern.digest)
        self._digest_changed(pattern.digest)
        self.pattern_length_spin.setValue(pattern.digest_length)
        self.pattern_image_hash_edit.setText(", ".join(sorted(pattern.image_hash)))
        self.update_pattern_preview()
        self.status("Settings loaded from the file.")

    def check_external_edit(self) -> bool:
        """True when the file changed on disk since the form was loaded."""
        try:
            current = self.archive.config_path.stat().st_mtime
        except OSError:
            return False
        return self._mtime is not None and current != self._mtime

    # --- save ----------------------------------------------------------

    def save(self) -> None:
        config_path = self.archive.config_path
        if self.check_external_edit():
            # writing the form now would silently discard the on-disk edit
            self.show_error(
                "Not saved — the config file changed on disk since this form"
                " was loaded. Reload first, then re-apply your changes."
            )
            return
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

        try:
            new_pattern = self.pattern_from_form()
        except (PatternError, ValueError) as error:
            self.show_error(f"Not saved — the naming pattern is invalid: {error}")
            return
        old_pattern = self._loaded_pattern
        if old_pattern is not None and new_pattern != old_pattern:
            if new_pattern.name == old_pattern.name:
                self.show_error(
                    "Not saved — a changed pattern needs a new name; the old one"
                    f" keeps {old_pattern.name!r} while the migration runs."
                )
                return
            if not self.confirm_migration(old_pattern, new_pattern):
                return
            pattern_table = document.setdefault("pattern", tomlkit.table())
            _write_pattern(pattern_table, new_pattern)
            additional = pattern_table.setdefault("additional", tomlkit.aot())
            if all(entry.get("name") != old_pattern.name for entry in additional):
                # the old scheme stays recognized until the migration finishes
                entry = tomlkit.table()
                _write_pattern(entry, old_pattern)
                additional.append(entry)

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

    def confirm_migration(self, old: NamingPattern, new: NamingPattern) -> bool:
        answer = QtWidgets.QMessageBox.question(
            self,
            "Change the naming pattern?",
            f"Every file is currently named by {old.name!r}; the archive would"
            f" switch to {new.name!r}.\n\nSaving starts a migration, it renames"
            " nothing by itself: the old pattern stays recognized, Verify reports"
            " files named under it as pending migration, and Rename brings them"
            " to the new scheme when you choose to.",
        )
        return answer == QtWidgets.QMessageBox.StandardButton.Yes

    def show_error(self, message: str | None) -> None:
        if message is None:
            self.error_label.setVisible(False)
            return
        self.error_label.setText(
            f'<span style="color:{theme.PALETTE["crit"]}"><b>{message}</b></span>'
        )
        self.error_label.setVisible(True)


def _write_pattern(table: tomlkit.items.Table, pattern: NamingPattern) -> None:
    """Write every pattern field explicitly — a migration is no place for defaults."""
    table["name"] = pattern.name
    table["datetime_format"] = pattern.datetime_format
    table["digest"] = pattern.digest
    table["digest_length"] = pattern.digest_length
    table["separator"] = pattern.separator
    table["image_hash"] = sorted(pattern.image_hash)


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
