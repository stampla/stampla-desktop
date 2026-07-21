"""Run library calls off the UI thread, reporting back via signals."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from PySide6 import QtCore
from stampla.progress import Cancelled, Monitor, ProgressEvent


class _Task(QtCore.QObject):
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    stopped = QtCore.Signal()
    progress = QtCore.Signal(object)  # ProgressEvent


def run_async(
    owner: QtCore.QObject,
    fn: Callable[[], object],
    on_done: Callable[[object], None],
    on_failed: Callable[[str], None],
) -> None:
    """Run ``fn`` in a thread; deliver the result on the UI thread."""
    run_monitored(owner, lambda _monitor: fn(), on_done, on_failed)


def run_monitored(
    owner: QtCore.QObject,
    fn: Callable[[Monitor], object],
    on_done: Callable[[object], None],
    on_failed: Callable[[str], None],
    on_progress: Callable[[ProgressEvent], None] | None = None,
    on_stopped: Callable[[], None] | None = None,
    cancel: threading.Event | None = None,
) -> None:
    """Run ``fn(monitor)`` in a thread with live progress and a stop flag.

    Progress events are throttled in the worker thread (the UI repaints
    at most ~20 times a second) and always include a phase's final
    event. Setting ``cancel`` raises Cancelled inside the library at the
    next safe point; ``on_stopped`` then fires instead of ``on_done``.
    """
    task = _Task(owner)

    def finish(handler: Callable[..., None]) -> Callable[..., None]:
        def handle(*args: object) -> None:
            try:
                handler(*args)
            finally:
                task.deleteLater()

        return handle

    task.done.connect(finish(on_done))
    task.failed.connect(finish(on_failed))
    task.stopped.connect(finish(on_stopped if on_stopped is not None else lambda: None))
    if on_progress is not None:
        task.progress.connect(on_progress)

    last = 0.0

    def emit_progress(event: ProgressEvent) -> None:
        nonlocal last
        now = time.monotonic()
        if now - last < 0.05 and event.done != event.total:
            return
        last = now
        task.progress.emit(event)

    monitor = Monitor(
        callback=emit_progress if on_progress is not None else None,
        should_cancel=cancel.is_set if cancel is not None else None,
    )

    def target() -> None:
        try:
            result = fn(monitor)
        except Cancelled:
            task.stopped.emit()
        except Exception as exc:
            task.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            task.done.emit(result)

    threading.Thread(target=target, daemon=True).start()
