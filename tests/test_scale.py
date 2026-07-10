"""Rendering must survive archives with hundreds of thousands of files.

Rows are capped; counts must stay exact — a truncated list that reads
as complete could hide the finding that mattered.
"""

from __future__ import annotations

import time
from pathlib import Path

from stampla.journal import GroupMove, Rename
from stampla.report import Bucket, Finding, Report
from PySide6 import QtWidgets

from stampla_desktop.app import MainWindow
from stampla_desktop.base import load_archive
from stampla_desktop.rename import RenamePage
from stampla_desktop.verify import VerifyPage
from tests.support import page_of, write_config


def labels_text(page: QtWidgets.QWidget) -> str:
    return "\n".join(label.text() for label in page.findChildren(QtWidgets.QLabel))


def big_report(findings_per_bucket: int) -> Report:
    report = Report(ok=180_000, scanned=200_000, groups=190_000)
    for bucket in (Bucket.DATE_MISMATCH, Bucket.UNNAMED, Bucket.EDIT_DRIFT, Bucket.CORRUPTION):
        for index in range(findings_per_bucket):
            report.add(Finding(bucket, Path(f"Photos/2026/f{index:06d}.jpg"), "detail"))
    return report


class TestVerifyAtScale:
    def test_huge_report_renders_capped_with_exact_counts(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        page = page_of(window, VerifyPage)
        assert isinstance(page, VerifyPage)
        report = big_report(5_000)

        started = time.monotonic()
        page.render_report(report)
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"render took {elapsed:.1f}s"

        text = labels_text(page)
        assert "180,000 ok" in text
        assert "20,000 findings" in text
        assert "5,000 ·" in text  # per-bucket counts are exact
        assert "…and 4,900 more" in text  # rendering is visibly truncated
        # never more than the cap of rows per bucket
        assert text.count("f000099.jpg") == 4  # row 100 present in each bucket
        assert "f000100.jpg" not in text  # row 101 is not

    def test_summary_never_hides_alarms_behind_truncation(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        page = page_of(window, VerifyPage)
        assert isinstance(page, VerifyPage)
        page.render_report(big_report(200))
        text = labels_text(page)
        # corruption (alarm) renders as its own group despite the volume
        assert "possible corruption" in text


class TestRenamePlanAtScale:
    def test_huge_plan_renders_capped_with_exact_counts(
        self, qapp: QtWidgets.QApplication, tmp_path: Path
    ) -> None:
        window = MainWindow(load_archive(write_config(tmp_path)))
        page = page_of(window, RenamePage)
        assert isinstance(page, RenamePage)
        moves = tuple(
            GroupMove(
                key=f"k{index}",
                renames=(
                    Rename(
                        old=tmp_path / f"a{index:06d}.jpg",
                        new=tmp_path / f"b{index:06d}.jpg",
                    ),
                ),
            )
            for index in range(10_000)
        )

        started = time.monotonic()
        page.render_plan(moves)
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"render took {elapsed:.1f}s"

        text = labels_text(page)
        assert "10,000 rename(s)" in text
        assert "…and 9,800 more groups" in text
