"""Tests for the Relocate view against a real miniature archive.

Relocate derives a file's home from its name alone, so these tests
need no exiftool: named files are written straight onto disk in the
wrong folder.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6 import QtWidgets

from stampla_desktop import relocate as relocate_module
from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.relocate import RelocatePage
from tests.support import TINY_JPEG, page_of, spin, write_config

# a July group shelved under 2026-01: the name says it belongs in 2026-07
PREFIX = "20260703_150727_9b677b64"


def relocate_page(window: MainWindow) -> RelocatePage:
    page = page_of(window, RelocatePage)
    assert isinstance(page, RelocatePage)
    return page


def labels_text(page: RelocatePage) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


def misplace_group(root: Path) -> Path:
    """A jpg + xmp group under 2026-01 whose name belongs in 2026-07."""
    wrong = root / "Photos" / "2026" / "2026-01"
    wrong.mkdir(parents=True)
    (wrong / f"{PREFIX}.jpg").write_bytes(TINY_JPEG)
    (wrong / f"{PREFIX}.xmp").write_text("<x/>")
    return wrong


class TestRelocateView:
    def test_plan_shows_the_move_and_enables_apply(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = write_config(tmp_path)
        misplace_group(tmp_path)
        window = MainWindow(load_archive(config))
        page = relocate_page(window)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        assert page.apply_button.isEnabled()
        text = labels_text(page)
        assert "1 group(s) to move" in text
        assert "in the wrong folder" in text
        assert "2026-01" in text
        assert "2026-07" in text

    def test_apply_moves_both_files_and_reports_moved(
        self, qapp: QtWidgets.QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = write_config(tmp_path)
        wrong = misplace_group(tmp_path)
        window = MainWindow(load_archive(config))
        page = relocate_page(window)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        monkeypatch.setattr(relocate_module, "confirm", lambda *args, **kwargs: True)
        page.confirm_apply()
        spin(qapp, lambda: not page.busy and not page._applying)

        right = tmp_path / "Photos" / "2026" / "2026-07"
        assert (right / f"{PREFIX}.jpg").exists()
        assert (right / f"{PREFIX}.xmp").exists()
        assert not list(wrong.glob("*"))
        # apply re-plans automatically; the moved files leave nothing behind
        assert not page.apply_button.isEnabled()
        assert "Everything is where its name says it belongs" in labels_text(page)

    def test_nothing_misplaced_shows_the_calm_empty_message(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = write_config(tmp_path)
        # a correctly shelved July group: nothing to move
        right = tmp_path / "Photos" / "2026" / "2026-07"
        right.mkdir(parents=True)
        (right / f"{PREFIX}.jpg").write_bytes(TINY_JPEG)
        window = MainWindow(load_archive(config))
        page = relocate_page(window)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        assert not page.apply_button.isEnabled()
        assert "Everything is where its name says it belongs" in labels_text(page)

    def test_dam_tree_shows_the_lightroom_checklist_and_moves_nothing(
        self, qapp: QtWidgets.QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = write_config(tmp_path, extra='\n[dam]\ntrees = ["Photos"]\n')
        wrong = misplace_group(tmp_path)
        window = MainWindow(load_archive(config))
        page = relocate_page(window)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "Do this inside Lightroom" in text
        assert "DAM-managed" in text
        assert "in the wrong folder" in text
        # a DAM-managed tree yields no moves, so Apply stays disabled
        assert not page.apply_button.isEnabled()

        # even forced, an apply moves nothing the DAM tracks
        monkeypatch.setattr(relocate_module, "confirm", lambda *args, **kwargs: True)
        page.confirm_apply()
        spin(qapp, lambda: not page.busy and not page._applying)
        assert (wrong / f"{PREFIX}.jpg").exists()
        assert not (tmp_path / "Photos" / "2026" / "2026-07").exists()

    def test_shoot_tree_shows_the_caveat_hint(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = tmp_path / "config.toml"
        tmp_path.mkdir(parents=True, exist_ok=True)
        # a shoot-organized tree: the shoot segment is not derivable from names
        config.write_text(
            f"root = {str(tmp_path)!r}\n\n"
            '[[trees]]\npath = "Photos"\nmedia = "photo"\nlayout = "{yyyy}/{shoot}"\n\n'
            '[extensions]\nraw = ["jpg"]\nmutable = []\n'
        )
        # a July file shelved under the wrong year, around the shoot segment
        wrong = tmp_path / "Photos" / "2025" / "beach"
        wrong.mkdir(parents=True)
        (wrong / f"{PREFIX}.jpg").write_bytes(TINY_JPEG)
        window = MainWindow(load_archive(config))
        page = relocate_page(window)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "in the wrong folder" in text
        assert "not derivable from" in text  # the shoot caveat hint
        assert not page.apply_button.isEnabled()
