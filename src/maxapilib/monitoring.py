"""Счётчики и логирование событий для мониторинга.

Модуль отвечает за две вещи:

* :class:`Monitor` — middleware, которое видит **каждое** событие от MAX
  (даже то, под которое не нашлось обработчика) и пишет его в лог;
* :class:`Stats` — счётчики, которые можно смотреть в любой момент::

      print(bot.stats)          # «события: 12 (сообщения 9, кнопки 3) | ...»
      bot.stats.as_dict()       # то же в виде словаря (для JSON)

В режиме вебхука счётчики доступны по адресу ``/stats``, а состояние
бота — по ``/health``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from maxapi.filters.middleware import BaseMiddleware
from maxapi.types.updates import UpdateUnion
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated

from .time_utils import humanize_delay
from .types import text_of

if TYPE_CHECKING:
    from maxapi.filters.middleware import HandlerCallable

__all__ = ["Monitor", "Stats", "describe_event"]

logger = logging.getLogger("maxapilib")


@dataclass
class Stats:
    """Счётчики работы бота.

    Attributes:
        started_at: Момент запуска бота (``time.monotonic()``).
        events: Сколько всего событий пришло от MAX.
        messages: Сколько пришло сообщений.
        callbacks: Сколько было нажатий кнопок.
        started: Сколько раз пользователи запускали бота.
        sent: Сколько сообщений отправил бот.
        answers: Сколько ответов на нажатия кнопок отправлено.
        errors: Сколько ошибок случилось в обработчиках.
        last_error: Текст последней ошибки.
    """

    started_at: float | None = None
    events: int = 0
    messages: int = 0
    callbacks: int = 0
    started: int = 0
    sent: int = 0
    answers: int = 0
    errors: int = 0
    last_error: str | None = None

    def mark_started(self, *, reset: bool = True) -> None:
        """Запомнить момент запуска бота."""
        if reset or self.started_at is None:
            self.started_at = time.monotonic()

    def mark_stopped(self) -> None:
        """Забыть момент запуска: бот остановлен."""
        self.started_at = None

    @property
    def uptime(self) -> float:
        """Сколько секунд бот работает (``0``, если он остановлен)."""
        if self.started_at is None:
            return 0.0
        return time.monotonic() - self.started_at

    @property
    def running(self) -> bool:
        """``True``, пока бот запущен."""
        return self.started_at is not None

    def count_event(self, event: UpdateUnion) -> None:
        """Учесть входящее событие."""
        self.events += 1

        if isinstance(event, MessageCreated):
            self.messages += 1
        elif isinstance(event, MessageCallback):
            self.callbacks += 1
        elif isinstance(event, BotStarted):
            self.started += 1

    def count_sent(self) -> None:
        """Учесть отправленное сообщение."""
        self.sent += 1

    def count_answer(self) -> None:
        """Учесть ответ на нажатие кнопки."""
        self.answers += 1

    def count_error(self, error: BaseException) -> None:
        """Учесть ошибку в обработчике."""
        self.errors += 1
        self.last_error = f"{type(error).__name__}: {error}"

    def as_dict(self) -> dict[str, Any]:
        """Счётчики в виде словаря (удобно для JSON и мониторинга)."""
        return {
            "status": "running" if self.running else "stopped",
            "uptime_seconds": round(self.uptime, 1),
            "uptime": humanize_delay(self.uptime) if self.running else "0c",
            "events": self.events,
            "messages": self.messages,
            "callbacks": self.callbacks,
            "bot_started": self.started,
            "sent": self.sent,
            "answers": self.answers,
            "errors": self.errors,
            "last_error": self.last_error,
        }

    def __str__(self) -> str:
        status = "работает" if self.running else "остановлен"
        parts = [
            f"статус: {status}",
            f"события: {self.events}",
            f"сообщения: {self.messages}",
            f"кнопки: {self.callbacks}",
            f"отправлено: {self.sent}",
            f"ответов на кнопки: {self.answers}",
            f"ошибки: {self.errors}",
        ]
        if self.running:
            parts.append(f"работает: {humanize_delay(self.uptime)}")
        if self.last_error is not None:
            parts.append(f"последняя ошибка: {self.last_error}")
        return " | ".join(parts)


def describe_event(event: UpdateUnion) -> str:
    """Короткое описание события для лога.

    Примеры: ``сообщение от 42 в чат 100: '/start'``,
    ``нажатие кнопки 'site' (пользователь 42, чат 100)``.
    """
    if isinstance(event, MessageCreated):
        message = event.message
        sender = message.sender
        user_id = sender.user_id if sender is not None else None
        text = text_of(message) or ""
        return f"сообщение от {user_id} в чат {message.recipient.chat_id}: {text!r}"

    if isinstance(event, MessageCallback):
        callback = event.callback
        user = callback.user
        user_id = user.user_id if user is not None else None
        chat_id = (
            event.message.recipient.chat_id if event.message is not None else None
        )
        return (
            f"нажатие кнопки {callback.payload!r} "
            f"(пользователь {user_id}, чат {chat_id})"
        )

    if isinstance(event, BotStarted):
        return (
            f"запуск бота пользователем {event.user.user_id} "
            f"(чат {event.chat_id})"
        )

    return f"событие {event.update_type}"


class Monitor(BaseMiddleware):
    """Middleware, которое считает события и пишет их в лог.

    Регистрируется библиотекой автоматически: при ``enable_logging()``
    видно каждое входящее событие, даже если под него нет обработчика.
    """

    def __init__(self, stats: Stats) -> None:
        self.stats = stats

    async def __call__(
        self,
        handler: HandlerCallable,
        event_object: UpdateUnion,
        data: dict[str, Any],
    ) -> Any:
        """Учесть событие, залогировать его и передать дальше."""
        self.stats.count_event(event_object)
        logger.info("← %s", describe_event(event_object))

        started = time.monotonic()
        try:
            return await handler(event_object, data)
        finally:
            logger.debug(
                "Событие обработано за %.3f c", time.monotonic() - started
            )
