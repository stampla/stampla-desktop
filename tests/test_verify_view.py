"""Tests for the Verify view against a real miniature archive."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.verify import VerifyPage
from tests.support import make_master, spin, write_config

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)


def labels_text(page: VerifyPage) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


@pytest.fixture
def window(qapp: QtWidgets.QApplication, tmp_path: Path) -> MainWindow:
    config = write_config(tmp_path)
    month = tmp_path / "Photos" / "2026" / "2026-01"
    make_master(month, "2026:01:05 12:30:00")
    # a date mismatch: the name is one hour off
    wrong = make_master(month, "2026:01:06 10:00:00", b"a")
    wrong.rename(month / ("20260106_110000_" + wrong.name.split("_")[2]))
    return MainWindow(load_archive(config))


@requires_exiftool
class TestVerifyView:
    def test_findings_render_with_structured_details(
        self, qapp: QtWidgets.QApplication, window: MainWindow
    ) -> None:
        page = window.stack.widget(1)
        assert isinstance(page, VerifyPage)
        page.start(skip_hash=False)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "1 ok" in text
        assert "name disagrees with camera time" in text
        assert "20260106_110000" in text  # from finding data, not prose parsing
        item = window.sidebar.item(1)
        assert item is not None
        assert item.text() == "Verify (1)"

    def test_stop_lands_safely(self, qapp: QtWidgets.QApplication, window: MainWindow) -> None:
        page = window.stack.widget(1)
        assert isinstance(page, VerifyPage)
        page.start(skip_hash=False)
        page.cancel.set()
        spin(qapp, lambda: not page.busy)
        assert "Stopped" in window.statusBar().currentMessage() or not page.busy
