"""Фильтры событий для диспетчера ``maxapi``.

Фильтры используются внутри декораторов :class:`maxapilib.Bot`
(``on_text``, ``on_command``, ``on_button``) и не требуют ручной настройки.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from maxapi.filters.filter import BaseFilter

from .types import text_of

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["CallbackPayload", "CommandFilter", "TextPattern"]


class TextPattern(BaseFilter):
    """Сообщение, текст которого подходит под регулярное выражение."""

    def __init__(self, pattern: str) -> None:
        """Скомпилировать регулярное выражение.

        Raises:
            ValueError: Если выражение некорректно.
        """
        try:
            self._regex = re.compile(pattern)
        except re.error as exc:
            message = f"Некорректное регулярное выражение {pattern!r}: {exc}"
            raise ValueError(message) from exc
        self.pattern = pattern

    async def __call__(self, event: Any) -> bool | dict[str, Any]:
        """Проверить текст сообщения."""
        text = text_of(getattr(event, "message", None))
        if not text:
            # Сообщение без текста (стикер, фото) не должно попадать
            # в текстовые обработчики.
            return False
        return self._regex.search(text) is not None

    def __repr__(self) -> str:
        return f"<TextPattern {self.pattern!r}>"


class CommandFilter(BaseFilter):
    """Команда вида ``/start``, в том числе с упоминанием бота ``/start@bot``."""

    def __init__(
        self,
        commands: Iterable[str],
        *,
        prefix: str = "/",
        case_sensitive: bool = False,
    ) -> None:
        """Запомнить список команд.

        Raises:
            ValueError: Если список команд пуст.
        """
        names = {command.removeprefix(prefix) for command in commands}
        names.discard("")
        if not names:
            message = "Укажите хотя бы одну команду, например on_command('start')"
            raise ValueError(message)

        self.prefix = prefix
        self.case_sensitive = case_sensitive
        self.commands = names if case_sensitive else {name.lower() for name in names}

    async def __call__(self, event: Any) -> bool | dict[str, Any]:
        """Проверить, что сообщение начинается с одной из команд."""
        text = text_of(getattr(event, "message", None))
        if not text:
            return False

        first = text.split(maxsplit=1)[0]
        if not first.startswith(self.prefix):
            return False

        name = first[len(self.prefix) :].split("@", 1)[0]
        if not self.case_sensitive:
            name = name.lower()
        return name in self.commands

    def __repr__(self) -> str:
        return f"<CommandFilter {sorted(self.commands)}>"


class CallbackPayload(BaseFilter):
    """Нажатие кнопки с указанным ``payload``."""

    def __init__(self, payload: str) -> None:
        self.payload = payload

    async def __call__(self, event: Any) -> bool | dict[str, Any]:
        """Сравнить payload нажатой кнопки с ожидаемым."""
        callback = getattr(event, "callback", None)
        return callback is not None and callback.payload == self.payload

    def __repr__(self) -> str:
        return f"<CallbackPayload {self.payload!r}>"
