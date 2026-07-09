"""The Rename view: the rename command, rendered — with the DAM hand-off.

Names are deterministic, so there is nothing to configure — only a
plan to review. The table shows whole families (sidecars nested under
their master) with the changed span of each new name highlighted, and
Apply runs the same validated, journaled engine as the CLI.

When the archive configures a DAM ([dam] in the config), the same
preview also dry-runs inject: masters the DAM must rename itself are
listed with their tokens and the checklist that finishes the job in
the DAM — the split the CLI expresses as two commands is one review
here, but each half applies through its own confirmed action.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from stampla.dam import InjectOptions, run_inject
from stampla.journal import FamilyMove
from stampla.progress import Monitor
from stampla.renamer import RenameOptions, run_rename
from stampla.report import Bucket, Report
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
        self.pending_tokens = 0

        self.preview_button = QtWidgets.QPushButton("Preview")
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setObjectName("primary")
        self.apply_button.setEnabled(False)
        self.tokens_button = QtWidgets.QPushButton("Write DAM tokens…")
        self.tokens_button.setEnabled(False)
        self.tokens_button.setVisible(self.dam_configured)
        self.preview_button.clicked.connect(lambda: self.start(apply=False))
        self.apply_button.clicked.connect(self.confirm_apply)
        self.tokens_button.clicked.connect(self.confirm_tokens)
        self.toolbar.addWidget(self.preview_button)
        self.toolbar.addWidget(self.apply_button)
        self.toolbar.addWidget(self.tokens_button)
        self.toolbar.addStretch()
        self.add_work_controls()
        self.add_cli(self.cli_commands)

    @property
    def dam_configured(self) -> bool:
        dam = self.archive.config.dam
        return dam is not None and bool(dam.trees)

    def cli_commands(self) -> list[tuple[str, str]]:
        base = ["rename", "--config", self.archive.config_path]
        commands = [
            ("Preview", cli(*base)),
            ("Apply", cli(*base, "--apply")),
        ]
        if self.dam_configured:
            commands.append(
                ("Write DAM tokens", cli("inject", "--config", self.archive.config_path, "--apply"))
            )
        return commands

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
        with_dam = self.dam_configured

        def run(monitor: Monitor) -> tuple[Report, tuple[FamilyMove, ...], Report | None]:
            report, moves = run_rename(archive.config, archive.root, (), options, monitor)
            inject_report: Report | None = None
            if with_dam and not apply:
                inject_report = run_inject(
                    archive.config, archive.root, (), InjectOptions(apply=False), monitor
                )
            return report, moves, inject_report

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
            "Apply renames",
            f"Rename {total} file(s) in {len(self.moves)} family(ies)?",
            "The plan is journaled first and can be undone from History.",
            command=cli("rename", "--config", self.archive.config_path, "--apply"),
        ):
            self.start(apply=True)

    def _finished(self, result: object, applied: bool) -> None:
        assert isinstance(result, tuple)
        report, moves, inject_report = result
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
        if inject_report is not None:
            self.render_tokens(inject_report)

    def confirm_tokens(self) -> None:
        if confirm(
            self,
            "Write DAM tokens",
            f"Write {self.pending_tokens} rename token(s) into metadata?",
            "Each master's correct name is written into the field your DAM renames"
            " from. Files without a sidecar carry the token inside the file, which"
            " changes their content hash — expected for formats edited in place.",
            command=cli("inject", "--config", self.archive.config_path, "--apply"),
        ):
            self.start_tokens()

    def start_tokens(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.tokens_button.setEnabled(False)
        self.work_started()
        self.status("Writing tokens…")
        archive = self.archive
        run_monitored(
            self,
            lambda monitor: run_inject(
                archive.config, archive.root, (), InjectOptions(apply=True), monitor
            ),
            self._tokens_written,
            self._failed,
            on_progress=self.show_progress,
            on_stopped=self._stopped,
            cancel=self.cancel,
        )

    def _tokens_written(self, result: object) -> None:
        assert isinstance(result, Report)
        self.busy = False
        self.preview_button.setEnabled(True)
        self.work_finished()
        written = sum(1 for f in result.findings if f.bucket is Bucket.TOKEN_WRITTEN)
        failed = sum(1 for f in result.findings if f.bucket is Bucket.APPLY_FAILED)
        self.status(
            f"{written} token(s) written and read back"
            + (f", {failed} FAILED verification" if failed else "")
            + " — finish in the DAM (steps below)."
        )
        self.render_tokens(result)

    def render_tokens(self, report: Report) -> None:
        """The DAM half of the plan: pending or written tokens + the checklist."""
        pending = [f for f in report.findings if f.bucket is Bucket.TOKEN_PENDING]
        written = [f for f in report.findings if f.bucket is Bucket.TOKEN_WRITTEN]
        blocked = [
            f for f in report.findings if f.bucket in (Bucket.NEEDS_SIDECAR, Bucket.APPLY_FAILED)
        ]
        self.pending_tokens = len(pending)
        self.tokens_button.setEnabled(bool(pending))
        if not (pending or written or blocked):
            return

        frame, layout = card()
        muted = theme.PALETTE["muted"]
        amber = theme.PALETTE["amber"]
        if written:
            head = f"{len(written)} token(s) written — finish the rename in your DAM"
        else:
            head = f"{len(pending)} master(s) are renamed by your DAM, not directly"
        layout.addWidget(
            rich_label(
                f'<span style="color:{amber}"><b>{head}</b></span>'
                f'&nbsp;&nbsp;<span style="color:{muted}">Renaming them behind the'
                " DAM's back would break its catalog link.</span>"
            )
        )
        for finding in (written or pending)[:100]:
            data = finding.data or {}
            token = str(data.get("token", ""))
            layout.addWidget(
                rich_label(
                    f'<span style="{MONO}">{html.escape(finding.path.name)}'
                    f'&nbsp;<span style="color:{theme.PALETTE["faint"]}">→</span>&nbsp;'
                    f'<span style="color:{amber}">{html.escape(token)}</span></span>'
                )
            )
        for finding in blocked[:100]:
            layout.addWidget(
                rich_label(
                    f'<span style="color:{theme.PALETTE["warn"]}">'
                    f"{html.escape(finding.path.name)}</span>"
                    f'&nbsp;&nbsp;<span style="color:{muted}">{html.escape(finding.detail)}</span>'
                )
            )
        steps = (
            "1. Write the tokens (button above), or run inject from the terminal.",
            "2. In Lightroom Classic: Metadata → Read Metadata from Files on the affected folders.",
            "3. Library → Rename Photos with the {Job Identifier} filename token.",
        )
        for step in steps:
            step_label = QtWidgets.QLabel(step)
            step_label.setObjectName("sub")
            layout.addWidget(step_label)
        self.add_card(frame)

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
