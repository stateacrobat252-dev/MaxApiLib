"""MaxApiLib — простая библиотека для ботов в мессенджере MAX.

Библиотека прячет асинхронность ``maxapi``: обработчики — обычные функции,
отправка сообщений — обычные вызовы без ``async`` и ``await``.

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
from .logs import enable_logging
from .time_utils import (
    Timer,
    every,
    humanize_delay,
    later,
    now,
    parse_time,
    sleep,
)
from .types import Button, Callback, Message, Started, TextBox

__version__ = "1.0.0"

__all__ = [
    "Bot",
    "Button",
    "Callback",
    "MaxApiClient",
    "MaxApiLibAPIError",
    "MaxApiLibAuthError",
    "MaxApiLibError",
    "MaxApiLibNetworkError",
    "MaxApiLibTimeoutError",
    "Message",
    "Started",
    "TextBox",
    "Timer",
    "__version__",
    "as_format",
    "enable_logging",
    "every",
    "humanize_delay",
    "later",
    "now",
    "parse_time",
    "sleep",
]
