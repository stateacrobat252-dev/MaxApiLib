"""Утилиты времени и простые таймеры.

Все таймеры работают в фоновых демон-потоках и не мешают завершению
программы: если бот остановлен, а таймер не отменён, процесс всё равно
завершится.

Пример::

    from maxapilib import every, later

    later(5, lambda: print("прошло 5 секунд"))
    watchdog = every(60, lambda: print("минута"))

    watchdog.cancel()  # остановить циклический таймер
"""

from __future__ import annotations

import datetime
import re
import threading
import time
from collections.abc import Callable

__all__ = [
    "Timer",
    "every",
    "humanize_delay",
    "later",
    "now",
    "parse_time",
    "sleep",
]

_UNITS: dict[str, float] = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}

_TIME_PATTERN = re.compile(
    r"^\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[smhd]?)\s*$"
)


class Timer:
    """Таймер, который можно остановить.

    Возвращается функциями :func:`later` и :func:`every`.

    Attributes:
        interval: Интервал таймера в секундах.
        repeating: ``True`` для циклического таймера (:func:`every`).
    """

    def __init__(
        self,
        thread: threading.Thread,
        stop_event: threading.Event,
        *,
        interval: float,
        repeating: bool,
    ) -> None:
        self._thread = thread
        self._stop_event = stop_event
        self.interval = interval
        self.repeating = repeating

    @property
    def is_alive(self) -> bool:
        """``True``, пока таймер ждёт следующего срабатывания."""
        return self._thread.is_alive()

    def cancel(self) -> None:
        """Остановить таймер. Повторный вызов безопасен."""
        self._stop_event.set()

    def __repr__(self) -> str:
        kind = "every" if self.repeating else "later"
        return f"<Timer {kind}={self.interval:g}s alive={self.is_alive}>"


def now() -> datetime.datetime:
    """Текущие дата и время."""
    return datetime.datetime.now()


def sleep(seconds: float) -> None:
    """Пауза в текущем потоке."""
    time.sleep(seconds)


def parse_time(value: str | None) -> float:
    """Перевести строку вида ``"10s"``, ``"5m"``, ``"2h"``, ``"1d"`` в секунды.

    Строка без суффикса трактуется как секунды. Если разобрать не удалось,
    возвращается ``0.0``.
    """
    if not isinstance(value, str):
        return 0.0

    match = _TIME_PATTERN.match(value)
    if match is None:
        return 0.0

    number = match.group("value").replace(",", ".")
    unit = match.group("unit")
    return float(number) * _UNITS.get(unit, 1.0)


def humanize_delay(seconds: float) -> str:
    """Короткое человекочитаемое представление интервала.

    ``30 -> "30c"``, ``120 -> "2m"``, ``3600 -> "1h"``, ``90000 -> "1d"``.
    Отрицательные значения приводятся к ``"0c"``.
    """
    if seconds < 60:
        return f"{int(max(seconds, 0))}c"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def later(seconds: float, callback: Callable[[], object]) -> Timer:
    """Вызвать ``callback`` один раз через ``seconds`` секунд.

    Returns:
        Timer: Таймер, который можно отменить до срабатывания.
    """
    stop_event = threading.Event()

    def runner() -> None:
        if not stop_event.wait(seconds):
            callback()

    thread = threading.Thread(target=runner, name="maxapilib-later", daemon=True)
    thread.start()
    return Timer(thread, stop_event, interval=seconds, repeating=False)


def every(
    seconds: float,
    callback: Callable[[], object],
    *,
    run_immediately: bool = False,
) -> Timer:
    """Вызывать ``callback`` каждые ``seconds`` секунд.

    Args:
        seconds: Интервал между вызовами в секундах (больше нуля).
        callback: Функция без аргументов.
        run_immediately: Вызвать ``callback`` сразу, не дожидаясь интервала.

    Returns:
        Timer: Таймер; вызовите ``timer.cancel()``, чтобы остановить цикл.

    Raises:
        ValueError: Если интервал не больше нуля.
    """
    if seconds <= 0:
        message = "Интервал every() должен быть больше нуля"
        raise ValueError(message)

    stop_event = threading.Event()

    def runner() -> None:
        if run_immediately:
            callback()
        while not stop_event.wait(seconds):
            callback()

    thread = threading.Thread(target=runner, name="maxapilib-every", daemon=True)
    thread.start()
    return Timer(thread, stop_event, interval=seconds, repeating=True)
