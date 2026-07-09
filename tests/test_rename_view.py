"""Tests for the Rename view against a real miniature archive."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.rename import RenamePage
from tests.support import make_master, spin, write_config

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)


def rename_page(window: MainWindow) -> RenamePage:
    for index in range(window.stack.count()):
        widget = window.stack.widget(index)
        if isinstance(widget, RenamePage):
            return widget
    raise AssertionError("Rename view missing")


def labels_text(page: RenamePage) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


@pytest.fixture
def stale_archive(tmp_path: Path) -> Path:
    config = write_config(tmp_path)
    month = tmp_path / "Photos" / "2026" / "2026-02"
    stale = make_master(month, "2026:02:01 10:00:00")
    # the camera time moved two hours: the name is now stale
    stale.rename(month / ("20260201_080000_" + stale.name.split("_")[2]))
    return config


@requires_exiftool
class TestRenameView:
    def test_preview_renders_the_plan_and_enables_apply(
        self, qapp: QtWidgets.QApplication, stale_archive: Path
    ) -> None:
        window = MainWindow(load_archive(stale_archive))
        page = rename_page(window)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        assert page.apply_button.isEnabled()
        text = labels_text(page)
        assert "1 rename(s)" in text
        assert "20260201_080000" in text

    def test_apply_renames_on_disk_and_replans(
        self, qapp: QtWidgets.QApplication, stale_archive: Path, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(stale_archive))
        page = rename_page(window)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        page.start(apply=True)
        spin(qapp, lambda: not page.busy and not page._applying)
        month = tmp_path / "Photos" / "2026" / "2026-02"
        assert list(month.glob("20260201_100000_*.jpg"))
        assert not list(month.glob("20260201_080000_*.jpg"))
        assert not page.apply_button.isEnabled()  # the re-plan found nothing left
        assert "nothing to rename" in labels_text(page)
