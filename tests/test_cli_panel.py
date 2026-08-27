"""Tests for the terminal-command transparency layer."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import cli, load_archive
from stampla_desktop.history import HistoryPage
from stampla_desktop.rename import RenamePage
from stampla_desktop.verify import VerifyPage
from tests.support import page_of, write_config


def test_cli_quotes_paths() -> None:
    # the platform renders the separators; the quoting is what's under test
    path = Path("/a dir/x.toml")
    assert cli("verify", "--config", path) == f"stampla verify --config '{path}'"


class TestPanels:
    def make_window(self, tmp_path: Path) -> MainWindow:
        return MainWindow(load_archive(write_config(tmp_path)))

    def test_commands_match_the_views_that_reveal_them(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = self.make_window(tmp_path)
        providers = {
            kind: page_of(window, kind).cli_commands()  # type: ignore[attr-defined]
            for kind in (VerifyPage, RenamePage)
        }
        verify_commands = dict(providers[VerifyPage])
        assert verify_commands["Check everything"].startswith("stampla verify --config")
        rename_commands = dict(providers[RenamePage])
        assert rename_commands["Apply"].endswith("--apply")

    def test_verify_options_appear_in_the_command_live(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = self.make_window(tmp_path)
        page = page_of(window, VerifyPage)
        assert isinstance(page, VerifyPage)
        page.recheck.setChecked(True)
        assert all("--full" in command for _, command in page.cli_commands())

    def test_history_panel_teaches_the_history_command(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = self.make_window(tmp_path)
        for index in range(window.stack.count()):
            page = window.stack.widget(index)
            if isinstance(page, HistoryPage):
                commands = [command for _, command in page.cli_panel.provider()]
                assert any(command.startswith("stampla history") for command in commands)
                return
        raise AssertionError("History view missing")

    def test_toggle_shows_panels_everywhere_and_persists(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = self.make_window(tmp_path)
        window.set_cli(True)
        assert all(page.cli_panel.isVisible() or not page.isVisible() for page in window._cli_pages)
        assert all(page.cli_toggle.isChecked() for page in window._cli_pages)
        window.set_cli(False)
        assert not any(page.cli_toggle.isChecked() for page in window._cli_pages)
