"""Тесты логирования и счётчиков (мониторинг)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from maxapi.types.updates import UpdateUnionAdapter

from maxapilib import Bot, Error, Message, Stats, close_log_files
from maxapilib.monitoring import describe_event

from .helpers import (
    TOKEN,
    FakeTransport,
    bot_started,
    message_callback,
    message_created,
    wait_for,
)


def test_stats_after_events(transport: FakeTransport, bot: Bot) -> None:
    """Счётчики считают события, отправки и ответы на кнопки."""

    @bot.on_command("start")
    def start(message: Message) -> None:
        message.reply("ответ")

    @bot.on_button("go")
    def go(callback) -> None:  # так пишет новичок, без аннотаций
        callback.answer("ок")

    @bot.on_started()
    def hello(event) -> None:
        event.send("привет")

    transport.push_updates(
        message_created("/start"), message_callback("go"), bot_started()
    )
    bot.run(blocking=False)
    try:
        wait_for(lambda: len(transport.messages) >= 2 and bool(transport.answers))
    finally:
        bot.stop()

    stats = bot.stats
    assert isinstance(stats, Stats)
    assert stats.events == 3
    assert stats.messages == 1
    assert stats.callbacks == 1
    assert stats.started == 1
    assert stats.sent == 2  # ответ на команду и сообщение при запуске
    assert stats.answers == 1
    assert stats.errors == 0
    assert stats.last_error is None


def test_stats_dict_and_text(bot: Bot) -> None:
    """Счётчики удобно читать и глазами, и кодом."""
    data = bot.stats.as_dict()

    assert data["status"] == "stopped"
    assert data["events"] == 0
    assert data["last_error"] is None
    assert "остановлен" in str(bot.stats)


def test_stats_running_flag(transport: FakeTransport, bot: Bot) -> None:
    bot.run(blocking=False)
    try:
        assert bot.stats.running
        assert bot.stats.as_dict()["status"] == "running"
        assert "работает" in str(bot.stats)
    finally:
        bot.stop()

    assert not bot.stats.running


def test_events_are_logged(
    transport: FakeTransport, bot: Bot, caplog: pytest.LogCaptureFixture
) -> None:
    """Каждое событие попадает в лог, даже без подходящего обработчика."""
    transport.push_updates(message_created("привет"))

    with caplog.at_level(logging.INFO, logger="maxapilib"):
        bot.run(blocking=False)
        try:
            wait_for(
                lambda: any(
                    "сообщение от 42" in message for message in caplog.messages
                )
            )
        finally:
            bot.stop()


def test_send_is_logged(
    transport: FakeTransport, bot: Bot, caplog: pytest.LogCaptureFixture
) -> None:
    @bot.on_command("start")
    def start(message: Message) -> None:
        message.reply("приветик")
        bot.send("и второе сообщение")

    transport.push_updates(message_created("/start"))

    with caplog.at_level(logging.INFO, logger="maxapilib"):
        bot.run(blocking=False)
        try:
            wait_for(lambda: len(transport.messages) >= 2)
        finally:
            bot.stop()

    assert any("ответ в чат 100" in message for message in caplog.messages)
    assert any(
        "отправлено в чат 100" in message for message in caplog.messages
    )


def test_log_file(transport: FakeTransport, tmp_path: Path) -> None:
    """Логи можно писать в файл."""
    log_file = tmp_path / "bot.log"
    bot = Bot(TOKEN, log_file=log_file)

    transport.push_updates(message_created("привет"))
    bot.run(blocking=False)
    try:
        wait_for(
            lambda: log_file.exists()
            and "сообщение от 42" in log_file.read_text(encoding="utf-8")
        )
    finally:
        bot.stop()
        close_log_files()


def test_handler_error_is_logged_and_counted(
    transport: FakeTransport, bot: Bot, caplog: pytest.LogCaptureFixture
) -> None:
    @bot.on_command("boom")
    def boom(message: Message) -> None:
        raise ValueError("всё сломалось")

    transport.push_updates(message_created("/boom"))

    with caplog.at_level(logging.INFO, logger="maxapilib"):
        bot.run(blocking=False)
        try:
            wait_for(lambda: bot.stats.errors == 1)
        finally:
            bot.stop()

    assert bot.stats.last_error == "ValueError: всё сломалось"
    assert any("всё сломалось" in message for message in caplog.messages)


def test_on_error_handler(transport: FakeTransport, bot: Bot) -> None:
    """on_error получает удобный объект с ошибкой."""
    errors: list[Error] = []

    @bot.on_error()
    def catch(error: Error) -> None:
        errors.append(error)

    @bot.on_command("boom")
    def boom(message: Message) -> None:
        raise RuntimeError("упало")

    transport.push_updates(message_created("/boom"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(errors))
    finally:
        bot.stop()

    error = errors[0]
    assert error.text == "RuntimeError: упало"
    assert str(error) == "RuntimeError: упало"
    assert "RuntimeError" in error.traceback
    assert error.event is not None
    assert getattr(error.event, "text", None) == "/boom"
    assert error.bot is bot


def test_on_error_filters_by_exception_type(
    transport: FakeTransport, bot: Bot
) -> None:
    seen: list[Error] = []

    @bot.on_error(KeyError)
    def only_key_error(error: Error) -> None:
        seen.append(error)

    @bot.on_command("boom")
    def boom(message: Message) -> None:
        raise ValueError("не тот тип")

    transport.push_updates(message_created("/boom"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bot.stats.errors == 1)
    finally:
        bot.stop()

    assert seen == []


def test_admin_is_notified_about_error(transport: FakeTransport) -> None:
    """admin_id получает сообщение об ошибке."""
    bot = Bot(TOKEN, admin_id=777)

    @bot.on_command("boom")
    def boom(message: Message) -> None:
        raise RuntimeError("упало")

    transport.push_updates(message_created("/boom"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.messages))
    finally:
        bot.stop()

    sent = transport.messages[-1]
    assert sent["params"] == {"user_id": 777}
    assert "Ошибка в боте" in sent["json"]["text"]
    assert "RuntimeError: упало" in sent["json"]["text"]


def test_describe_event() -> None:
    assert "сообщение от 42 в чат 100: 'привет'" in describe_event(
        UpdateUnionAdapter.validate_python(message_created("привет"))
    )
    assert "нажатие кнопки 'go'" in describe_event(
        UpdateUnionAdapter.validate_python(message_callback("go"))
    )
    assert "запуск бота пользователем 42" in describe_event(
        UpdateUnionAdapter.validate_python(bot_started())
    )
