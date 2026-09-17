"""Работа бота через вебхук.

В режиме вебхука MAX сам присылает события боту по HTTPS — сервер
держит библиотека. Это рекомендуемый MAX способ для продакшена
(long polling годится для разработки).

Пользоваться этим напрямую не нужно: достаточно вызвать
``bot.run_webhook("https://ваш-сервер/путь")``.

Дополнительно сервер отвечает на два адреса для мониторинга:

* ``GET /health`` — жив ли бот;
* ``GET /stats`` — счётчики (то же, что ``bot.stats``).
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from .exceptions import MaxApiLibError

if TYPE_CHECKING:
    from maxapi import Bot as MaxApiBot
    from maxapi.dispatcher import Dispatcher

    from .monitoring import Stats

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "HEALTH_PATH",
    "STATS_PATH",
    "WebhookServer",
    "generate_secret",
    "webhook_path",
]

logger = logging.getLogger("maxapilib")

#: Хост и порт, на которых поднимается сервер вебхука.
DEFAULT_HOST = "0.0.0.0"  # сервер должен слушать все сетевые интерфейсы
DEFAULT_PORT = 8080

#: Служебные адреса для мониторинга.
HEALTH_PATH = "/health"
STATS_PATH = "/stats"

_SECRET_LENGTH = 32


def generate_secret() -> str:
    """Случайный секрет вебхука.

    MAX разрешает в секрете только ``A-Z``, ``a-z``, ``0-9`` и дефис,
    поэтому используется ``token_hex``.
    """
    return secrets.token_hex(_SECRET_LENGTH // 2)


def webhook_path(url: str) -> str:
    """Вытащить путь из URL вебхука (``https://host/hook`` → ``/hook``)."""
    path = urlparse(url).path
    return path or "/"


def _import_aiohttp() -> Any:
    """Импортировать aiohttp с понятной ошибкой (идёт вместе с maxapi)."""
    try:
        from aiohttp import web
    except ImportError as exc:  # pragma: no cover - aiohttp есть вместе с maxapi
        message = (
            "Для вебхуков нужен aiohttp: выполните pip install aiohttp "
            "(обычно он уже установлен вместе с maxapi)."
        )
        raise MaxApiLibError(message) from exc
    return web


class WebhookServer:
    """HTTP-сервер, принимающий события MAX.

    Attributes:
        bound_port: Порт, который сервер реально занял (важно, если
            указан ``port=0`` — тогда порт выбирает система).
    """

    def __init__(
        self,
        *,
        dispatcher: Dispatcher,
        bot: MaxApiBot,
        url: str,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        secret: str | None = None,
        stats: Stats | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._bot = bot
        self._url = url
        self._host = host
        self._port = port
        self._secret = secret
        self._stats = stats
        self._runner: Any = None
        self._site: Any = None
        self.bound_port: int = port

    @property
    def path(self) -> str:
        """Путь, на который MAX присылает события."""
        return webhook_path(self._url)

    async def start(self) -> None:
        """Поднять сервер.

        Raises:
            MaxApiLibError: Если порт занят или не удалось запустить сервер.
        """
        web = _import_aiohttp()
        from maxapi.webhook.aiohttp import AiohttpMaxWebhook

        hook = AiohttpMaxWebhook(
            dp=self._dispatcher, bot=self._bot, secret=self._secret
        )

        app = web.Application()
        app.on_startup.append(hook.on_startup)
        hook.setup(app, path=self.path)
        app.router.add_get(HEALTH_PATH, self._health)
        app.router.add_get(STATS_PATH, self._stats_handler)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner, host=self._host, port=self._port
        )

        try:
            await self._site.start()
        except OSError as exc:
            await self.stop()
            message = (
                f"Не удалось запустить сервер вебхука на "
                f"{self._host}:{self._port} ({exc}). "
                "Возможно, порт уже занят — укажите другой: "
                "bot.run_webhook(url, port=8081)."
            )
            raise MaxApiLibError(message) from exc

        self.bound_port = self._resolve_port()

    async def stop(self) -> None:
        """Остановить сервер (повторный вызов безопасен)."""
        runner, self._runner, self._site = self._runner, None, None
        if runner is not None:
            await runner.cleanup()

    def describe(self) -> str:
        """Строка для логов: куда слушает сервер и куда пишет MAX."""
        return (
            f"слушает http://{self._host}:{self.bound_port}{self.path}, "
            f"MAX присылает события на {self._url}"
        )

    def _resolve_port(self) -> int:
        """Узнать фактический порт сервера (нужно при ``port=0``)."""
        server = getattr(self._site, "_server", None)
        sockets = getattr(server, "sockets", None)
        if not sockets:
            return self._port
        return int(sockets[0].getsockname()[1])

    async def _health(self, request: Any) -> Any:
        """Ответ на ``GET /health``: бот работает."""
        web = _import_aiohttp()
        payload: dict[str, Any] = {"status": "ok"}
        if self._stats is not None:
            payload["bot"] = self._stats.as_dict()
        return web.json_response(payload)

    async def _stats_handler(self, request: Any) -> Any:
        """Ответ на ``GET /stats``: счётчики бота."""
        web = _import_aiohttp()
        if self._stats is None:  # pragma: no cover - защита от прямого вызова
            return web.json_response(
                {"status": "error", "message": "статистика недоступна"},
                status=500,
            )
        return web.json_response(self._stats.as_dict())
