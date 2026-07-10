"""Tests for the Organize view."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.import_view import ImportPage
from stampla_desktop.organize import OrganizePage
from tests.support import make_master, page_of, spin, write_config

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)


def labels_text(page: OrganizePage) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


@requires_exiftool
class TestOrganizeView:
    def test_analysis_reports_proposals_without_touching_anything(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path / "archive")))
        messy = tmp_path / "messy"
        photo = make_master(messy, "2026:07:01 10:00:00")
        original = messy / "holiday-pic.jpg"
        photo.rename(original)

        page = page_of(window, OrganizePage)
        assert isinstance(page, OrganizePage)
        page.source = messy
        page.analyze_button.setEnabled(True)
        page.start()
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "look importable" in text
        assert "holiday-pic.jpg" in text
        assert original.exists()  # organize never renames
        assert page.import_button.isEnabled()

    def test_hand_off_prefills_the_import_view(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path / "archive")))
        messy = tmp_path / "messy"
        messy.mkdir()
        page = page_of(window, OrganizePage)
        assert isinstance(page, OrganizePage)
        page.source = messy
        page.hand_off()

        import_page = page_of(window, ImportPage)
        assert isinstance(import_page, ImportPage)
        assert import_page.source == messy
        assert window.stack.currentWidget() is import_page

    def test_mtime_dated_files_are_flagged_for_review(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path / "archive")))
        messy = tmp_path / "messy"
        messy.mkdir()
        from tests.support import TINY_JPEG

        (messy / "stripped.jpg").write_bytes(TINY_JPEG)  # no capture time

        page = page_of(window, OrganizePage)
        assert isinstance(page, OrganizePage)
        page.source = messy
        page.analyze_button.setEnabled(True)
        page.start()
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "need your eyes" in text
        assert "modification time" in text


class TestPolicyIgnoredFiles:
    """Files excluded by ignore patterns must never be invisible.

    A folder where every file matches an import ignore pattern must not
    render as "0 of 0" — that reads as an empty folder and hides real
    files from the person deciding what to keep.
    """

    def test_all_ignored_folder_explains_itself(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        from tests.support import TINY_JPEG

        config = write_config(tmp_path / "archive", '\n[import]\nignore = ["*.jpg"]\n')
        window = MainWindow(load_archive(config))
        messy = tmp_path / "messy"
        messy.mkdir()
        (messy / "a.jpg").write_bytes(TINY_JPEG)
        (messy / "b.jpg").write_bytes(TINY_JPEG)

        page = page_of(window, OrganizePage)
        assert isinstance(page, OrganizePage)
        page.source = messy
        page.analyze_button.setEnabled(True)
        page.start()
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "2 ignored by policy" in text
        assert "excluded by your import ignore patterns" in text
        assert "*.jpg" in text
