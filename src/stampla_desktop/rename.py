"""The Rename view: the rename command, rendered.

Names are deterministic, so there is nothing to configure — only a
plan to review. The table shows whole families (sidecars nested under
their master) with the changed span of each new name highlighted, and
Apply runs the same validated, journaled engine as the CLI.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from stampla.journal import FamilyMove
from stampla.renamer import RenameOptions, run_rename
from stampla.report import Report
from PySide6 import QtWidgets

from stampla_desktop import theme
from stampla_desktop.base import (
    MONO,
    Page,
    card,
    cli,
    confirm,
    diff_html,
    relative,
    rich_label,
)
from stampla_desktop.worker import run_monitored

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

BLURB = "Preview stale names as old → new, then apply — journaled and revertable from History."


class RenamePage(Page):
    def __init__(self, window: MainWindow) -> None:
        super().__init__("Rename", window)
        self.subtitle.setText(
            "Files whose derived name no longer matches. Renames are validated as a"
            " whole, journaled before the first change, and revertable from History."
        )
        self.busy = False
        self._applying = False
        self.moves: tuple[FamilyMove, ...] = ()

        self.preview_button = QtWidgets.QPushButton("Preview")
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setObjectName("primary")
        self.apply_button.setEnabled(False)
        self.preview_button.clicked.connect(lambda: self.start(apply=False))
        self.apply_button.clicked.connect(self.confirm_apply)
        self.toolbar.addWidget(self.preview_button)
        self.toolbar.addWidget(self.apply_button)
        self.toolbar.addStretch()
        self.add_work_controls()
        self.add_cli(self.cli_commands)

    def cli_commands(self) -> list[tuple[str, str]]:
        base = ["rename", "--config", self.archive.config_path]
        return [
            ("Preview", cli(*base)),
            ("Apply", cli(*base, "--apply")),
        ]

    def start(self, apply: bool) -> None:
        if self.busy:
            return
        self.busy = True
        self._applying = apply
        self.preview_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.work_started()
        self.status("Applying renames…" if apply else "Planning renames…")
        options = RenameOptions(apply=apply, workers=None, full=False, use_manifest=True)
        archive = self.archive
        run_monitored(
            self,
            lambda monitor: run_rename(archive.config, archive.root, (), options, monitor),
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
            "Apply renames",
            f"Rename {total} file(s) in {len(self.moves)} family(ies)?",
            "The plan is journaled first and can be undone from History.",
            command=cli("rename", "--config", self.archive.config_path, "--apply"),
        ):
            self.start(apply=True)

    def _finished(self, result: object, applied: bool) -> None:
        assert isinstance(result, tuple)
        report, moves = result
        assert isinstance(report, Report)
        self.busy = False
        self.preview_button.setEnabled(True)
        self.work_finished()
        self.moves = () if applied else moves
        self.apply_button.setEnabled(bool(self.moves))
        if applied:
            failed = sum(1 for f in report.findings if f.bucket.value == "apply-failed")
            self.status(
                f"Applied {len(moves)} family(ies)"
                + (f", {failed} failed" if failed else "")
                + " — revertable from History."
            )
            self.window_.refresh_history()
            self.start(apply=False)
            return
        self.status("Plan ready — nothing has been changed.")
        self.render_plan(moves)

    def _failed(self, message: str) -> None:
        self.busy = False
        self.preview_button.setEnabled(True)
        self.apply_button.setEnabled(bool(self.moves))
        self.work_finished()
        self.status(message)

    def _stopped(self) -> None:
        self.busy = False
        self.preview_button.setEnabled(True)
        self.work_finished()
        if self._applying:
            self.status(
                "Stopped mid-apply — completed families are journaled; finish or"
                " revert them from History."
            )
            self.window_.refresh_history()
        else:
            self.status("Stopped — a preview changes nothing.")

    def render_plan(self, moves: tuple[FamilyMove, ...]) -> None:
        self.clear_body()
        total = sum(len(move.renames) for move in moves)
        if not moves:
            self.add_card(rich_label("Every name matches — nothing to rename."))
            return
        self.add_card(rich_label(f"<b>{total} rename(s)</b> planned in {len(moves)} family(ies):"))
        frame, layout = card()
        muted, faint = theme.PALETTE["muted"], theme.PALETTE["faint"]
        root = self.archive.root
        for move in moves[:200]:
            for index, rename in enumerate(move.renames):
                old_text = relative(rename.old, root) if index == 0 else f"└ {rename.old.name}"
                layout.addWidget(
                    rich_label(
                        f'<span style="{MONO}">'
                        f'<span style="color:{muted}">{html.escape(old_text)}</span>'
                        f'&nbsp;<span style="color:{faint}">→</span>&nbsp;'
                        f"{diff_html(rename.old.name, rename.new.name)}</span>"
                    )
                )
        if len(moves) > 200:
            more = QtWidgets.QLabel(f"…and {len(moves) - 200} more families")
            more.setObjectName("faint")
            layout.addWidget(more)
        self.add_card(frame)
