"""Тесты утилит времени и таймеров."""

from __future__ import annotations

import threading
import time

import pytest

from maxapilib import Timer, every, humanize_delay, later, now, parse_time, sleep


def test_now() -> None:
    current = now()
    assert current.year >= 2024
    assert current.month in range(1, 13)


def test_sleep() -> None:
    start = time.monotonic()
    sleep(0.05)
    assert time.monotonic() - start >= 0.05


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10s", 10.0),
        ("5m", 300.0),
        ("1h", 3600.0),
        ("1d", 86400.0),
        ("10", 10.0),
        (" 2.5m ", 150.0),
        ("1,5h", 5400.0),
    ],
)
def test_parse_time(value: str, expected: float) -> None:
    assert parse_time(value) == expected


@pytest.mark.parametrize("value", ["", "invalid", None, "m", "10x"])
def test_parse_time_invalid(value: str | None) -> None:
    assert parse_time(value) == 0.0


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(30, "30c"), (120, "2m"), (3600, "1h"), (86400, "1d"), (90000, "1d"), (-5, "0c")],
)
def test_humanize_delay(seconds: float, expected: str) -> None:
    assert humanize_delay(seconds) == expected


def test_later_calls_callback() -> None:
    called = threading.Event()
    later(0.05, called.set)

    assert called.wait(timeout=2.0)


def test_later_can_be_cancelled() -> None:
    called = threading.Event()
    timer = later(0.3, called.set)

    assert isinstance(timer, Timer)
    assert timer.is_alive
    timer.cancel()
    assert not called.wait(timeout=0.5)  # колбэк не должен сработать
    timer.cancel()  # повторная отмена безопасна


def test_every_calls_callback_until_cancel() -> None:
    counter = threading.Event()
    calls: list[int] = []

    def callback() -> None:
        calls.append(1)
        if len(calls) >= 3:
            counter.set()

    timer = every(0.05, callback)
    assert counter.wait(timeout=2.0)
    timer.cancel()

    assert timer.repeating
    assert repr(timer).startswith("<Timer every=")


def test_every_run_immediately() -> None:
    calls: list[int] = []
    timer = every(5, lambda: calls.append(1), run_immediately=True)
    try:
        assert calls == [1]
    finally:
        timer.cancel()


def test_every_rejects_bad_interval() -> None:
    with pytest.raises(ValueError, match="больше нуля"):
        every(0, lambda: None)


def test_timers_do_not_block_interpreter_exit() -> None:
    """Таймеры не должны держать процесс (иначе pytest зависает)."""
    timer = every(60, lambda: None)
    try:
        threads = [
            thread
            for thread in threading.enumerate()
            if thread.name.startswith("maxapilib-")
        ]
        assert threads
        assert all(thread.daemon for thread in threads)
    finally:
        timer.cancel()
