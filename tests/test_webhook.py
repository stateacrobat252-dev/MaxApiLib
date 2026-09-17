"""Тесты режима вебхука.

Сервер поднимается на localhost, события отправляются ему обычным
HTTP-запросом — интернет не нужен. MAX Bot API по-прежнему подменён
заглушкой.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from aiohttp import ClientSession

from maxapilib import Bot, MaxApiLibError, Message
from maxapilib.webhook import generate_secret, webhook_path

from .helpers import TOKEN, FakeTransport, message_created, wait_for

HOST = "127.0.0.1"
URL = "http://127.0.0.1/hook"
SECRET = "secret-for-tests"


async def parse(resp: Any) -> Any:
    """Разобрать ответ: ошибки отдаются обычным текстом, ответы — JSON."""
    text = await resp.text()
    try:
        return json.loads(text)
    except ValueError:
        return text


def post(
    url: str, payload: dict[str, Any], headers: dict[str, str] | None = None
) -> tuple[int, Any]:
    """Отправить событие на сервер вебхука."""

    async def request() -> tuple[int, Any]:
        async with (
            ClientSession() as session,
            session.post(url, json=payload, headers=headers) as resp,
        ):
            return resp.status, await parse(resp)

    return asyncio.run(request())


def get(url: str) -> tuple[int, Any]:
    """Запросить служебный адрес (health/stats)."""

    async def request() -> tuple[int, Any]:
        async with ClientSession() as session, session.get(url) as resp:
            return resp.status, await parse(resp)

    return asyncio.run(request())


def started_webhook(bot: Bot) -> int:
    """Запустить бота на вебхуке и вернуть занятый порт."""
    bot.run_webhook(URL, host=HOST, port=0, subscribe=False, blocking=False)
    wait_for(lambda: bot.webhook_port is not None)
    port = bot.webhook_port
    assert port is not None
    return port


def test_webhook_helpers() -> None:
    assert webhook_path("https://bot.example.com/hook") == "/hook"
    assert webhook_path("https://bot.example.com") == "/"

    secret = generate_secret()
    assert len(secret) >= 5
    assert all(char.isalnum() or char == "-" for char in secret)
    assert secret != generate_secret()


def test_webhook_receives_event(transport: FakeTransport) -> None:
    """Событие, присланное MAX на наш адрес, доходит до обработчика."""
    bot = Bot(TOKEN, auto_check_subscriptions=False)
    handled: list[str] = []

    @bot.on_command("start")
    def start(message: Message) -> None:
        handled.append(message.text)

    port = started_webhook(bot)
    try:
        status, body = post(
            f"http://{HOST}:{port}/hook", message_created("/start")
        )
        wait_for(lambda: bool(handled))
    finally:
        bot.stop()

    assert status == 200
    assert body == {"ok": True}
    assert handled == ["/start"]
    assert not bot.is_running


def test_webhook_secret(transport: FakeTransport) -> None:
    """С секретом запросы без правильного заголовка отклоняются."""
    bot = Bot(TOKEN, auto_check_subscriptions=False)

    @bot.on_command("start")
    def start(message: Message) -> None:
        pass

    bot.run_webhook(
        URL, host=HOST, port=0, secret=SECRET, subscribe=False, blocking=False
    )
    wait_for(lambda: bot.webhook_port is not None)
    port = bot.webhook_port
    assert port is not None
    try:
        status, _ = post(f"http://{HOST}:{port}/hook", message_created("/start"))
        assert status == 403

        status, _ = post(
            f"http://{HOST}:{port}/hook",
            message_created("/start"),
            headers={"X-Max-Bot-Api-Secret": SECRET},
        )
        assert status == 200
    finally:
        bot.stop()


def test_health_and_stats_endpoints(transport: FakeTransport) -> None:
    """Вебхук отдаёт /health и /stats для мониторинга."""
    bot = Bot(TOKEN, auto_check_subscriptions=False)

    @bot.on_command("start")
    def start(message: Message) -> None:
        message.reply("ок")

    port = started_webhook(bot)
    try:
        post(f"http://{HOST}:{port}/hook", message_created("/start"))
        wait_for(lambda: bool(transport.messages))

        status, health = get(f"http://{HOST}:{port}/health")
        assert status == 200
        assert health["status"] == "ok"
        assert health["bot"]["status"] == "running"

        status, stats = get(f"http://{HOST}:{port}/stats")
        assert status == 200
        assert stats["events"] == 1
        assert stats["messages"] == 1
        assert stats["sent"] == 1
    finally:
        bot.stop()


def test_webhook_subscribes_bot(transport: FakeTransport) -> None:
    """При запуске библиотека сама подписывает бота на вебхук."""
    bot = Bot(TOKEN, auto_check_subscriptions=False)

    bot.run_webhook(
        "https://bot.example.com/hook",
        host=HOST,
        port=0,
        subscribe=True,
        blocking=False,
    )
    try:
        wait_for(
            lambda: any(
                call["path"] == "/subscriptions" for call in transport.calls
            )
        )
    finally:
        bot.stop()

    subscribe = [
        call for call in transport.calls if call["path"] == "/subscriptions"
    ][-1]
    assert subscribe["method"] == "POST"
    assert subscribe["json"]["url"] == "https://bot.example.com/hook"
    assert subscribe["json"]["secret"]  # секрет придуман автоматически


def test_subscribe_failure_does_not_kill_server(
    transport: FakeTransport, caplog: pytest.LogCaptureFixture
) -> None:
    """Если подписка не удалась, сервер всё равно работает."""
    transport.subscribe_error = OSError("нет сети")
    bot = Bot(TOKEN, auto_check_subscriptions=False)
    handled: list[str] = []

    @bot.on_command("start")
    def start(message: Message) -> None:
        handled.append(message.text)

    bot.run_webhook(
        URL,
        host=HOST,
        port=0,
        secret=SECRET,
        subscribe=True,
        blocking=False,
    )
    wait_for(lambda: bot.webhook_port is not None)
    port = bot.webhook_port
    assert port is not None
    try:
        status, _ = post(
            f"http://{HOST}:{port}/hook",
            message_created("/start"),
            headers={"X-Max-Bot-Api-Secret": SECRET},
        )
        wait_for(lambda: bool(handled))
    finally:
        bot.stop()

    assert status == 200
    assert handled == ["/start"]
    assert any("Не удалось подписаться" in message for message in caplog.messages)


def test_busy_port_message(transport: FakeTransport) -> None:
    """Занятый порт даёт понятную ошибку."""
    first = Bot(TOKEN, auto_check_subscriptions=False)
    port = started_webhook(first)
    try:
        second = Bot(TOKEN, auto_check_subscriptions=False)
        with pytest.raises(MaxApiLibError, match="порт уже занят"):
            second.run_webhook(
                URL, host=HOST, port=port, subscribe=False, blocking=True
            )
    finally:
        first.stop()


def test_stop_closes_server(transport: FakeTransport) -> None:
    bot = Bot(TOKEN, auto_check_subscriptions=False)
    port = started_webhook(bot)

    bot.stop()

    assert not bot.is_running
    assert bot.webhook_port is None
    with pytest.raises(OSError):
        post(f"http://{HOST}:{port}/hook", message_created("/start"))


def test_delete_webhook_and_webhooks_list(transport: FakeTransport) -> None:
    """Подписки можно посмотреть и удалить (чтобы вернуться к поллингу)."""
    transport.subscriptions = [
        {"url": "https://old.example.com/hook", "time": 1700000000000}
    ]
    bot = Bot(TOKEN)

    assert bot.webhooks() == ["https://old.example.com/hook"]

    bot.delete_webhook()
    assert any(call["method"] == "DELETE" for call in transport.calls)
