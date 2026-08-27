"""Shared test fixtures: headless Qt and isolated journals."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
import stampla.journal as journal_module
from PySide6 import QtWidgets


@pytest.fixture(scope="session")
def qapp() -> QtWidgets.QApplication:
    instance = QtWidgets.QApplication.instance()
    if isinstance(instance, QtWidgets.QApplication):
        return instance
    return QtWidgets.QApplication([])


@pytest.fixture(autouse=True)
def isolated_journal_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test's journals out of the user's real journal directory."""
    monkeypatch.setattr(journal_module, "default_journal_dir", lambda: tmp_path / "journals")


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A modal dialog in a headless run blocks forever — the Windows CI
    hang of 2026-08-27 was an unexpected QMessageBox.warning doing
    exactly that. Every modal auto-dismisses with its default/cancel
    answer and is recorded, so an unexpected dialog fails an assertion
    instead of hanging the suite. Tests that need a specific answer
    monkeypatch the dialog themselves, which overrides this.
    """
    shown: list[str] = []

    def record_exec(self: QtWidgets.QMessageBox) -> int:
        shown.append(self.text())
        # the default button, or Cancel: never the destructive choice
        default = self.defaultButton()
        if default is not None:
            return int(self.standardButton(default))
        return int(QtWidgets.QMessageBox.StandardButton.Cancel)

    def record_static(kind: str) -> object:
        def handler(*args: object, **_kwargs: object) -> QtWidgets.QMessageBox.StandardButton:
            text = str(args[2]) if len(args) > 2 else kind
            shown.append(f"{kind}: {text}")
            return QtWidgets.QMessageBox.StandardButton.Ok

        return staticmethod(handler)

    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", record_exec)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", record_static("warning"))
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", record_static("critical"))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", record_static("information"))
    return shown
