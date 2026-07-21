"""Tests for the background worker."""

from __future__ import annotations

import threading

import pytest
from PySide6 import QtWidgets
from stampla.progress import Monitor, ProgressEvent

from stampla_desktop.worker import run_async, run_monitored
from tests.support import spin


class TestRunAsync:
    def test_delivers_the_result_on_the_ui_thread(self, qapp: QtWidgets.QApplication) -> None:
        results: list[object] = []
        run_async(qapp, lambda: 41 + 1, results.append, pytest.fail)
        spin(qapp, lambda: bool(results))
        assert results == [42]

    def test_exceptions_become_failure_messages(self, qapp: QtWidgets.QApplication) -> None:
        failures: list[str] = []

        def boom() -> object:
            raise ValueError("boom")

        run_async(qapp, boom, lambda result: pytest.fail(str(result)), failures.append)
        spin(qapp, lambda: bool(failures))
        assert failures == ["ValueError: boom"]


class TestRunMonitored:
    def test_progress_events_arrive_and_the_final_one_always_lands(
        self, qapp: QtWidgets.QApplication
    ) -> None:
        events: list[ProgressEvent] = []
        results: list[object] = []

        def work(monitor: Monitor) -> str:
            for done in range(1, 5):
                monitor.step("hash", done, 4)
            return "done"

        run_monitored(qapp, work, results.append, pytest.fail, on_progress=events.append)
        spin(qapp, lambda: bool(results))
        assert results == ["done"]
        assert events, "at least one progress event must arrive"
        assert events[-1].done == 4  # done == total beats the throttle

    def test_cancel_fires_stopped_instead_of_done(self, qapp: QtWidgets.QApplication) -> None:
        stopped: list[bool] = []
        cancel = threading.Event()
        cancel.set()

        def work(monitor: Monitor) -> str:
            monitor.check()
            return "never"

        run_monitored(
            qapp,
            work,
            lambda _result: pytest.fail("done must not fire"),
            pytest.fail,
            on_stopped=lambda: stopped.append(True),
            cancel=cancel,
        )
        spin(qapp, lambda: bool(stopped))
        assert stopped == [True]
