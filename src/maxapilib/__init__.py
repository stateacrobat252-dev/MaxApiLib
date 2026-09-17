"""MaxApiLib — простая библиотека для ботов в мессенджере MAX.

Библиотека прячет асинхронность ``maxapi``: обработчики — обычные функции,
отправка сообщений — обычные вызовы без ``async`` и ``await``.
Возможности: команды и кнопки, состояния (FSM), вебхуки, логи и счётчики
для мониторинга.

Пример::

    from maxapilib import Bot, Button, TextBox

    bot = Bot()  # токен из переменной окружения MAX_BOT_TOKEN

    @bot.on_command("start")
    def start(message):
        menu = TextBox("Выберите действие:")
        menu.add(Button.callback("Сайт", "site"))
        menu.add(Button.link("Правила", "https://example.com"))
        message.reply(menu)

    @bot.on_button("site")
    def site(callback):
        callback.answer("Открываю сайт")

    if __name__ == "__main__":
        bot.run()
"""

from __future__ import annotations

from .bot import Bot, as_format
from .client import MaxApiClient
from .exceptions import (
    MaxApiLibAPIError,
    MaxApiLibAuthError,
    MaxApiLibError,
    MaxApiLibNetworkError,
    MaxApiLibTimeoutError,
)
from .logs import close_log_files, enable_logging
from .monitoring import Monitor, Stats, describe_event
from .states import StateManager
from .time_utils import (
    Timer,
    every,
    humanize_delay,
    later,
    now,
    parse_time,
    sleep,
)
from .types import Button, Callback, Error, Message, Started, TextBox
from .webhook import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HEALTH_PATH,
    STATS_PATH,
    WebhookServer,
    generate_secret,
    webhook_path,
)

__version__ = "1.2.0"

__all__ = [
    "Bot",
    "Button",
    "Callback",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "Error",
    "HEALTH_PATH",
    "MaxApiClient",
    "MaxApiLibAPIError",
    "MaxApiLibAuthError",
    "MaxApiLibError",
    "MaxApiLibNetworkError",
    "MaxApiLibTimeoutError",
    "Message",
    "Monitor",
    "STATS_PATH",
    "Started",
    "Stats",
    "StateManager",
    "TextBox",
    "Timer",
    "WebhookServer",
    "__version__",
    "as_format",
    "close_log_files",
    "describe_event",
    "enable_logging",
    "every",
    "generate_secret",
    "humanize_delay",
    "later",
    "now",
    "parse_time",
    "sleep",
    "webhook_path",
]
