"""Render the app icon: an aperture iris with clock hands in the opening.

Regenerates every size from geometry — there is no source image. Small
sizes are redrawn with heavier strokes and less detail rather than
downscaled, so the mark stays legible in the Dock and the menu bar.

Usage:
    python assets/make_icon.py

Writes the window icon into the package resources, and on macOS also
builds assets/icon.icns via iconutil.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

GRAPHITE = QtGui.QColor("#1e2128")
GRAPHITE_EDGE = QtGui.QColor("#16181d")
AMBER = QtGui.QColor("#e8a33d")
HANDS = QtGui.QColor("#e9e7e2")

#: side of the generated square, one render per icns slot
ICONSET_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def _pen(color: QtGui.QColor, width: float) -> QtGui.QPen:
    pen = QtGui.QPen(color, width)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    return pen


def draw(painter: QtGui.QPainter, size: int) -> None:
    center = QtCore.QPointF(size / 2, size / 2)
    small = size <= 64
    tiny = size <= 16

    tile = QtCore.QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88)
    gradient = QtGui.QLinearGradient(0, tile.top(), 0, tile.bottom())
    gradient.setColorAt(0.0, GRAPHITE)
    gradient.setColorAt(1.0, GRAPHITE_EDGE)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(tile, size * 0.20, size * 0.20)

    ring_r = size * 0.315
    painter.setPen(_pen(AMBER, size * (0.055 if small else 0.036)))
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    painter.drawEllipse(center, ring_r, ring_r)

    if not tiny:
        # aperture iris: six pinwheel blades from the rim to the opening
        outer_r = ring_r * 0.92
        open_r = ring_r * 0.54
        painter.setPen(_pen(AMBER, size * (0.045 if small else 0.028)))
        twist = math.radians(62.0)
        for i in range(6):
            start = math.tau * i / 6
            painter.drawLine(
                QtCore.QPointF(
                    center.x() + outer_r * math.cos(start),
                    center.y() + outer_r * math.sin(start),
                ),
                QtCore.QPointF(
                    center.x() + open_r * math.cos(start + twist),
                    center.y() + open_r * math.sin(start + twist),
                ),
            )

    # clock hands at 10:08; the aperture opening is the dial
    hands = ((-60.0, 0.26, 0.046), (35.0, 0.40, 0.032))
    if tiny:
        hands = ((-60.0, 0.42, 0.085), (35.0, 0.62, 0.065))
    elif small:
        hands = ((-60.0, 0.26, 0.060), (35.0, 0.40, 0.048))
    for angle_deg, length, width in hands:
        angle = math.radians(angle_deg - 90.0)
        painter.setPen(_pen(HANDS, size * width))
        painter.drawLine(
            center,
            QtCore.QPointF(
                center.x() + ring_r * length * math.cos(angle),
                center.y() + ring_r * length * math.sin(angle),
            ),
        )

    if not small:
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(AMBER)
        painter.drawEllipse(center, size * 0.024, size * 0.024)


def render(size: int) -> QtGui.QImage:
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    draw(painter, size)
    painter.end()
    return image


def main() -> None:
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assets = Path(__file__).resolve().parent
    package = assets.parent / "src" / "stampla_desktop"

    resources = package / "resources"
    resources.mkdir(exist_ok=True)
    render(256).save(str(resources / "icon.png"))

    iconset = assets / "icon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()
    for size in ICONSET_SIZES:
        image = render(size)
        if size < 1024:
            image.save(str(iconset / f"icon_{size}x{size}.png"))
        if size > 16:
            image.save(str(iconset / f"icon_{size // 2}x{size // 2}@2x.png"))

    if sys.platform == "darwin" and shutil.which("iconutil"):
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(assets / "icon.icns")],
            check=True,
        )
        shutil.rmtree(iconset)
        print(f"wrote {resources / 'icon.png'} and {assets / 'icon.icns'}")
    else:
        print(f"wrote {resources / 'icon.png'} and {iconset}/ (no iconutil; icns skipped)")


if __name__ == "__main__":
    main()
