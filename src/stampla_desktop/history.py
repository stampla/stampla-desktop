"""The History view: the history command, rendered.

Journals are global; the library scopes them to the open archive. Each
run shows its originating command, local-time stamp and status — and
the status decides the actions: complete and partial runs can be
undone, an interrupted (partial) run can be resumed.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets
from stampla.apply import ApplyResult, apply_plan, undo_journal
from stampla.journal import Journal, journal_summaries

from stampla_desktop.base import Page, card, cli, confirm, rich_label, when
from stampla_desktop.worker import run_monitored

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

BLURB = "Every change ever applied, newest first — with Undo, and Resume for interrupted runs."

MAX_ROWS = 200

#: journal status → (palette key, what the state means here)
STATUS_STYLE = {
    "complete": ("ok", "applied"),
    "partial": ("warn", "interrupted — resume finishes it"),
    "undone": ("muted", "reverted"),
    "pending": ("info", "never started"),
}


class HistoryPage(Page):
    ready_status = "Every applied change, newest first."

    def __init__(self, window: MainWindow) -> None:
        super().__init__("History", window)
        self.subtitle.setText(
            "Every change Stampla has applied to this archive, newest first."
            " Undo re-verifies copied files before deleting anything."
        )
        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        self.toolbar.addWidget(refresh_button)
        self.toolbar.addStretch()
        self.add_work_controls()
        self.add_cli(self.cli_commands)
        self.refresh()

    def cli_commands(self) -> list[tuple[str, str]]:
        rows = [("List history", cli("history", "--root", self.archive.root))]
        # never teach bare --latest: it takes the newest journal across
        # EVERY archive on this machine, not this one's newest run
        summaries = journal_summaries(root=self.archive.root)
        if summaries:
            rows.append(("Undo this archive's newest run", cli("undo", summaries[-1].path)))
        return rows

    def refresh(self) -> None:
        if self.busy:
            return  # the finished handler refreshes; never yank rows mid-run
        self.clear_body()
        summaries = journal_summaries(root=self.archive.root)
        if not summaries:
            self.add_card(rich_label("No changes recorded for this archive yet."))
            return
        newest_first = list(reversed(summaries))
        if len(newest_first) > MAX_ROWS:
            self.add_card(
                rich_label(
                    f"Showing the {MAX_ROWS} most recent of {len(newest_first):,} runs —"
                    " older journals remain on disk and in the history command."
                )
            )
        for summary in newest_first[:MAX_ROWS]:
            _color_key, meaning = STATUS_STYLE.get(summary.status, ("muted", ""))
            frame, layout = card()
            row = QtWidgets.QHBoxLayout()
            column = QtWidgets.QVBoxLayout()
            origin = summary.command or summary.kind

            title_row = QtWidgets.QHBoxLayout()
            title_row.setSpacing(8)
            title_row.addWidget(
                rich_label(f"<b>{html.escape(origin)}</b> · {summary.groups} group(s)", wrap=False),
                0,
            )
            pill = QtWidgets.QLabel(summary.status)
            pill.setObjectName("pill")
            pill.setProperty("status", summary.status)
            title_row.addWidget(pill, 0)
            meaning_label = QtWidgets.QLabel(meaning)
            meaning_label.setObjectName("faint")
            title_row.addWidget(meaning_label, 0)
            title_row.addStretch(1)
            column.addLayout(title_row)

            name = QtWidgets.QLabel(f"{when(summary.created_at)} · {summary.path.name}")
            name.setObjectName("faint")
            column.addWidget(name)
            row.addLayout(column, 1)
            if summary.status == "partial":
                resume_button = QtWidgets.QPushButton("Resume")
                resume_button.setObjectName("primary")
                resume_button.clicked.connect(
                    lambda _=False, p=summary.path: self.confirm_resume(p)
                )
                row.addWidget(resume_button, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            if summary.status in ("complete", "partial"):
                undo_button = QtWidgets.QPushButton("Undo…")
                undo_button.setObjectName("danger")
                undo_button.clicked.connect(lambda _=False, p=summary.path: self.confirm_undo(p))
                row.addWidget(undo_button, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            layout.addLayout(row)
            self.add_card(frame)

    def confirm_undo(self, path: Path) -> None:
        if self.busy:
            self.status("An operation is already running.")
            return
        if not confirm(
            self,
            "Undo",
            f"Revert {path.name}?",
            "Files edited since are re-verified and refused, never deleted.",
            command=cli("undo", path),
        ):
            return
        if not self.begin_work("Undo"):
            return
        self.work_started()
        self.status("Undoing…")
        run_monitored(
            self,
            lambda monitor: undo_journal(Journal.load(path), monitor=monitor),
            self._undone,
            self._failed,
            on_progress=self.show_progress,
            on_stopped=self._stopped,
            cancel=self.cancel,
        )

    def confirm_resume(self, path: Path) -> None:
        if self.busy:
            self.status("An operation is already running.")
            return
        if not confirm(
            self,
            "Resume",
            f"Finish {path.name}?",
            "Families already done are skipped; the remaining ones are applied.",
            command=cli("resume", path),
        ):
            return
        if not self.begin_work("Resume"):
            return
        self.work_started()
        self.status("Resuming…")
        run_monitored(
            self,
            lambda monitor: apply_plan(Journal.load(path), monitor=monitor),
            self._resumed,
            self._failed,
            on_progress=self.show_progress,
            on_stopped=self._stopped,
            cancel=self.cancel,
        )

    def _failed(self, message: str) -> None:
        self.end_work()
        self.work_finished()
        self.show_failure("Undo / resume", message)
        self.refresh()

    def _stopped(self) -> None:
        self.end_work()
        self.work_finished()
        self.status("Stopped at a safe point — finish or revert from the list below.")
        self.refresh()

    def _undone(self, result: object) -> None:
        self.end_work()
        self.work_finished()
        assert isinstance(result, ApplyResult)
        self.status(
            f"Undo: {len(result.applied)} group(s) reverted,"
            f" {len(result.skipped)} not applied, {len(result.failed)} failed."
        )
        self.refresh()

    def _resumed(self, result: object) -> None:
        self.end_work()
        self.work_finished()
        assert isinstance(result, ApplyResult)
        self.status(
            f"Resume: {len(result.applied)} group(s) applied,"
            f" {len(result.skipped)} already done, {len(result.failed)} failed."
        )
        self.refresh()
