"""The Relocate view: the relocate command, rendered.

A tree's layout maps each capture time to a directory, and the capture
time is in the name — so a file's correct shelf is derivable, and any
group sitting somewhere else is misplaced. This view plans those moves
(whole groups at a time) and applies them through the same validated,
journaled engine as the CLI.

Two trees are never moved for you: a DAM-managed tree's files are moved
inside the DAM instead (a folder checklist rendered as its own card),
and shoot-organized trees can't be derived back from names. Both are
reported, never touched.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from PySide6 import QtWidgets
from stampla.journal import GroupMove
from stampla.progress import Monitor
from stampla.relocate import RelocateOptions, run_relocate
from stampla.report import Bucket, Finding, Report

from stampla_desktop import buckets, theme
from stampla_desktop.base import (
    MONO,
    Page,
    card,
    cli,
    confirm,
    relative,
    rich_label,
)
from stampla_desktop.worker import run_monitored

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

BLURB = "Move files to the folder their name says they belong in — report-only until Apply."

MAX_ROWS = 200


class RelocatePage(Page):
    ready_status = "Plan to see what would move."

    def __init__(self, window: MainWindow) -> None:
        super().__init__("Relocate", window)
        self.subtitle.setText(
            "Report-only until Apply: files whose name says they belong in another"
            " folder are moved there, whole groups at a time."
        )
        self._applying = False
        self.moves: tuple[GroupMove, ...] = ()

        self.plan_button = QtWidgets.QPushButton("Plan")
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setObjectName("primary")
        self.apply_button.setEnabled(False)
        self.plan_button.clicked.connect(lambda: self.start(apply=False))
        self.apply_button.clicked.connect(self.confirm_apply)
        self.toolbar.addWidget(self.plan_button)
        self.toolbar.addWidget(self.apply_button)
        self.toolbar.addStretch()
        self.add_work_controls()
        self.add_cli(self.cli_commands)
        self.show_empty(
            "⇄",
            "No plan yet",
            "Plan finds files whose name says they belong in another folder.",
        )

    def cli_commands(self) -> list[tuple[str, str]]:
        base = ["relocate", "--config", self.archive.config_path]
        return [
            ("Plan", cli(*base)),
            ("Apply", cli(*base, "--apply")),
        ]

    def start(self, apply: bool) -> None:
        if not self.begin_work("Relocate apply" if apply else "Relocate plan"):
            return
        self._applying = apply
        self.plan_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.work_started()
        self.status("Moving groups…" if apply else "Planning moves…")
        options = RelocateOptions(apply=apply) if apply else None
        archive = self.archive

        def run(monitor: Monitor) -> tuple[Report, tuple[GroupMove, ...]]:
            return run_relocate(archive.config, archive.root, (), options, monitor)

        run_monitored(
            self,
            run,
            lambda result: self._finished(result, applied=apply),
            self._failed,
            on_progress=self.show_progress,
            on_stopped=self._stopped,
            cancel=self.cancel,
        )

    def confirm_apply(self) -> None:
        total = sum(len(move.renames) for move in self.moves)
        if confirm(
            self,
            "Apply moves",
            f"Move {total} file(s) in {len(self.moves)} group(s)?",
            "The plan is journaled first and can be undone from History.",
            command=cli("relocate", "--config", self.archive.config_path, "--apply"),
        ):
            self.start(apply=True)

    def _finished(self, result: object, applied: bool) -> None:
        assert isinstance(result, tuple)
        report, moves = result
        assert isinstance(report, Report)
        self.end_work()
        self.plan_button.setEnabled(True)
        self.work_finished()
        self.moves = () if applied else moves
        self.apply_button.setEnabled(bool(self.moves))
        if applied:
            relocated = sum(1 for f in report.findings if f.bucket is Bucket.RELOCATED)
            failed = sum(1 for f in report.findings if f.bucket is Bucket.APPLY_FAILED)
            self.status(
                f"Moved {relocated} group(s)"
                + (f", {failed} failed" if failed else "")
                + " — revertable from History."
            )
            self.window_.refresh_history()
            self.start(apply=False)
            return
        misplaced = [f for f in report.findings if f.bucket is Bucket.MISPLACED]
        if not misplaced:
            self.show_empty(
                "✓",
                "Nothing to move",
                "Everything is where its name says it belongs.",
            )
            self.status("Plan ready — everything is in its place.")
            return
        self.status("Plan ready — nothing has been moved.")
        self.render_plan(report)

    def _failed(self, message: str) -> None:
        applying = self._applying
        self.end_work()
        self.plan_button.setEnabled(True)
        self.apply_button.setEnabled(bool(self.moves))
        self.work_finished()
        if applying:
            self.show_failure("Relocate", message)
        else:
            self.status(message)

    def _stopped(self) -> None:
        self.end_work()
        self.plan_button.setEnabled(True)
        self.work_finished()
        if self._applying:
            self.status(
                "Stopped mid-apply — completed groups are journaled; finish or"
                " revert them from History."
            )
            self.window_.refresh_history()
        else:
            self.status("Stopped — a plan changes nothing.")

    def render_plan(self, report: Report) -> None:
        self.clear_body()
        pending = [
            f for f in report.findings if f.bucket in (Bucket.RELOCATE_PENDING, Bucket.RELOCATED)
        ]
        misplaced = [f for f in report.findings if f.bucket is Bucket.MISPLACED]
        self.add_card(
            rich_label(
                f"<b>{len(pending):,} group(s) to move</b>"
                f" · {report.scanned:,} file(s) considered"
                f" · {report.ok:,} ok"
            )
        )

        if pending:
            frame, layout = card()
            muted, faint = theme.PALETTE["muted"], theme.PALETTE["faint"]
            amber = theme.PALETTE["amber"]
            root = self.archive.root
            for finding in pending[:MAX_ROWS]:
                data = finding.data or {}
                target_dir = str(data.get("target_dir", ""))
                old_dir = relative(finding.path.parent, root)
                new_dir = relative(root / target_dir, root) if target_dir else ""
                layout.addWidget(
                    rich_label(
                        f'<span style="{MONO}">{html.escape(finding.path.name)}'
                        f'&nbsp;&nbsp;<span style="color:{muted}">{html.escape(old_dir)}</span>'
                        f'&nbsp;<span style="color:{faint}">→</span>&nbsp;'
                        f'<span style="color:{amber}">{html.escape(new_dir)}</span></span>'
                    )
                )
            if len(pending) > MAX_ROWS:
                more = QtWidgets.QLabel(f"…and {len(pending) - MAX_ROWS:,} more group(s)")
                more.setObjectName("faint")
                layout.addWidget(more)
            self.add_card(frame)

        self._render_misplaced(misplaced)
        self._render_hints(report)

    def _render_misplaced(self, misplaced: list[Finding]) -> None:
        if not misplaced:
            return
        color = theme.PALETTE[buckets.color_of(Bucket.MISPLACED)]
        frame, layout = card()
        frame.setProperty("severity", buckets.color_of(Bucket.MISPLACED))
        layout.addWidget(
            rich_label(
                f'<span style="color:{color}"><b>{len(misplaced):,} · '
                f"{buckets.title_of(Bucket.MISPLACED)}</b></span>"
                f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                f"{buckets.explain_of(Bucket.MISPLACED)}</span>"
            )
        )
        root = self.archive.root
        for finding in misplaced[:MAX_ROWS]:
            detail = (
                f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                f"{html.escape(finding.detail)}</span>"
                if finding.detail
                else ""
            )
            layout.addWidget(
                rich_label(
                    f'<span style="{MONO}">'
                    f"{html.escape(relative(finding.path, root))}</span>{detail}"
                )
            )
        if len(misplaced) > MAX_ROWS:
            more = QtWidgets.QLabel(f"…and {len(misplaced) - MAX_ROWS:,} more")
            more.setObjectName("faint")
            layout.addWidget(more)
        self.add_card(frame)

    def _render_hints(self, report: Report) -> None:
        """DAM folder moves get their own Lightroom card; other hints are info."""
        dam_hints = [hint for hint in report.hints if "DAM-managed" in hint]
        other_hints = [hint for hint in report.hints if "DAM-managed" not in hint]
        if dam_hints:
            frame, layout = card()
            frame.setProperty("severity", "info")
            layout.addWidget(
                rich_label(
                    f'<span style="color:{theme.PALETTE["info"]}">'
                    "<b>Do this inside Lightroom</b></span>"
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                    "These folders belong to your DAM — moving them in the Finder"
                    " would break its catalog. Move them in the Folders panel"
                    " instead.</span>"
                )
            )
            for hint in dam_hints:
                layout.addWidget(rich_label(html.escape(hint)))
            self.add_card(frame)
        if other_hints:
            frame, layout = card()
            frame.setProperty("severity", "info")
            for hint in other_hints:
                layout.addWidget(
                    rich_label(
                        f'<span style="color:{theme.PALETTE["muted"]}">{html.escape(hint)}</span>'
                    )
                )
            self.add_card(frame)
