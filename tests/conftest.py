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
