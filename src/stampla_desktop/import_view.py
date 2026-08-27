"""The Import view: the import command, rendered.

Import copies a memory card (or any folder) into the archive, named on
arrival. The view is built around the command's central promise — the
safe-to-format verdict — and never says more than the library does:
the banner is green only when an applied, whole-source run reports
``safe_to_format``, exactly the CLI's exit-0 rule. Apply re-plans and
copies in one operation, like the CLI, so what is applied is always
current, never a stale preview.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtWidgets
from stampla.importer import ImportPlan, ImportVerdict, apply_import, build_plan, verdict_of
from stampla.progress import Monitor
from stampla.report import Bucket, Report

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

BLURB = "Copy a memory card into the archive, named on arrival — ends in a safe-to-format verdict."

#: keep the page responsive on huge cards; counts always stay exact
MAX_GROUP_ROWS = 300


class ImportPage(Page):
    ready_status = "Choose a card or folder, then Preview."

    def __init__(self, window: MainWindow) -> None:
        super().__init__("Import", window)
        self.subtitle.setText(
            "Files on the card are never modified or removed — import copies, and"
            " every copy is re-hashed at its destination. The card stays a backup"
            " until the verdict clears it for formatting."
        )
        self.busy = False
        self._applying = False
        self.source: Path | None = None

        self.source_label = QtWidgets.QLabel("No source selected")
        self.source_label.setObjectName("sub")
        self.browse_button = QtWidgets.QPushButton("Choose card or folder…")
        self.browse_button.clicked.connect(self.browse)
        self.preview_button = QtWidgets.QPushButton("Preview")
        self.preview_button.setEnabled(False)
        self.apply_button = QtWidgets.QPushButton("Import")
        self.apply_button.setObjectName("primary")
        self.apply_button.setEnabled(False)
        self.preview_button.clicked.connect(lambda: self.start(apply=False))
        self.apply_button.clicked.connect(self.confirm_apply)
        self.shoot_edit = QtWidgets.QLineEdit()
        self.shoot_edit.setPlaceholderText("shoot / job name")
        self.shoot_edit.setToolTip(
            "Fills the {shoot} folder token for trees that file by shoot;"
            " whitespace becomes underscores."
        )
        self.shoot_edit.setMaximumWidth(180)
        self.shoot_edit.setVisible(
            any("{shoot}" in tree.layout for tree in self.archive.config.trees)
        )
        self.shoot_edit.textChanged.connect(lambda _: self.cli_panel.refresh())
        self.toolbar.addWidget(self.browse_button)
        self.toolbar.addWidget(self.preview_button)
        self.toolbar.addWidget(self.apply_button)
        self.toolbar.addWidget(self.shoot_edit)
        self.toolbar.addWidget(self.source_label, 1)
        self.add_work_controls()
        self.add_cli(self.cli_commands)
        self.show_empty(
            "⇥",
            "No source selected",
            "Choose a memory card or folder — Preview shows what would be imported"
            " without copying anything.",
        )

    def cli_commands(self) -> list[tuple[str, str]]:
        source = self.source if self.source is not None else Path("/Volumes/CARD")
        base = ["import", source, "--config", self.archive.config_path]
        if self.shoot_edit.text().strip():
            base += ["--shoot", self.shoot_edit.text().strip()]
        return [
            ("Preview", cli(*base)),
            ("Import", cli(*base, "--apply")),
        ]

    def browse(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose card or folder")
        if chosen:
            self.set_source(Path(chosen))

    def set_source(self, source: Path) -> None:
        """Select what to import; Organize hands folders over through this."""
        if self.busy:
            # swapping the source mid-run would render the finished
            # result — the verdict included — under the wrong name
            self.status("An operation is running — the source stays unchanged.")
            return
        self.source = source
        self.source_label.setText(str(source))
        self.preview_button.setEnabled(True)
        self.apply_button.setEnabled(False)
        self.show_empty(
            "⇥",
            source.name,
            "Ready — Preview shows what would be imported without copying anything.",
        )
        self.cli_panel.refresh()

    def confirm_apply(self) -> None:
        if self.source is None:
            return
        if confirm(
            self,
            "Import",
            f"Copy new files from {self.source.name} into the archive?",
            "The card is never written to. Files are re-planned at this moment,"
            " copied, then re-hashed at their destination; the run is journaled"
            " and revertable from History.",
            command=cli("import", self.source, "--config", self.archive.config_path, "--apply"),
        ):
            self.start(apply=True)

    def start(self, apply: bool) -> None:
        if self.source is None:
            return
        if not self.begin_work("Import" if apply else "Import preview"):
            return
        self._applying = apply
        self.browse_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.work_started()
        self.status("Importing…" if apply else "Planning the import…")
        archive = self.archive
        source = self.source
        shoot = self.shoot_edit.text().strip() or None

        def run(monitor: Monitor) -> tuple[ImportPlan, Report]:
            plan = build_plan(archive.config, archive.root, source, monitor=monitor, shoot=shoot)
            report = apply_import(plan, archive.root, monitor=monitor) if apply else plan.report
            return plan, report

        run_monitored(
            self,
            run,
            lambda result: self._finished(result, applied=apply),
            self._failed,
            on_progress=self.show_progress,
            on_stopped=self._stopped,
            cancel=self.cancel,
        )

    def _finished(self, result: object, applied: bool) -> None:
        assert isinstance(result, tuple)
        plan, report = result
        assert isinstance(plan, ImportPlan)
        assert isinstance(report, Report)
        self._reset()
        self.apply_button.setEnabled(bool(plan.moves) and not applied)
        verdict = verdict_of(report, applied=applied)
        if applied:
            self.status(
                "Import finished."
                if not report.has_problems
                else "Import finished with problems — review below."
            )
            self.window_.refresh_history()
        else:
            self.status("Plan ready — nothing has been copied.")
        self.render_result(plan, report, verdict, applied)

    def _failed(self, message: str) -> None:
        self._reset()
        if self._applying:
            self.show_failure("Import", message)
        else:
            self.status(message)

    def _stopped(self) -> None:
        self._reset()
        if self._applying:
            self.status(
                "Stopped mid-import — copied groups are journaled; finish or revert"
                " them from History. The card was not modified."
            )
            self.window_.refresh_history()
        else:
            self.status("Stopped — planning changes nothing.")

    def _reset(self) -> None:
        self.end_work()
        self.browse_button.setEnabled(True)
        self.preview_button.setEnabled(self.source is not None)
        self.work_finished()

    def render_result(
        self,
        plan: ImportPlan,
        report: Report,
        verdict: ImportVerdict | None,
        applied: bool,
    ) -> None:
        self.clear_body()
        if verdict is not None:
            assert self.source is not None
            self.add_card(_verdict_banner(verdict, self.source))

        counted: dict[Bucket, int] = {}
        for finding in report.findings:
            counted[finding.bucket] = counted.get(finding.bucket, 0) + 1

        moved = sum(len(move.renames) for move in plan.moves)
        already = counted.get(Bucket.ALREADY_IMPORTED, 0)
        ignored = counted.get(Bucket.IGNORED, 0)
        failed = counted.get(Bucket.APPLY_FAILED, 0)
        if applied:
            # report.ok is the library's count of groups copied AND verified;
            # never derive success from the plan when some groups failed
            verb = f"<b>{report.ok:,}</b> group(s) copied and verified"
            if failed:
                verb += (
                    f' · <span style="color:{theme.PALETTE["crit"]}"><b>{failed:,}'
                    "</b> group(s) FAILED</span>"
                )
        else:
            verb = (
                f"<b>{moved:,}</b> file(s) in <b>{len(plan.moves):,}</b> group(s) would be copied"
            )
        summary = f"{verb} · {already:,} already in the archive · {ignored:,} ignored by policy"
        # the banner already carries the counts for an applied run; keep the
        # standalone summary line only for dry runs, which have no banner
        if verdict is None:
            self.add_card(rich_label(summary))

        if ignored and not report.scanned:
            # every file on the card was excluded before planning even began;
            # without this the preview reads as "the card is empty"
            frame, layout = card()
            frame.setProperty("severity", "info")
            patterns = ", ".join(self.archive.config.import_ignore)
            layout.addWidget(
                rich_label(
                    f'<span style="color:{theme.PALETTE["info"]}"><b>Every file here is'
                    " excluded by your import ignore patterns</b></span>"
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                    f"All {ignored:,} file(s) match"
                    f' <span style="{MONO}">{html.escape(patterns)}</span> or sit on hidden'
                    " paths. Nothing was skipped silently — adjust the patterns in Settings"
                    " if these files should be considered.</span>"
                )
            )
            self.add_card(frame)

        problems = [f for f in report.findings if f.bucket.severity.value in ("alarm", "attention")]
        if problems:
            frame, layout = card()
            frame.setProperty("severity", "crit")
            layout.addWidget(
                rich_label(
                    f'<span style="color:{theme.PALETTE["crit"]}"><b>{len(problems)}'
                    f" problem(s) block the verdict</b></span>"
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">Anything'
                    " listed here exists only on the card or conflicts with the"
                    " archive — resolve before formatting.</span>"
                )
            )
            for finding in problems[:MAX_GROUP_ROWS]:
                color = theme.PALETTE[buckets.color_of(finding.bucket)]
                detail = (
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                    f"{html.escape(finding.detail)}</span>"
                    if finding.detail
                    else ""
                )
                layout.addWidget(
                    rich_label(
                        f'<span style="color:{color}">{buckets.title_of(finding.bucket)}</span>'
                        f'&nbsp;&nbsp;<span style="{MONO}">{html.escape(str(finding.path))}'
                        f"</span>{detail}"
                    )
                )
            if len(problems) > MAX_GROUP_ROWS:
                layout.addWidget(rich_label(f"…and {len(problems) - MAX_GROUP_ROWS:,} more"))
            self.add_card(frame)

        if plan.moves:
            frame, layout = card()
            muted, faint = theme.PALETTE["muted"], theme.PALETTE["faint"]
            root = self.archive.root
            shown = 0
            for move in plan.moves[:MAX_GROUP_ROWS]:
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
                shown += 1
            if len(plan.moves) > shown:
                layout.addWidget(
                    rich_label(
                        f"…and {len(plan.moves) - shown:,} more group(s) — counts above are exact"
                    )
                )
            self.add_card(frame)


def _verdict_banner(verdict: ImportVerdict, source: Path) -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame()
    frame.setObjectName("banner")
    frame.setProperty("verdict", "safe" if verdict.safe_to_format else "unsafe")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    if verdict.safe_to_format:
        color = theme.PALETTE["ok"]
        title = "Card fully accounted for — safe to format"
        body = (
            "Every file was copied and verified against its on-card digest, already"
            " sat in the archive byte-identical, or is on your ignore list. The card"
            " itself was never written to."
        )
    else:
        color = theme.PALETTE["crit"]
        title = "NOT safe to format"
        body = (
            "Some files are not accounted for — they exist only on the card, could"
            " not be dated, or conflict with the archive. Resolve the problems below"
            " and import again; re-running import is the pre-format check."
        )
    layout.addWidget(
        rich_label(f'<span style="color:{color}; font-size: 15px"><b>{title}</b></span>')
    )
    body_label = QtWidgets.QLabel(body)
    body_label.setObjectName("sub")
    body_label.setWordWrap(True)
    layout.addWidget(body_label)
    layout.addWidget(
        rich_label(
            f'<span style="color:{theme.PALETTE["faint"]}">{html.escape(str(source))}'
            f" · {verdict.imported} group(s) imported and verified"
            f" · {verdict.already_imported} already in the archive"
            f" · {verdict.ignored} file(s) ignored</span>"
        )
    )
    return frame
