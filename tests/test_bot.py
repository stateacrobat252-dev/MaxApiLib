"""Сквозные тесты: бот получает события MAX и отвечает (сеть подменена).

Проверяется вся цепочка целиком: поллинг ``maxapi`` → фильтры →
пользовательский обработчик в отдельном потоке → синхронная отправка
сообщения → HTTP-запрос к MAX Bot API.
"""

from __future__ import annotations

import logging
import time

import pytest

import maxapilib
from maxapilib import (
    Bot,
    Button,
    Callback,
    MaxApiLibError,
    Message,
    Started,
    TextBox,
)
from maxapilib.exceptions import MaxApiLibAuthError, MaxApiLibTimeoutError
from maxapilib.logs import resolve_level

from .helpers import (
    CHAT_ID,
    FakeTransport,
    bot_started,
    message_callback,
    message_created,
    wait_for,
)

TOKEN = "x" * 40


def test_command_handler_replies(transport: FakeTransport, bot: Bot) -> None:
    seen: list[tuple[str | None, list[str], bool]] = []

    @bot.on_command("start")
    def start(message: Message) -> None:
        seen.append((message.command, message.args, bot.current is message))
        message.reply("Привет!")

    transport.push_updates(message_created("/start"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.messages))
    finally:
        bot.stop()

    assert seen == [("start", [], True)]
    sent = transport.messages[-1]
    assert sent["params"] == {"chat_id": CHAT_ID}
    assert sent["json"]["text"] == "Привет!"
    assert sent["json"]["link"] == {"type": "reply", "mid": "mid.1"}
    assert bot.current is None
    assert not bot.is_running


