"""Настройка логирования MaxApiLib.

``Bot`` включает логи по умолчанию (уровень ``INFO``): в консоли видно,
что бот получил событие и что отправил в ответ. Если приложение уже
настроило ``logging``, библиотека ничего не меняет.

Дополнительно можно писать логи в файл::

    import maxapilib

    maxapilib.enable_logging("DEBUG", file="bot.log")

    # или сразу при создании бота:
    bot = maxapilib.Bot(log_level="DEBUG", log_file="bot.log")
"""

from __future__ import annotations

import logging
from pathlib import Path

__all__ = ["LOG_FORMAT", "close_log_files", "enable_logging", "resolve_level"]

#: Формат строк логов.
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

#: Уровень библиотеки по умолчанию.
DEFAULT_LEVEL = logging.INFO

_MAXAPI_LOGGER = "maxapi"
_LIBRARY_LOGGER = "maxapilib"


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


def _file_handler(path: str | Path) -> logging.FileHandler:
    """Создать обработчик файла, если такого ещё нет."""
    filename = Path(path).resolve()

    root = logging.getLogger()
    for existing in root.handlers:
        if isinstance(existing, logging.FileHandler) and (
            Path(existing.baseFilename).resolve() == filename
        ):
            return existing

    handler = logging.FileHandler(filename, encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    return handler


def enable_logging(
    level: int | str = DEFAULT_LEVEL,
    *,
    file: str | Path | None = None,
) -> None:
    """Включить логи MaxApiLib и ``maxapi``.

    Args:
        level: Уровень логирования: ``"DEBUG"``, ``"INFO"``, ``"WARNING"``
            или число.
        file: Путь к файлу, куда дополнительно писать логи.

    Raises:
        ValueError: Если название уровня неизвестно.
    """
    value = resolve_level(level)

    # Консоль: basicConfig ничего не делает, если приложение уже
    # настроило логирование само.
    logging.basicConfig(level=value, format=LOG_FORMAT)
    logging.getLogger(_LIBRARY_LOGGER).setLevel(value)

    # maxapi пишет много INFO-логов о каждом событии: при обычной отладке
    # достаточно предупреждений, подробности — только на уровне DEBUG.
    logging.getLogger(_MAXAPI_LOGGER).setLevel(
        logging.DEBUG if value <= logging.DEBUG else logging.WARNING
    )

    if file is not None:
        _file_handler(file)


def close_log_files() -> None:
    """Закрыть файловые обработчики, созданные :func:`enable_logging`.

    Полезно в тестах и при остановке бота: файл перестаёт быть занятым.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, logging.FileHandler):
            root.removeHandler(handler)
            handler.close()
