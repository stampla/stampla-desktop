"""Tests for the Import view — the verdict must never overpromise."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.import_view import ImportPage
from tests.support import TINY_JPEG, make_master, spin, write_config

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)


def import_page(window: MainWindow) -> ImportPage:
    for index in range(window.stack.count()):
        widget = window.stack.widget(index)
        if isinstance(widget, ImportPage):
            return widget
    raise AssertionError("Import view missing")


def labels_text(page: ImportPage) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


def make_card(tmp_path: Path) -> Path:
    card = tmp_path / "card"
    photo = make_master(card, "2026:07:01 10:00:00")
    photo.rename(card / "DSC_0001.JPG")  # camera-style original name
    return card


@requires_exiftool
class TestImportView:
    def test_preview_shows_the_plan_and_no_verdict(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path / "archive")))
        (tmp_path / "archive" / "Photos").mkdir(parents=True, exist_ok=True)
        page = import_page(window)
        page.set_source(make_card(tmp_path))
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "would be copied" in text
        assert "DSC_0001.JPG" in text
        # a dry run must never judge the card
        assert "safe to format" not in text.lower()
        assert page.apply_button.isEnabled()

    def test_applied_import_earns_the_green_verdict(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        archive_root = tmp_path / "archive"
        window = MainWindow(load_archive(write_config(archive_root)))
        (archive_root / "Photos").mkdir(parents=True, exist_ok=True)
        page = import_page(window)
        page.set_source(make_card(tmp_path))
        page.start(apply=True)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "safe to format" in text
        assert "NOT safe" not in text
        month = archive_root / "Photos" / "2026" / "2026-07"
        assert list(month.glob("20260701_100000_*.jpg"))

    def test_undatable_file_blocks_the_verdict(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        archive_root = tmp_path / "archive"
        window = MainWindow(load_archive(write_config(archive_root)))
        (archive_root / "Photos").mkdir(parents=True, exist_ok=True)
        card = tmp_path / "card"
        card.mkdir()
        (card / "NODATE.JPG").write_bytes(TINY_JPEG)  # no capture time anywhere

        page = import_page(window)
        page.set_source(card)
        page.start(apply=True)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "NOT safe to format" in text
        assert "no capture time found" in text

    def test_source_is_required_before_running(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path / "archive")))
        page = import_page(window)
        assert not page.preview_button.isEnabled()
        page.start(apply=False)  # must be a no-op without a source
        assert not page.busy


class TestPolicyIgnoredFiles:
    """A card where every file is excluded must not preview as empty."""

    def test_all_ignored_card_explains_itself(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = write_config(tmp_path / "archive", '\n[import]\nignore = ["*.jpg"]\n')
        window = MainWindow(load_archive(config))
        card = tmp_path / "card"
        card.mkdir()
        (card / "DSC_0001.jpg").write_bytes(TINY_JPEG)

        page = import_page(window)
        page.set_source(card)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "1 ignored by policy" in text
        assert "excluded by your import ignore patterns" in text
        assert "*.jpg" in text
