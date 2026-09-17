"""Настройка логирования MaxApiLib.

По умолчанию библиотека не пишет логи (используется ``NullHandler``),
чтобы не мешать приложению. При отладке включите их явно::

    import maxapilib

    maxapilib.enable_logging()          # уровень INFO
    maxapilib.enable_logging("DEBUG")   # подробный разбор работы бота
"""

from __future__ import annotations

import logging

__all__ = ["LOG_FORMAT", "enable_logging"]

#: Формат строк логов.
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def resolve_level(level: int | str) -> int:
    """Превратить строку уровня ("DEBUG") или число в числовой уровень.

    Raises:
        ValueError: Если название уровня неизвестно.
    """
    if isinstance(level, int):
        return level

    resolved = logging.getLevelName(level.upper())
    if not isinstance(resolved, int):
        message = (
            f"Неизвестный уровень логирования {level!r}. "
            "Используйте, например, 'DEBUG', 'INFO' или 'WARNING'."
        )
        raise ValueError(message)
    return resolved


def enable_logging(level: int | str = logging.INFO) -> None:
    """Включить вывод логов MaxApiLib и ``maxapi``.

    Args:
        level: Уровень логирования (строка или число).

    Raises:
        ValueError: Если название уровня неизвестно.
    """
    value = resolve_level(level)

    logging.basicConfig(level=value, format=LOG_FORMAT)
    logging.getLogger("maxapilib").setLevel(value)
    # maxapi пишет много INFO-логов о каждом событии: при обычной отладке
    # достаточно предупреждений, подробности — только на уровне DEBUG.
    logging.getLogger("maxapi").setLevel(
        logging.DEBUG if value <= logging.DEBUG else logging.WARNING
    )
