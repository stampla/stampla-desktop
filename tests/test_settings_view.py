"""Tests for the Settings view: the config file stays the source of truth."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.settings import SettingsPage
from tests.support import page_of, write_config


def settings_page(window: MainWindow) -> SettingsPage:
    page = page_of(window, SettingsPage)
    assert isinstance(page, SettingsPage)
    return page


def shown_settings_page(window: MainWindow) -> SettingsPage:
    """The Settings page, made actually visible so isVisible() is meaningful."""
    page = settings_page(window)
    window.show()
    window.go(window.stack.indexOf(page))
    return page


def test_form_loads_values_from_the_file(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    window = MainWindow(load_archive(write_config(tmp_path)))
    page = settings_page(window)
    assert Path(page.root_edit.text()) == Path(str(tmp_path))
    assert len(page.tree_rows) == 1
    assert page.tree_rows[0].path.text() == "Photos"
    assert not page.twins_check.isChecked()


def test_save_preserves_hand_written_comments(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    config = root / "config.toml"
    config.write_text(
        "# my precious comment\n"
        f"root = {str(root)!r}\n"
        "\n"
        "[[trees]]\n"
        'path = "Photos"\n'
        'media = "photo"\n'
        "\n"
        "[extensions]\n"
        'raw = ["jpg"]\n'
        "mutable = []\n"
    )

    window = MainWindow(load_archive(config))
    page = settings_page(window)
    page.timezone_edit.setText("Europe/Warsaw")
    page.save()

    text = config.read_text()
    assert "# my precious comment" in text
    assert 'timezone = "Europe/Warsaw"' in text


def test_invalid_configuration_is_never_written(
    qapp: QtWidgets.QApplication, tmp_path: Path
) -> None:
    config = write_config(tmp_path)
    before = config.read_text()

    window = MainWindow(load_archive(config))
    page = shown_settings_page(window)
    for row in list(page.tree_rows):
        page.remove_tree_row(row)
    page.save()

    assert config.read_text() == before
    assert page.error_label.isVisible()
    text = page.error_label.text().lower()
    assert "not saved" in text or "invalid" in text


def test_unknown_timezone_is_rejected(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    config = write_config(tmp_path)
    before = config.read_text()

    window = MainWindow(load_archive(config))
    page = shown_settings_page(window)
    page.timezone_edit.setText("Nowhere/Nonsense")
    page.save()

    assert config.read_text() == before
    assert page.error_label.isVisible()


def test_save_reloads_the_archive_everywhere(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    window = MainWindow(load_archive(write_config(tmp_path)))
    page = settings_page(window)
    page.tree_rows[0].layout_edit.setText("{yyyy}/{mm}")
    page.save()

    assert window.archive.config.trees[0].layout == "{yyyy}/{mm}"


class TestPatternEditor:
    def test_form_loads_the_pattern(self, qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        page = settings_page(window)
        assert page.pattern_name_edit.text() == "md5-8"
        assert page.pattern_format_edit.text() == "%Y%m%d_%H%M%S"
        assert page.pattern_digest_combo.currentText() == "md5"
        assert page.pattern_length_spin.value() == 8
        assert "20260610_161045_" in page.pattern_preview.text()

    def test_preview_surfaces_library_validation(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        page = settings_page(window)
        page.pattern_format_edit.setText("%d%m%Y_%H%M%S")  # day first: unsortable
        assert "sorting" in page.pattern_preview.text()
        page.pattern_format_edit.setText("%Y-%m-%d %H:%M:%S")  # colons: unsafe
        assert "not safe in filenames" in page.pattern_preview.text()

    def test_pattern_change_keeps_the_old_scheme_recognized(
        self,
        qapp: QtWidgets.QApplication,
        tmp_path: Path,
        monkeypatch: object,
    ) -> None:
        import pytest

        assert isinstance(monkeypatch, pytest.MonkeyPatch)
        monkeypatch.setattr(
            QtWidgets.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes),
        )
        config = write_config(tmp_path)
        window = MainWindow(load_archive(config))
        page = settings_page(window)
        page.pattern_name_edit.setText("sha256-22")
        page.pattern_digest_combo.setCurrentText("sha256")
        page.pattern_length_spin.setValue(22)
        page.save()

        assert not page.error_label.isVisible()
        saved = window.archive.config
        assert saved.pattern.name == "sha256-22"
        assert saved.pattern.digest_length == 22
        assert [p.name for p in saved.additional_patterns] == ["md5-8"]

    def test_changed_pattern_requires_a_new_name(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        config = write_config(tmp_path)
        before = config.read_text()
        window = MainWindow(load_archive(config))
        page = shown_settings_page(window)
        page.pattern_length_spin.setValue(12)  # changed, but still named md5-8
        page.save()

        assert config.read_text() == before
        assert page.error_label.isVisible()
        assert "new name" in page.error_label.text()

    def test_dam_rejects_long_prefixes_on_save(
        self,
        qapp: QtWidgets.QApplication,
        tmp_path: Path,
        monkeypatch: object,
    ) -> None:
        import pytest

        assert isinstance(monkeypatch, pytest.MonkeyPatch)
        monkeypatch.setattr(
            QtWidgets.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes),
        )
        config = write_config(tmp_path)
        before = config.read_text()
        window = MainWindow(load_archive(config))
        page = shown_settings_page(window)
        page.dam_trees_edit.setText("Photos")
        page.pattern_name_edit.setText("sha256-22")
        page.pattern_digest_combo.setCurrentText("sha256")
        page.pattern_length_spin.setValue(22)
        page.save()

        assert config.read_text() == before
        assert page.error_label.isVisible()
        assert "TransmissionReference" in page.error_label.text()
