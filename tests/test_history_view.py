"""Tests for the History view with seeded journals."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6 import QtWidgets
from stampla.apply import apply_plan
from stampla.journal import GroupMove, Journal, Rename

import stampla_desktop.history as history_module
from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.history import HistoryPage
from tests.support import spin, write_config


def history_page(window: MainWindow) -> HistoryPage:
    for index in range(window.stack.count()):
        widget = window.stack.widget(index)
        if isinstance(widget, HistoryPage):
            return widget
    raise AssertionError("History view missing")


def labels_text(page: HistoryPage) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


def make_journal(root: Path, key: str, old: str, new: str) -> Journal:
    (root / old).write_bytes(b"x")
    move = GroupMove(key, (Rename(old=root / old, new=root / new),))
    return Journal.create(root, (move,), command="rename")


class TestHistoryView:
    def test_empty_history_says_so(self, qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        assert "No changes recorded" in labels_text(history_page(window))

    def test_statuses_and_actions_reflect_the_journal(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = write_config(tmp_path)
        journal = make_journal(tmp_path, "a", "a.bin", "b.bin")
        assert apply_plan(journal).ok

        window = MainWindow(load_archive(config))
        page = history_page(window)
        text = labels_text(page)
        assert "complete" in text
        assert "rename" in text

    def test_undo_reverts_and_refreshes(
        self,
        qapp: QtWidgets.QApplication,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config = write_config(tmp_path)
        journal = make_journal(tmp_path, "a", "a.bin", "b.bin")
        assert apply_plan(journal).ok
        assert not (tmp_path / "a.bin").exists()

        window = MainWindow(load_archive(config))
        page = history_page(window)
        monkeypatch.setattr(history_module, "confirm", lambda *args, **kwargs: True)
        page.confirm_undo(journal.path)
        spin(qapp, lambda: (tmp_path / "a.bin").exists())
        assert "undone" in labels_text(page)

    def test_partial_journal_offers_resume(
        self,
        qapp: QtWidgets.QApplication,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config = write_config(tmp_path)
        (tmp_path / "a.bin").write_bytes(b"a")
        (tmp_path / "b.bin").write_bytes(b"b")
        moves = (
            GroupMove("a", (Rename(old=tmp_path / "a.bin", new=tmp_path / "a2.bin"),)),
            GroupMove("b", (Rename(old=tmp_path / "b.bin", new=tmp_path / "b2.bin"),)),
        )
        journal = Journal.create(tmp_path, moves, command="rename")
        journal.mark_done("a")
        (tmp_path / "a.bin").rename(tmp_path / "a2.bin")  # group a applied pre-crash

        window = MainWindow(load_archive(config))
        page = history_page(window)
        assert "partial" in labels_text(page)

        monkeypatch.setattr(history_module, "confirm", lambda *args, **kwargs: True)
        page.confirm_resume(journal.path)
        # the file landing is mid-run: wait for the page to finish and
        # refresh, or the labels race the worker's done signal
        spin(qapp, lambda: not page.busy and (tmp_path / "b2.bin").exists())
        assert "complete" in labels_text(page)
