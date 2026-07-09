"""Tests for the application shell."""

from __future__ import annotations

from pathlib import Path

import pytest
from stampla.config import ConfigError
from PySide6 import QtWidgets

from stampla_desktop.app import VIEWS, MainWindow
from stampla_desktop.base import load_archive
from tests.support import write_config


class TestLoadArchive:
    def test_resolves_the_root(self, tmp_path: Path) -> None:
        archive = load_archive(write_config(tmp_path))
        assert archive.root == tmp_path.resolve()

    def test_missing_root_is_a_config_error(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text('[[trees]]\npath = "Photos"\nmedia = "photo"\n')
        with pytest.raises(ConfigError):
            load_archive(config)


class TestMainWindow:
    def test_sidebar_lists_overview_and_every_view(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        assert window.sidebar.count() == 1 + len(VIEWS)
        item = window.sidebar.item(0)
        assert item is not None
        assert item.text() == "Overview"
        assert tmp_path.name in window.windowTitle()

    def test_go_switches_the_visible_page(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        window.go(0)
        assert window.stack.currentIndex() == 0
