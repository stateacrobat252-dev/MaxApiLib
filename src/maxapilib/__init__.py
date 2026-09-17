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
from .monitoring import Stats
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

__version__ = "1.1.0"

__all__ = [
    "Bot",
    "Button",
    "Callback",
    "Error",
    "MaxApiClient",
    "MaxApiLibAPIError",
    "MaxApiLibAuthError",
    "MaxApiLibError",
    "MaxApiLibNetworkError",
    "MaxApiLibTimeoutError",
    "Message",
    "Started",
    "Stats",
    "TextBox",
    "Timer",
    "__version__",
    "as_format",
    "close_log_files",
    "enable_logging",
    "every",
    "humanize_delay",
    "later",
    "now",
    "parse_time",
    "sleep",
]
