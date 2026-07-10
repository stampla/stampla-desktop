"""The Organize view: the organize command, rendered.

Triage for the messy tree every archive drags along. Organize never
renames and has no apply — it runs the import planning over a folder
and reports what would happen, what is already archived, what could
only be dated from hearsay, and what remains unresolvable. Confirmed
folders hand off to the Import view.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

from stampla.importer import ImportPlan
from stampla.organize import run_organize
from stampla.report import Bucket, Report
from PySide6 import QtWidgets

from stampla_desktop import buckets, theme
from stampla_desktop.base import MONO, Page, card, cli, relative, rich_label
from stampla_desktop.worker import run_monitored

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

BLURB = "Triage a messy folder: proposals, duplicates, undatable files — nothing is ever renamed."

MAX_ROWS = 300


class OrganizePage(Page):
    ready_status = "Choose a folder to triage — nothing is ever renamed."

    def __init__(self, window: MainWindow) -> None:
        super().__init__("Organize", window)
        self.subtitle.setText(
            "Report only: what each group would be named and where it would live,"
            " what is already in the archive, and what needs your eyes first."
            " Import confirmed folders from the Import view."
        )
        self.busy = False
        self.source: Path | None = None

        self.source_label = QtWidgets.QLabel("No folder selected")
        self.source_label.setObjectName("sub")
        browse_button = QtWidgets.QPushButton("Choose folder…")
        browse_button.clicked.connect(self.browse)
        self.analyze_button = QtWidgets.QPushButton("Analyze")
        self.analyze_button.setObjectName("primary")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self.start)
        self.import_button = QtWidgets.QPushButton("Open in Import…")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.hand_off)
        self.toolbar.addWidget(browse_button)
        self.toolbar.addWidget(self.analyze_button)
        self.toolbar.addWidget(self.import_button)
        self.toolbar.addWidget(self.source_label, 1)
        self.add_work_controls()
        self.add_cli(self.cli_commands)
        self.show_empty(
            "☰",
            "No folder selected",
            "Pick a messy folder to see what it would become — organize never renames.",
        )

    def cli_commands(self) -> list[tuple[str, str]]:
        source = self.source if self.source is not None else Path("/path/to/messy-folder")
        return [
            ("Analyze", cli("organize", source, "--config", self.archive.config_path)),
        ]

    def browse(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose a folder to triage")
        if chosen:
            self.source = Path(chosen)
            self.source_label.setText(chosen)
            self.analyze_button.setEnabled(True)
            self.import_button.setEnabled(False)
            self.clear_body()
            self.cli_panel.refresh()

    def hand_off(self) -> None:
        """Confirmed batch → the Import view, source prefilled."""
        if self.source is None:
            return
        from stampla_desktop.import_view import ImportPage

        for index in range(self.window_.stack.count()):
            widget = self.window_.stack.widget(index)
            if isinstance(widget, ImportPage):
                widget.set_source(self.source)
                self.window_.go(index)
                return

    def start(self) -> None:
        if self.busy or self.source is None:
            return
        self.busy = True
        self.analyze_button.setEnabled(False)
        self.work_started()
        self.status("Analyzing the folder…")
        archive = self.archive
        source = self.source
        run_monitored(
            self,
            lambda monitor: run_organize(archive.config, archive.root, source, monitor=monitor),
            self._finished,
            self._failed,
            on_progress=self.show_progress,
            on_stopped=self._stopped,
            cancel=self.cancel,
        )

    def _finished(self, result: object) -> None:
        assert isinstance(result, tuple)
        report, plan = result
        assert isinstance(report, Report)
        assert isinstance(plan, ImportPlan)
        self._reset()
        self.import_button.setEnabled(bool(plan.moves))
        self.status("Analysis finished — nothing was touched.")
        self.render_result(report, plan)

    def _failed(self, message: str) -> None:
        self._reset()
        self.status(message)

    def _stopped(self) -> None:
        self._reset()
        self.status("Stopped — organize never changes anything anyway.")

    def _reset(self) -> None:
        self.busy = False
        self.analyze_button.setEnabled(self.source is not None)
        self.work_finished()

    def render_result(self, report: Report, plan: ImportPlan) -> None:
        self.clear_body()
        ignored = [f for f in report.findings if f.bucket is Bucket.IGNORED]
        summary = (
            f"<b>{len(plan.moves):,}</b> group(s) look importable out of"
            f" <b>{report.groups:,}</b> · {report.scanned:,} file(s) considered"
        )
        if ignored:
            summary += f" · {len(ignored):,} ignored by policy"
        self.add_card(rich_label(summary))

        if ignored and not report.scanned:
            # "0 of 0" with no explanation reads as an empty folder — say
            # out loud that the files exist and why none were considered.
            frame, layout = card()
            frame.setProperty("severity", "info")
            patterns = ", ".join(self.archive.config.import_ignore)
            layout.addWidget(
                rich_label(
                    f'<span style="color:{theme.PALETTE["info"]}"><b>Every file here is'
                    " excluded by your import ignore patterns</b></span>"
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                    f"All {len(ignored):,} file(s) match"
                    f' <span style="{MONO}">{html.escape(patterns)}</span> or sit on hidden'
                    " paths. Nothing was skipped silently — adjust the patterns in Settings"
                    " if these files should be considered.</span>"
                )
            )
            self.add_card(frame)

        flagged = [
            f
            for f in report.findings
            if f.bucket.severity.value in ("alarm", "attention")
            or f.bucket.value in ("mtime-dated", "name-dated")
        ]
        if flagged:
            frame, layout = card()
            frame.setProperty("severity", "warn")
            layout.addWidget(
                rich_label(
                    f'<span style="color:{theme.PALETTE["warn"]}"><b>{len(flagged)}'
                    " finding(s) need your eyes before importing</b></span>"
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">Dates from'
                    " modification time or filenames are proposals, not evidence.</span>"
                )
            )
            for finding in flagged[:MAX_ROWS]:
                color = theme.PALETTE[buckets.color_of(finding.bucket)]
                detail = (
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                    f"{html.escape(finding.detail)}</span>"
                    if finding.detail
                    else ""
                )
                layout.addWidget(
                    rich_label(
                        f'<span style="color:{color}">{buckets.TITLE[finding.bucket]}</span>'
                        f'&nbsp;&nbsp;<span style="{MONO}">{html.escape(finding.path.name)}'
                        f"</span>{detail}"
                    )
                )
            if len(flagged) > MAX_ROWS:
                layout.addWidget(rich_label(f"…and {len(flagged) - MAX_ROWS:,} more"))
            self.add_card(frame)

        if plan.moves:
            frame, layout = card()
            muted, faint = theme.PALETTE["muted"], theme.PALETTE["faint"]
            root = self.archive.root
            for move in plan.moves[:MAX_ROWS]:
                first = move.renames[0]
                others = len(move.renames) - 1
                extra = (
                    f' <span style="color:{faint}">+{others} more in the group</span>'
                    if others
                    else ""
                )
                layout.addWidget(
                    rich_label(
                        f'<span style="{MONO}">'
                        f'<span style="color:{muted}">{html.escape(first.old.name)}</span>'
                        f'&nbsp;<span style="color:{faint}">→</span>&nbsp;'
                        f'<span style="color:{theme.PALETTE["amber"]}">'
                        f"{html.escape(relative(first.new, root))}</span></span>{extra}"
                    )
                )
            if len(plan.moves) > MAX_ROWS:
                layout.addWidget(rich_label(f"…and {len(plan.moves) - MAX_ROWS:,} more group(s)"))
            self.add_card(frame)
