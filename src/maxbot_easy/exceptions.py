"""Ошибки, которые библиотека показывает пользователю.

Все ошибки библиотеки наследуются от :class:`MaxBotEasyError`, поэтому в
программе достаточно поймать одну базовую ошибку::

    from maxbot_easy import Bot, MaxBotEasyError

    bot = Bot()
    try:
        bot.send("Привет!", chat_id=1)
    except MaxBotEasyError as problem:
        print("Не получилось:", problem)
"""

from __future__ import annotations

__all__ = [
    "MaxBotEasyAPIError",
    "MaxBotEasyError",
    "MaxBotEasyNetworkError",
]


class MaxBotEasyError(Exception):
    """Общая ошибка библиотеки: всё, что пошло не так при работе с ботом."""


class MaxBotEasyAPIError(MaxBotEasyError):
    """Сервер MAX отклонил запрос.

    Так бывает, если токен неверный, бот не добавлен в чат или сервис
    временно не принимает запросы.

    Args:
        message: Понятное человеку объяснение и подсказка, что делать.
        code: Код ошибки от сервера MAX, если сервер его прислал.
        original: Исходная ошибка библиотеки ``maxapi`` — пригодится, когда
            нужно посмотреть технические детали.
    """

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        original: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.original = original

    def __str__(self) -> str:
        if self.code is None:
            return self.message

        return f"{self.message} (код ошибки от сервера MAX: {self.code})"


class MaxBotEasyNetworkError(MaxBotEasyError):
    """Не удалось связаться с сервером MAX.

    Обычно причина в интернете или в том, что сервис недоступен. Можно
    подождать и попробовать снова.

    Args:
        message: Понятное человеку объяснение и подсказка, что делать.
        original: Исходная ошибка библиотеки ``maxapi`` — пригодится, когда
            нужно посмотреть технические детали.
    """

    def __init__(
        self,
        message: str,
        *,
        original: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.original = original
