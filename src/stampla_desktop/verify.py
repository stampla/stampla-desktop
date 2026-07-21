"""The Verify view: the verify command, rendered.

Findings arrive in buckets the library has already classified; this
view orders them alarms-first, colors them by the library's severity,
and rebuilds detail lines from structured finding data where it
exists — the prose is never parsed.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from PySide6 import QtWidgets
from stampla.report import BUCKET_ORDER, Bucket, Finding, Report, Severity
from stampla.verify import VerifyOptions, run_verify

from stampla_desktop import buckets, theme
from stampla_desktop.base import MONO, Page, card, cli, relative, rich_label
from stampla_desktop.worker import run_monitored

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow

BLURB = "Recompute every name from metadata and content; report what disagrees."


class VerifyPage(Page):
    ready_status = "Run a check to see the archive's health."

    def __init__(self, window: MainWindow) -> None:
        super().__init__("Verify", window)
        self.subtitle.setText(BLURB)
        self.busy = False

        self.quick_button = QtWidgets.QPushButton("Check names (fast)")
        self.full_button = QtWidgets.QPushButton("Check everything")
        self.full_button.setObjectName("primary")
        self.recheck = QtWidgets.QCheckBox("Re-read all files (ignore cache)")
        self.quick_button.clicked.connect(lambda: self.start(skip_hash=True))
        self.full_button.clicked.connect(lambda: self.start(skip_hash=False))
        self.toolbar.addWidget(self.full_button)
        self.toolbar.addWidget(self.quick_button)
        self.toolbar.addWidget(self.recheck)
        self.toolbar.addStretch()
        self.add_work_controls()
        self.add_cli(self.cli_commands)
        self.recheck.toggled.connect(lambda _: self.cli_panel.refresh())
        self.show_empty(
            "✓",
            "The archive has not been checked yet",
            "Check everything re-computes every name from metadata and content.",
        )

    def cli_commands(self) -> list[tuple[str, str]]:
        base = ["verify", "--config", self.archive.config_path]
        extra = ["--full"] if self.recheck.isChecked() else []
        return [
            ("Check everything", cli(*base, *extra)),
            ("Check names (fast)", cli(*base, "--skip-hash", *extra)),
        ]

    def start(self, skip_hash: bool) -> None:
        if self.busy:
            return
        self.busy = True
        self.quick_button.setEnabled(False)
        self.full_button.setEnabled(False)
        self.work_started()
        self.status("Checking the archive…")
        options = VerifyOptions(
            skip_hash=skip_hash,
            workers=None,
            full=self.recheck.isChecked(),
            use_manifest=True,
        )
        archive = self.archive
        run_monitored(
            self,
            lambda monitor: run_verify(archive.config, archive.root, [], options, monitor),
            self._finished,
            self._failed,
            on_progress=self.show_progress,
            on_stopped=self._stopped,
            cancel=self.cancel,
        )

    def _finished(self, report: object) -> None:
        assert isinstance(report, Report)
        self._reset()
        self.status("Check finished.")
        self.render_report(report)
        problems = sum(
            1
            for finding in report.findings
            if finding.bucket.severity in (Severity.ALARM, Severity.ATTENTION)
        )
        self.window_.update_sidebar_label(self, f"Verify ({problems})" if problems else "Verify ✓")

    def _failed(self, message: str) -> None:
        self._reset()
        self.status(message)

    def _stopped(self) -> None:
        self._reset()
        self.status("Stopped — a check changes nothing, so there is nothing to clean up.")

    def _reset(self) -> None:
        self.busy = False
        self.quick_button.setEnabled(True)
        self.full_button.setEnabled(True)
        self.work_finished()

    def render_report(self, report: Report) -> None:
        self.clear_body()
        ok_color = theme.PALETTE["ok"]
        summary = rich_label(
            f"scanned <b>{report.scanned:,}</b> files in <b>{report.groups:,}</b>"
            f' groups — <span style="color:{ok_color}"><b>{report.ok:,} ok</b></span>,'
            f" {len(report.findings):,} findings"
        )
        self.add_card(summary)

        grouped: dict[Bucket, list[Finding]] = {}
        for finding in report.findings:
            grouped.setdefault(finding.bucket, []).append(finding)
        for bucket in BUCKET_ORDER:
            findings = grouped.get(bucket)
            if not findings:
                continue
            color = theme.PALETTE[buckets.color_of(bucket)]
            frame, layout = card()
            frame.setProperty("severity", buckets.color_of(bucket))
            layout.addWidget(
                rich_label(
                    f'<span style="color:{color}"><b>{len(findings):,} · '
                    f"{buckets.TITLE[bucket]}</b></span>"
                    f'&nbsp;&nbsp;<span style="color:{theme.PALETTE["muted"]}">'
                    f"{buckets.EXPLAIN[bucket]}</span>"
                )
            )
            root = self.archive.root
            for finding in findings[:100]:
                detail_html = _detail_html(finding)
                detail = f"&nbsp;&nbsp;{detail_html}" if detail_html else ""
                layout.addWidget(
                    rich_label(
                        f'<span style="{MONO}">'
                        f"{html.escape(relative(finding.path, root))}</span>{detail}"
                    )
                )
            if len(findings) > 100:
                more = QtWidgets.QLabel(f"…and {len(findings) - 100:,} more")
                more.setObjectName("faint")
                layout.addWidget(more)
            self.add_card(frame)
        for hint in report.hints:
            hint_label = QtWidgets.QLabel(f"hint: {hint}")
            hint_label.setObjectName("faint")
            hint_label.setWordWrap(True)
            self.add_card(hint_label)


def _detail_html(finding: Finding) -> str:
    """The detail line; rebuilt from structured data where it exists."""
    muted = theme.PALETTE["muted"]
    data = finding.data or {}
    if finding.bucket is Bucket.DATE_MISMATCH and "name_datetime" in data:
        return (
            f'<span style="color:{muted}">name says</span>'
            f' <span style="color:{theme.PALETTE["crit"]};{MONO}">'
            f"{html.escape(str(data['name_datetime']))}</span>"
            f'<span style="color:{muted}">, metadata says</span>'
            f' <span style="color:{theme.PALETTE["ok"]};{MONO}">'
            f"{html.escape(str(data['metadata_datetime']))}</span>"
            f' <span style="color:{theme.PALETTE["faint"]}">'
            f"({html.escape(str(data['source']))})</span>"
        )
    if not finding.detail:
        return ""
    return f'<span style="color:{muted}">{html.escape(finding.detail)}</span>'
