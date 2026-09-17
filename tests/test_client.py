"""Тесты асинхронного ядра: корректность запросов к MAX Bot API."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from maxapi import Bot as MaxApiBot
from maxapi.types.updates import UpdateUnionAdapter

from maxapilib import Button, MaxApiClient, TextBox
from maxapilib.exceptions import MaxApiLibAPIError

from .helpers import FakeTransport, message_created

TOKEN = "x" * 40


def make_client() -> MaxApiClient:
    """Клиент без сети: HTTP-слой подменяет фикстура transport."""
    return MaxApiClient(MaxApiBot(token=TOKEN))


def source_message() -> Any:
    """Сообщение из события ``message_created`` (как его видит maxapi)."""
    return UpdateUnionAdapter.validate_python(message_created("привет")).message


def test_bot_property() -> None:
    maxapi_bot = MaxApiBot(token=TOKEN)
    assert MaxApiClient(maxapi_bot).bot is maxapi_bot


def test_send_message_to_chat(transport: FakeTransport) -> None:
    asyncio.run(make_client().send_message(text="Привет", chat_id=100))

    request = transport.calls[-1]
    assert request["method"] == "POST"
    assert request["path"] == "/messages"
    assert request["params"] == {"chat_id": 100}
    assert request["json"]["text"] == "Привет"


def test_send_message_to_user(transport: FakeTransport) -> None:
    asyncio.run(make_client().send_message(text="Привет", user_id=42))

    assert transport.calls[-1]["params"] == {"user_id": 42}


def test_chat_id_wins_over_user_id(transport: FakeTransport) -> None:
    asyncio.run(make_client().send_message(text="Привет", chat_id=100, user_id=42))

    assert transport.calls[-1]["params"] == {"chat_id": 100}


def test_send_message_with_keyboard(transport: FakeTransport) -> None:
    """Клавиатура уходит в формате, который понимает MAX API."""
    box = TextBox("Меню")
    box.row(
        Button.callback("Кнопка", "go"), Button.link("Сайт", "https://example.com")
    )

    asyncio.run(
        make_client().send_message(
            text=box.text, chat_id=100, attachments=box.to_attachments()
        )
    )

    attachments = transport.calls[-1]["json"]["attachments"]
    assert attachments == [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "Кнопка",
                            "payload": "go",
                            "intent": "default",
                        },
                        {
                            "type": "link",
                            "text": "Сайт",
                            "url": "https://example.com",
                        },
                    ]
                ]
            },
        }
    ]


def test_send_message_with_reply_link(transport: FakeTransport) -> None:
    asyncio.run(
        make_client().send_message(text="Ответ", chat_id=100, reply_to="mid.1")
    )

    assert transport.calls[-1]["json"]["link"] == {"type": "reply", "mid": "mid.1"}


def test_send_message_options(transport: FakeTransport) -> None:
    asyncio.run(
        make_client().send_message(
            text="Привет",
            chat_id=100,
            notify=False,
            disable_link_preview=True,
        )
    )

    params = transport.calls[-1]["params"]
    assert params["disable_link_preview"] == "true"
    assert transport.calls[-1]["json"]["notify"] is False


def test_reply_uses_source_message(transport: FakeTransport) -> None:
    asyncio.run(make_client().reply(source_message(), text="Ответ"))

    request = transport.calls[-1]
    assert request["params"] == {"chat_id": 100}
    assert request["json"]["text"] == "Ответ"
    assert request["json"]["link"] == {"type": "reply", "mid": "mid.1"}


def test_reply_with_keyboard(transport: FakeTransport) -> None:
    box = TextBox("Меню").button("Кнопка", "go")

    asyncio.run(
        make_client().reply(
            source_message(), text=box.text, attachments=box.to_attachments()
        )
    )

    attachments = transport.calls[-1]["json"]["attachments"]
    assert attachments[0]["type"] == "inline_keyboard"


def test_reply_without_body_raises(transport: FakeTransport) -> None:
    message = source_message()
    message.body = None  # сообщение могло быть удалено к моменту ответа

    with pytest.raises(MaxApiLibAPIError, match="нет тела"):
        asyncio.run(make_client().reply(message, text="Ответ"))


def test_answer_callback_error_is_translated(transport: FakeTransport) -> None:
    from maxapi.exceptions.max import MaxApiError

    transport.send_error = MaxApiError(400, {"message": "callback не найден"})

    with pytest.raises(MaxApiLibAPIError, match="нажатие кнопки"):
        asyncio.run(make_client().answer_callback("cb-1", text="Готово"))


def test_answer_callback_with_text(transport: FakeTransport) -> None:
    asyncio.run(make_client().answer_callback("cb-1", text="Готово"))

    request = transport.calls[-1]
    assert request["method"] == "POST"
    assert request["path"] == "/answers"
    assert request["params"] == {"callback_id": "cb-1"}
    assert request["json"]["message"]["text"] == "Готово"


def test_answer_callback_notification_only(transport: FakeTransport) -> None:
    asyncio.run(
        make_client().answer_callback("cb-1", notification="Уведомление")
    )

    request = transport.calls[-1]
    assert request["json"] == {"notification": "Уведомление"}


def test_answer_callback_empty(transport: FakeTransport) -> None:
    asyncio.run(make_client().answer_callback("cb-1"))

    request = transport.calls[-1]
    assert request["params"] == {"callback_id": "cb-1"}
    assert request["json"] == {}
