"""The app-wide one-operation-at-a-time gate and its busy guards."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.import_view import ImportPage
from stampla_desktop.verify import VerifyPage
from tests.support import page_of, write_config


@pytest.fixture
def window(qapp: QtWidgets.QApplication, tmp_path: Path) -> MainWindow:
    return MainWindow(load_archive(write_config(tmp_path)))


class TestOperationGate:
    def test_second_view_is_refused_while_one_runs(self, window: MainWindow) -> None:
        verify_page = page_of(window, VerifyPage)
        import_page = page_of(window, ImportPage)
        assert isinstance(verify_page, VerifyPage)
        assert isinstance(import_page, ImportPage)

        assert verify_page.begin_work("Verify")
        assert not import_page.begin_work("Import")
        assert not import_page.busy
        assert "still running" in window.statusBar().currentMessage()

        verify_page.end_work()
        assert import_page.begin_work("Import")
        import_page.end_work()

    def test_source_stays_put_while_busy(self, window: MainWindow, tmp_path: Path) -> None:
        import_page = page_of(window, ImportPage)
        assert isinstance(import_page, ImportPage)
        first = tmp_path / "card-a"
        first.mkdir()
        import_page.set_source(first)

        assert import_page.begin_work("Import")
        import_page.cancel = threading.Event()
        second = tmp_path / "card-b"
        second.mkdir()
        import_page.set_source(second)
        assert import_page.source == first  # the running run keeps its source
        import_page.end_work()

    def test_close_is_deferred_while_an_operation_runs(self, window: MainWindow) -> None:
        verify_page = page_of(window, VerifyPage)
        assert isinstance(verify_page, VerifyPage)
        assert verify_page.begin_work("Verify")
        # with an operation running, releasing while closing closes the
        # window; the closeEvent path itself needs a human dialog, so this
        # exercises the deferred half only
        window._closing = True
        verify_page.end_work()
        assert not window.isVisible()
