"""Render the app icon: an aperture iris carved from an amber disc, with
clock hands at 10:08 in the opening.

Regenerates every size from geometry — there is no source image. Small
sizes are simplified (no hands at 16px, heavier cuts at 32) rather than
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

TILE_TOP = QtGui.QColor("#23262e")
TILE_BOTTOM = QtGui.QColor("#14161b")
DISC_LIGHT = QtGui.QColor("#f2b459")
DISC_DARK = QtGui.QColor("#cf8a24")
CUT = QtGui.QColor("#181a20")
HANDS = QtGui.QColor("#f4f1ea")
PINION = QtGui.QColor("#e8a33d")

#: side of the generated square, one render per icns slot
ICONSET_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def _pt(center: QtCore.QPointF, r: float, a: float) -> QtCore.QPointF:
    return QtCore.QPointF(center.x() + r * math.cos(a), center.y() + r * math.sin(a))


def _ray_to_circle(
    origin: QtCore.QPointF,
    direction: tuple[float, float],
    center: QtCore.QPointF,
    radius: float,
) -> QtCore.QPointF:
    """Farthest intersection of origin + t*direction with the circle."""
    ox, oy = origin.x() - center.x(), origin.y() - center.y()
    dx, dy = direction
    a = dx * dx + dy * dy
    b = 2 * (ox * dx + oy * dy)
    c = ox * ox + oy * oy - radius * radius
    t = (-b + math.sqrt(max(b * b - 4 * a * c, 0.0))) / (2 * a)
    return QtCore.QPointF(origin.x() + t * dx, origin.y() + t * dy)


def _hand(
    p: QtGui.QPainter,
    center: QtCore.QPointF,
    a: float,
    length: float,
    base_w: float,
    tip_w: float,
) -> None:
    """A tapered hand: wide at the pinion, narrow at the tip."""
    tip = _pt(center, length, a)
    nx, ny = math.cos(a + math.tau / 4), math.sin(a + math.tau / 4)
    back = _pt(center, -length * 0.14, a)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(HANDS)
    p.drawPolygon(
        QtGui.QPolygonF(
            [
                QtCore.QPointF(back.x() + nx * base_w / 2, back.y() + ny * base_w / 2),
                QtCore.QPointF(back.x() - nx * base_w / 2, back.y() - ny * base_w / 2),
                QtCore.QPointF(tip.x() - nx * tip_w / 2, tip.y() - ny * tip_w / 2),
                QtCore.QPointF(tip.x() + nx * tip_w / 2, tip.y() + ny * tip_w / 2),
            ]
        )
    )


def draw(painter: QtGui.QPainter, size: int) -> None:
    center = QtCore.QPointF(size / 2, size / 2)
    small = size <= 64
    tiny = size <= 16

    tile = QtCore.QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88)
    g = QtGui.QLinearGradient(0, tile.top(), 0, tile.bottom())
    g.setColorAt(0.0, TILE_TOP)
    g.setColorAt(1.0, TILE_BOTTOM)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(g)
    painter.drawRoundedRect(tile, size * 0.20, size * 0.20)

    disc_r = size * 0.335
    painter.setBrush(QtGui.QColor(0, 0, 0, 70))
    painter.drawEllipse(
        QtCore.QPointF(center.x(), center.y() + size * 0.012), disc_r * 1.03, disc_r * 1.03
    )
    rg = QtGui.QRadialGradient(_pt(center, disc_r * 0.75, math.radians(-125)), disc_r * 2.1)
    rg.setColorAt(0.0, DISC_LIGHT)
    rg.setColorAt(1.0, DISC_DARK)
    painter.setBrush(rg)
    painter.drawEllipse(center, disc_r, disc_r)

    # aperture iris: hexagonal opening plus each side extended to the rim
    open_r = disc_r * 0.56
    rot = math.radians(-15.0)
    verts = [_pt(center, open_r, rot + k * math.tau / 6) for k in range(6)]
    painter.setBrush(CUT)
    painter.drawPolygon(QtGui.QPolygonF(verts))
    cut_pen = QtGui.QPen(CUT, size * (0.034 if small else 0.022))
    cut_pen.setCapStyle(QtCore.Qt.PenCapStyle.FlatCap)
    painter.setPen(cut_pen)
    for k in range(6):
        a, b = verts[k - 1], verts[k]
        d = (b.x() - a.x(), b.y() - a.y())
        n = math.hypot(*d)
        painter.drawLine(b, _ray_to_circle(b, (d[0] / n, d[1] / n), center, disc_r))

    if tiny:
        return  # at 16px the iris alone is the mark

    # clock hands at 10:08; the aperture opening is the dial
    scale = 1.35 if small else 1.0
    _hand(
        painter,
        center,
        math.radians(-150.0),
        disc_r * 0.30,
        size * 0.046 * scale,
        size * 0.024 * scale,
    )
    _hand(
        painter,
        center,
        math.radians(-55.0),
        disc_r * 0.46,
        size * 0.034 * scale,
        size * 0.015 * scale,
    )
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(PINION)
    painter.drawEllipse(center, size * 0.030 * scale, size * 0.030 * scale)
    painter.setBrush(CUT)
    painter.drawEllipse(center, size * 0.013 * scale, size * 0.013 * scale)


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
