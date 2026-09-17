"""Тесты исключений MaxApiLib."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from maxapi.exceptions.max import InvalidToken, MaxApiError
from maxapi.types.updates import UpdateUnionAdapter

from maxapilib import Bot, MaxApiClient, TextBox
from maxapilib.bot import unpack_content
from maxapilib.client import is_api_error, translate_error
from maxapilib.exceptions import (
    MaxApiLibAPIError,
    MaxApiLibAuthError,
    MaxApiLibError,
    MaxApiLibNetworkError,
    MaxApiLibTimeoutError,
)

from .helpers import FakeTransport, message_created

TOKEN = "x" * 40


def make_client() -> MaxApiClient:
    """Асинхронный клиент без сети (запросы подменяет фикстура transport)."""
    from maxapi import Bot as MaxApiBot

    return MaxApiClient(MaxApiBot(token=TOKEN))


def test_error_hierarchy() -> None:
    assert issubclass(MaxApiLibAPIError, MaxApiLibError)
    assert issubclass(MaxApiLibAuthError, MaxApiLibAPIError)
    assert issubclass(MaxApiLibNetworkError, MaxApiLibAPIError)
    assert issubclass(MaxApiLibTimeoutError, MaxApiLibAPIError)


def test_error_message_and_details() -> None:
    error = MaxApiLibError("что-то сломалось")
    assert error.message == "что-то сломалось"
    assert error.details == {}
    assert str(error) == "что-то сломалось"

    detailed = MaxApiLibError("ошибка", details={"code": 500})
    assert detailed.details == {"code": 500}


def test_translate_invalid_token() -> None:
    error = translate_error(InvalidToken("нет"), "отправить сообщение")
    assert isinstance(error, MaxApiLibAuthError)
    assert "токен" in error.message
    assert error.details["action"] == "отправить сообщение"


def test_translate_network_error() -> None:
    error = translate_error(OSError("сеть недоступна"), "отправить сообщение")
    assert isinstance(error, MaxApiLibNetworkError)
    assert "нет связи" in error.message


def test_translate_api_error() -> None:
    error = translate_error(
        MaxApiError(500, {"message": "boom"}), "отправить сообщение"
    )
    assert isinstance(error, MaxApiLibAPIError)
    assert not isinstance(error, (MaxApiLibAuthError, MaxApiLibNetworkError))
    assert error.details["code"] == 500
    assert error.details["raw"] == {"message": "boom"}


def test_translate_unknown_error() -> None:
    error = translate_error(RuntimeError("что-то"), "отправить сообщение")
    assert isinstance(error, MaxApiLibAPIError)
    assert "RuntimeError" in error.message


def test_is_api_error() -> None:
    assert is_api_error(InvalidToken("нет"))
    assert is_api_error(OSError("нет сети"))
    assert not is_api_error(RuntimeError("что-то"))


def test_send_error_is_translated(transport: FakeTransport) -> None:
    """Ошибка API при отправке превращается в MaxApiLibAPIError."""
    transport.send_error = MaxApiError(500, {"message": "boom"})

    with pytest.raises(MaxApiLibAPIError) as info:
        asyncio.run(make_client().send_message(text="Привет", chat_id=100))

    assert "API MAX вернул ошибку 500" in str(info.value)


def test_unauthorized_is_translated(transport: FakeTransport) -> None:
    """401 превращается в MaxApiLibAuthError."""
    transport.unauthorized = True

    with pytest.raises(MaxApiLibAuthError):
        asyncio.run(make_client().send_message(text="Привет", chat_id=100))


def test_network_error_is_translated(transport: FakeTransport) -> None:
    """Обрыв сети превращается в MaxApiLibNetworkError."""
    transport.send_error = OSError("сеть недоступна")

    with pytest.raises(MaxApiLibNetworkError):
        asyncio.run(make_client().send_message(text="Привет", chat_id=100))


def test_bot_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)
    with pytest.raises(MaxApiLibAuthError, match="Не указан токен"):
        Bot()


def test_bot_validates_token() -> None:
    with pytest.raises(ValueError, match="Некорректный токен"):
        Bot("short")


def test_bot_takes_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_BOT_TOKEN", TOKEN)
    assert Bot().maxapi.headers["Authorization"] == TOKEN


def test_send_before_run_raises() -> None:
    bot = Bot(TOKEN)
    with pytest.raises(MaxApiLibError, match="Бот не запущен"):
        bot.send("Привет", chat_id=100)


def test_wait_without_run_raises() -> None:
    bot = Bot(TOKEN)
    with pytest.raises(MaxApiLibError, match="Бот не запущен"):
        bot.wait()


def test_send_requires_target() -> None:
    bot = Bot(TOKEN)
    with pytest.raises(MaxApiLibError, match="Не указан получатель"):
        bot.send("Привет")


def test_send_rejects_unknown_content() -> None:
    bot = Bot(TOKEN)
    with pytest.raises(MaxApiLibError, match="строкой или TextBox"):
        bot.send(123, chat_id=100)


def test_send_rejects_empty_text() -> None:
    bot = Bot(TOKEN)
    with pytest.raises(MaxApiLibError, match="не может быть пустым"):
        bot.send("   ", chat_id=100)


def test_reply_outside_run_raises() -> None:
    bot = Bot(TOKEN)
    update: Any = UpdateUnionAdapter.validate_python(message_created("привет"))
    with pytest.raises(MaxApiLibError, match="Бот не запущен"):
        bot.reply(update.message, "ответ")


def test_format_validation() -> None:
    with pytest.raises(ValueError, match="Неизвестный формат"):
        Bot(TOKEN, format="rtf")


def test_format_accepts_known_values() -> None:
    assert Bot(TOKEN, format="markdown").maxapi is not None
    assert Bot(TOKEN, format="html").maxapi is not None


def test_unpack_content_variants() -> None:
    text, attachments = unpack_content(TextBox("Меню").button("Кнопка", "go"), None)
    assert text == "Меню"
    assert attachments is not None
    assert len(attachments) == 1

    text, attachments = unpack_content("Просто текст", None)
    assert text == "Просто текст"
    assert attachments is None
