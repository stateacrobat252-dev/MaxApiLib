"""Вспомогательные средства тестов: события MAX и заглушка HTTP-слоя."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from maxapi.exceptions.max import InvalidToken

BOT_USER: dict[str, Any] = {
    "user_id": 1,
    "first_name": "MaxApiLib Bot",
    "username": "maxapilib_bot",
    "is_bot": True,
    "last_activity_time": 1700000000000,
}

USER: dict[str, Any] = {
    "user_id": 42,
    "first_name": "Иван",
    "is_bot": False,
    "last_activity_time": 1700000000000,
}

CHAT_ID = 100

CHAT: dict[str, Any] = {
    "chat_id": CHAT_ID,
    "type": "dialog",
    "status": "active",
    "last_event_time": 1700000000000,
    "participants_count": 2,
    "owner_id": 42,
    "is_public": False,
}


def message_created(
    text: str = "/start", *, mid: str = "mid.1", chat_id: int = CHAT_ID
) -> dict[str, Any]:
    """Событие ``message_created`` в том виде, в каком его присылает MAX."""
    return {
        "update_type": "message_created",
        "timestamp": 1700000000000,
        "message": {
            "sender": USER,
            "recipient": {"chat_id": chat_id, "chat_type": "dialog"},
            "timestamp": 1700000000000,
            "body": {"mid": mid, "seq": 1, "text": text},
        },
    }


def message_callback(
    payload: str = "go", *, callback_id: str = "cb-1", chat_id: int = CHAT_ID
) -> dict[str, Any]:
    """Событие ``message_callback`` (нажатие inline-кнопки)."""
    return {
        "update_type": "message_callback",
        "timestamp": 1700000000001,
        "message": {
            "sender": USER,
            "recipient": {"chat_id": chat_id, "chat_type": "dialog"},
            "timestamp": 1700000000000,
            "body": {"mid": "mid.10", "seq": 1, "text": "Меню"},
        },
        "callback": {
            "timestamp": 1700000000001,
            "callback_id": callback_id,
            "payload": payload,
            "user": USER,
        },
    }


def bot_started(
    *, chat_id: int = CHAT_ID, payload: str | None = None
) -> dict[str, Any]:
    """Событие ``bot_started`` (пользователь нажал «Начать»)."""
    return {
        "update_type": "bot_started",
        "timestamp": 1700000000002,
        "chat_id": chat_id,
        "user": USER,
        "payload": payload,
    }


class FakeTransport:
    """Заглушка MAX Bot API.

    Attributes:
        calls: Все запросы к API в порядке отправки.
        messages: Запросы ``POST /messages``.
        answers: Запросы ``POST /answers``.
        updates: События, которые вернёт следующий ``GET /updates``.
        unauthorized: Отвечать 401 на любой запрос.
        fail_updates: Имитировать обрыв сети при получении событий.
        send_error: Ошибка, которую выбрасывает ``POST /messages``.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.answers: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.unauthorized = False
        self.fail_updates = False
        self.send_error: Exception | None = None
        self.message_delay = 0.0

    def push_updates(self, *events: dict[str, Any]) -> None:
        """Положить события в следующий ответ ``GET /updates``."""
        self.updates = list(events)

    async def handle(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Ответить на запрос так, как это сделал бы MAX Bot API."""
        record = {
            "method": method,
            "path": path,
            "params": dict(params or {}),
            "json": json,
        }
        self.calls.append(record)

        if self.unauthorized:
            raise InvalidToken("Неверный токен!")

        if path.endswith("/me"):
            return dict(BOT_USER)

        if path.endswith("/updates"):
            if self.fail_updates:
                raise OSError("Нет сети")
            events, self.updates = self.updates, []
            if not events:
                # Настоящий GET /updates — long polling: запрос висит, пока
                # не появится событие. Небольшая пауза удерживает тесты
                # от холостого цикла.
                await asyncio.sleep(0.05)
            return {"updates": events, "marker": 1700000000002}

        if "/chats/" in path:
            # maxapi обогащает событие данными чата (GET /chats/{chat_id}).
            return dict(CHAT, chat_id=int(path.rsplit("/", 1)[-1]))

        if path.endswith("/messages"):
            self.messages.append(record)
            if self.send_error is not None:
                raise self.send_error
            if self.message_delay:
                await asyncio.sleep(self.message_delay)
            text = (json or {}).get("text", "")
            return {
                "message": {
                    "sender": dict(BOT_USER),
                    "recipient": {"chat_id": CHAT_ID, "chat_type": "dialog"},
                    "timestamp": 1700000000003,
                    "body": {"mid": "mid.sent", "seq": 2, "text": text},
                }
            }

        if path.endswith("/answers"):
            self.answers.append(record)
            if self.send_error is not None:
                raise self.send_error
            return {"success": True, "message": None}

        if path.endswith("/subscriptions"):
            return {"subscriptions": []}

        message = f"Заглушка не знает про запрос {record}"
        raise AssertionError(message)


def wait_for(condition: Callable[[], bool], *, timeout: float = 10.0) -> None:
    """Ждать выполнения условия (опрос с небольшими паузами)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    message = f"Условие не выполнено за {timeout} c"
    raise AssertionError(message)
