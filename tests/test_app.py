"""Tests for the application shell."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6 import QtWidgets
from stampla.config import ConfigError, load_config

from stampla_desktop.app import VIEWS, MainWindow, create_archive_config
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


class TestCreateArchiveConfig:
    def test_create_archive_config_writes_a_loadable_default(
        self,
        qapp: QtWidgets.QApplication,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
        )
        path = create_archive_config()
        assert path is not None
        assert path.exists()
        load_config(path)  # loads without raising
        text = path.read_text()
        assert "Photos" in text
        assert "#" in text

    def test_create_archive_config_refuses_to_overwrite(
        self,
        qapp: QtWidgets.QApplication,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
        )
        warnings: list[str] = []
        monkeypatch.setattr(
            QtWidgets.QMessageBox,
            "warning",
            lambda *a, **k: warnings.append(a[2] if len(a) > 2 else ""),
        )

        first = create_archive_config()
        assert first is not None
        assert create_archive_config() is None
        assert warnings


def test_exiftool_warning_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from stampla_desktop import app as app_module

    monkeypatch.setattr("stampla_desktop.app.shutil.which", lambda _: None)
    warning = app_module.exiftool_warning()
    assert warning is not None
    assert "ExifTool" in warning
    assert "Import" in warning  # says what will break, not just what's missing


def test_no_warning_when_exiftool_present(monkeypatch: pytest.MonkeyPatch) -> None:
    from stampla_desktop import app as app_module

    monkeypatch.setattr("stampla_desktop.app.shutil.which", lambda _: "/opt/homebrew/bin/exiftool")
    assert app_module.exiftool_warning() is None
