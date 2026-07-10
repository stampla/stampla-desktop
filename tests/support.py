"""Test helpers: an event-loop pump and a miniature archive builder."""

from __future__ import annotations

import base64
import hashlib
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtWidgets

# A minimal valid 1x1 JPEG.
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHR"
    "ofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QA"
    "FAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN"
    "//2Q=="
)

CONFIG_TEMPLATE = """
root = {root!r}

[[trees]]
path = "Photos"
media = "photo"

[extensions]
raw = ["jpg"]
mutable = []
"""


def spin(app: QtWidgets.QApplication, done: Callable[[], bool], timeout: float = 30.0) -> None:
    """Pump the event loop until ``done()`` — cross-thread signals need it."""
    deadline = time.monotonic() + timeout
    while not done():
        if time.monotonic() > deadline:
            raise TimeoutError("condition not met before timeout")
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def write_config(root: Path, extra: str = "") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    config = root / "config.toml"
    config.write_text(CONFIG_TEMPLATE.format(root=str(root)) + extra)
    return config


def make_master(directory: Path, capture: str, seasoning: bytes = b"") -> Path:
    """A canonically named JPEG with the given capture time."""
    directory.mkdir(parents=True, exist_ok=True)
    scratch = directory / "scratch.jpg"
    scratch.write_bytes(TINY_JPEG + seasoning)
    subprocess.run(
        [
            "exiftool",
            "-q",
            "-overwrite_original",
            f"-EXIF:DateTimeOriginal={capture}",
            str(scratch),
        ],
        check=True,
    )
    digest = hashlib.md5(scratch.read_bytes()).hexdigest()
    compact = capture.replace(":", "").replace(" ", "_")
    named = directory / f"{compact}_{digest[:8]}.jpg"
    scratch.rename(named)
    return named


def page_of(window: object, kind: type) -> object:
    """The window's page of the given type; sidebar order is not our contract."""
    stack = window.stack  # type: ignore[attr-defined]
    for index in range(stack.count()):
        widget = stack.widget(index)
        if isinstance(widget, kind):
            return widget
    raise AssertionError(f"no {kind.__name__} in the stack")
