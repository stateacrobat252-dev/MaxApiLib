"""Иерархия исключений MaxApiLib.

Все ошибки библиотеки наследуются от :class:`MaxApiLibError`, поэтому
достаточно одного ``except MaxApiLibError`` в коде бота::

    from maxapilib import Bot, MaxApiLibError

    bot = Bot()
    try:
        bot.send("Привет!", chat_id=42)
    except MaxApiLibError as exc:
        print("Не получилось отправить сообщение:", exc)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "MaxApiLibAPIError",
    "MaxApiLibAuthError",
    "MaxApiLibError",
    "MaxApiLibNetworkError",
    "MaxApiLibTimeoutError",
]


class MaxApiLibError(Exception):
    """Базовое исключение MaxApiLib.

    Attributes:
        message: Текст ошибки.
        details: Дополнительные данные об ошибке (например, код ответа API).
    """

    def __init__(
        self, message: str, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class MaxApiLibAPIError(MaxApiLibError):
    """API MAX ответил ошибкой или принял некорректные данные."""


class MaxApiLibAuthError(MaxApiLibAPIError):
    """Токен бота неверен, отозван или не передан."""


class MaxApiLibNetworkError(MaxApiLibAPIError):
    """Не удалось соединиться с API MAX."""


class MaxApiLibTimeoutError(MaxApiLibAPIError):
    """Синхронный вызов не успел выполниться за отведённое время."""
