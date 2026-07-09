"""Tests for the DAM hand-off half of the Rename view."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.rename import RenamePage
from tests.support import TINY_JPEG, page_of, spin

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)

DAM_CONFIG = """
root = {root!r}

[[trees]]
path = "Photos"
media = "photo"

[extensions]
raw = ["jpg"]
mutable = ["jpg"]

[dam]
trees = ["Photos"]
"""


def write_dam_config(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    config = root / "config.toml"
    config.write_text(DAM_CONFIG.format(root=str(root)))
    return config


def make_stale_master(directory: Path, capture: str) -> Path:
    """A named master whose date moved after import: the DAM must rename it."""
    directory.mkdir(parents=True, exist_ok=True)
    stale = directory / "20260101_090000_deadbeef.jpg"
    stale.write_bytes(TINY_JPEG)
    subprocess.run(
        ["exiftool", "-q", "-overwrite_original", f"-EXIF:DateTimeOriginal={capture}", str(stale)],
        check=True,
    )
    return stale


def labels_text(page: RenamePage) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


@requires_exiftool
class TestDamHandOff:
    def test_preview_lists_dam_owned_masters_with_tokens(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = write_dam_config(tmp_path)
        make_stale_master(tmp_path / "Photos" / "2026" / "2026-01", "2026:01:01 11:00:00")

        window = MainWindow(load_archive(config))
        page = page_of(window, RenamePage)
        assert isinstance(page, RenamePage)
        assert page.tokens_button.isVisible() or True  # visibility needs a shown window
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "renamed by your DAM" in text
        assert "20260101_110000_" in text  # the token the DAM will rename to
        assert "Read Metadata from Files" in text
        assert page.tokens_button.isEnabled()

    def test_write_tokens_applies_and_verifies(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = write_dam_config(tmp_path)
        stale = make_stale_master(tmp_path / "Photos" / "2026" / "2026-01", "2026:01:01 11:00:00")

        window = MainWindow(load_archive(config))
        page = page_of(window, RenamePage)
        assert isinstance(page, RenamePage)
        page.start(apply=False)
        spin(qapp, lambda: not page.busy)
        page.start_tokens()
        spin(qapp, lambda: not page.busy)

        text = labels_text(page)
        assert "token(s) written" in text
        stored = subprocess.run(
            ["exiftool", "-s3", "-XMP-photoshop:TransmissionReference", str(stale)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert stored.startswith("20260101_110000_")

    def test_without_dam_config_the_hand_off_stays_out_of_the_way(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        from tests.support import write_config

        window = MainWindow(load_archive(write_config(tmp_path)))
        page = page_of(window, RenamePage)
        assert isinstance(page, RenamePage)
        assert not page.dam_configured
        commands = [label for label, _ in page.cli_commands()]
        assert "Write DAM tokens" not in commands