def test_command_arguments_and_mention(transport: FakeTransport, bot: Bot) -> None:
    seen: list[list[str]] = []

    @bot.on_command("echo")
    def echo(message: Message) -> None:
        seen.append(message.args)

    transport.push_updates(message_created("/echo@maxapilib_bot привет мир"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(seen))
    finally:
        bot.stop()

    assert seen == [["привет", "мир"]]


def test_button_handler_answers_callback(
    transport: FakeTransport, bot: Bot
) -> None:
    pressed: list[str | None] = []

    @bot.on_button("go")
    def press(callback: Callback) -> None:
        pressed.append(callback.payload)
        callback.answer("Готово", notification="Кнопка нажата")

    transport.push_updates(message_callback("go", callback_id="cb-42"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.answers))
    finally:
        bot.stop()

    assert pressed == ["go"]
    answer = transport.answers[-1]
    assert answer["params"] == {"callback_id": "cb-42"}
    assert answer["json"]["message"]["text"] == "Готово"
    assert answer["json"]["notification"] == "Кнопка нажата"


def test_callback_catch_all(transport: FakeTransport, bot: Bot) -> None:
    pressed: list[str | None] = []

    @bot.on_callback()
    def any_button(callback: Callback) -> None:
        pressed.append(callback.payload)

    transport.push_updates(message_callback("любой_payload"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(pressed))
    finally:
        bot.stop()

    assert pressed == ["любой_payload"]


def test_text_handler_sends_keyboard(transport: FakeTransport, bot: Bot) -> None:
    @bot.on_text(r"меню")
    def menu(message: Message) -> None:
        box = TextBox("Меню:")
        box.row(
            Button.callback("Кнопка", "go"),
            Button.link("Сайт", "https://example.com"),
        )
        message.send(box)

    transport.push_updates(message_created("покажи меню"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.messages))
    finally:
        bot.stop()

    sent = transport.messages[-1]["json"]
    assert sent["text"] == "Меню:"
    assert "link" not in sent  # это отправка, а не ответ
    assert sent["attachments"] == [
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


def test_send_without_target_uses_current_chat(
    transport: FakeTransport, bot: Bot
) -> None:
    @bot.on_message()
    def echo(message: Message) -> None:
        bot.send("эхо: " + message.text)

    transport.push_updates(message_created("привет"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.messages))
    finally:
        bot.stop()

    sent = transport.messages[-1]
    assert sent["params"] == {"chat_id": CHAT_ID}
    assert sent["json"]["text"] == "эхо: привет"


def test_on_message_fallback(transport: FakeTransport, bot: Bot) -> None:
    handled: list[str] = []

    @bot.on_message()
    def catch_all(message: Message) -> None:
        handled.append(message.text)

    transport.push_updates(message_created("раз"), message_created("два"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: len(handled) == 2)
    finally:
        bot.stop()

    assert handled == ["раз", "два"]


def test_first_registered_handler_wins(transport: FakeTransport, bot: Bot) -> None:
    order: list[str] = []

    @bot.on_message()
    def first(message: Message) -> None:
        order.append("первый")

    @bot.on_command("start")
    def second(message: Message) -> None:
        order.append("второй")

    transport.push_updates(message_created("/start"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(order))
    finally:
        bot.stop()

    assert order == ["первый"]


def test_started_handler(transport: FakeTransport, bot: Bot) -> None:
    started: list[Started] = []

    @bot.on_started()
    def on_start(event: Started) -> None:
        started.append(event)
        event.send("Здравствуйте!")

    transport.push_updates(bot_started(payload="promo"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.messages))
    finally:
        bot.stop()

    assert len(started) == 1
    assert started[0].payload == "promo"
    assert transport.messages[-1]["params"] == {"chat_id": CHAT_ID}


def test_handler_error_does_not_stop_bot(
    transport: FakeTransport, bot: Bot
) -> None:
    handled: list[str] = []

    @bot.on_command("boom")
    def boom(message: Message) -> None:
        raise RuntimeError(f"Ошибка в обработчике: {message.text}")

    @bot.on_command("ok")
    def ok(message: Message) -> None:
        handled.append(message.command or "")

    transport.push_updates(message_created("/boom"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.calls))
        transport.push_updates(message_created("/ok"))
        wait_for(lambda: bool(handled))
    finally:
        bot.stop()

    assert handled == ["ok"]


def test_handlers_cannot_be_added_after_start(
    transport: FakeTransport, bot: Bot
) -> None:
    bot.run(blocking=False)
    try:
        with pytest.raises(MaxApiLibError, match="после запуска бота"):
            bot.on_text("что-нибудь")
        with pytest.raises(MaxApiLibError, match="уже запущен"):
            bot.run()
    finally:
        bot.stop()


def test_run_after_stop_works(transport: FakeTransport, bot: Bot) -> None:
    bot.run(blocking=False)
    bot.stop()
    assert not bot.is_running

    bot.run(blocking=False)
    try:
        assert bot.is_running
    finally:
        bot.stop()


def test_send_after_stop_works(transport: FakeTransport, bot: Bot) -> None:
    bot.run(blocking=False)
    bot.stop()

    # Разовое уведомление работает и без запущенного бота.
    bot.send("Привет", chat_id=CHAT_ID)
    assert transport.messages[-1]["json"]["text"] == "Привет"


def test_invalid_token_stops_run(transport: FakeTransport) -> None:
    transport.unauthorized = True
    bot = Bot(TOKEN)

    with pytest.raises(MaxApiLibAuthError, match="токен"):
        bot.run()


def test_stop_is_idempotent(transport: FakeTransport, bot: Bot) -> None:
    bot.run(blocking=False)
    bot.stop()
    bot.stop()
    assert not bot.is_running


def test_skip_updates_option(transport: FakeTransport) -> None:
    bot = Bot(TOKEN, skip_updates=True)
    handled: list[str] = []

    @bot.on_message()
    def catch_all(message: Message) -> None:
        handled.append(message.text)

    # Событие «из прошлого»: его timestamp меньше времени запуска бота.
    transport.push_updates(message_created("старое"))
    bot.run(blocking=False)
    try:
        fresh = message_created("новое", mid="mid.2")
        fresh["timestamp"] = int(time.time() * 1000) + 60_000
        transport.push_updates(fresh)
        wait_for(lambda: bool(handled))
    finally:
        bot.stop()

    assert handled == ["новое"]


def test_async_handler_is_rejected(transport: FakeTransport, bot: Bot) -> None:
    with pytest.raises(MaxApiLibError, match="async def"):

        @bot.on_command("start")
        async def start(message: Message) -> None:
            print(message)


def test_call_timeout(transport: FakeTransport) -> None:
    bot = Bot(TOKEN, call_timeout=0.05)
    transport.message_delay = 0.5

    @bot.on_command("start")
    def start(message: Message) -> None:
        message.send("медленно")

    transport.push_updates(message_created("/start"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.messages))
        with pytest.raises(MaxApiLibTimeoutError):
            bot.send("Привет", chat_id=CHAT_ID)
    finally:
        bot.stop()


def test_enable_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    maxapilib.enable_logging("WARNING")
    assert logging.getLogger("maxapilib").level == logging.WARNING
    assert logging.getLogger("maxapi").level == logging.WARNING


def test_resolve_level() -> None:
    assert resolve_level("info") == logging.INFO
    assert resolve_level(10) == 10
    with pytest.raises(ValueError, match="Неизвестный уровень"):
        resolve_level("супер-подробный")


def test_bot_with_log_level(transport: FakeTransport) -> None:
    bot = Bot(TOKEN, log_level="ERROR", auto_check_subscriptions=False)
    assert bot.maxapi is not None
