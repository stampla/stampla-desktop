"""The Overview: the archive at a glance, and where to go next."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from stampla_desktop import theme
from stampla_desktop.base import MONO, Page, card, rich_label

if TYPE_CHECKING:
    from stampla_desktop.app import MainWindow


class OverviewPage(Page):
    def __init__(self, window: MainWindow, tasks: list[tuple[str, str, int]]) -> None:
        super().__init__("Overview", window)
        archive = self.archive
        self.subtitle.setText(str(archive.root))

        frame, layout = card()
        layout.addWidget(rich_label(f"<b>{html.escape(archive.root.name)}</b>"))
        for tree in archive.config.trees:
            layout.addWidget(
                rich_label(
                    f'<span style="{MONO}">{html.escape(str(tree.path))}</span>'
                    f' <span style="color:{theme.PALETTE["muted"]}">— {tree.media},'
                    f" filed as {html.escape(tree.layout)}</span>"
                )
            )
        config_note = QtWidgets.QLabel(f"config: {archive.config_path}")
        config_note.setObjectName("faint")
        layout.addWidget(config_note)
        self.add_card(frame)

        for title, blurb, page_index in tasks:
            frame, layout = card()
            row = QtWidgets.QHBoxLayout()
            column = QtWidgets.QVBoxLayout()
            column.addWidget(rich_label(f"<b>{html.escape(title)}</b>"))
            blurb_label = QtWidgets.QLabel(blurb)
            blurb_label.setObjectName("sub")
            blurb_label.setWordWrap(True)
            column.addWidget(blurb_label)
            row.addLayout(column, 1)
            button = QtWidgets.QPushButton("Open")
            button.clicked.connect(lambda _=False, i=page_index: self.window_.go(i))
            row.addWidget(button, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            layout.addLayout(row)
            self.add_card(frame)
