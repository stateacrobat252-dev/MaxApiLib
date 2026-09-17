"""Состояния (FSM) и данные пользователя.

Библиотека хранит для каждой пары «чат + пользователь»:

* **состояние** — короткая строка, например ``"waiting_name"``;
* **данные** — любые значения, например ``{"name": "Иван"}``.

Пример анкеты::

    @bot.on_command("start")
    def start(message):
        bot.set_state(message, "waiting_name")     # запомнили состояние
        message.reply("Как вас зовут?")

    @bot.on_state("waiting_name")                  # сработает в этом состоянии
    def get_name(message):
        bot.set_data(message, name=message.text)   # сохранили ответ
        bot.reset_state(message)                   # вышли из анкеты
        message.reply(f"Привет, {bot.get_data(message, 'name')}!")

Хранение по умолчанию — в оперативной памяти (данные теряются при
перезапуске). Для продакшена можно передать ``Bot(storage=RedisContext)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .exceptions import MaxApiLibError

if TYPE_CHECKING:
    from maxapi.context import ContextManager

    from .types import Callback, Message, Started

__all__ = ["StateManager"]

#: Событие бота, из которого берутся chat_id и user_id.
EventTarget = "Message | Callback | Started"

_MISSING_TARGET = (
    "Не понятно, для кого менять состояние: передайте событие "
    "(например message) или укажите chat_id."
)


class StateManager:
    """Асинхронная работа с состояниями поверх ``maxapi``.

    Обычно вызывается через методы :class:`maxapilib.Bot`:
    ``bot.set_state``, ``bot.get_state``, ``bot.set_data``,
    ``bot.get_data``, ``bot.reset_state``.
    """

    def __init__(self, fsm: ContextManager) -> None:
        self._fsm = fsm

    async def set_state(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        state: str | None,
    ) -> None:
        """Запомнить состояние (``None`` — сбросить)."""
        await self._fsm.set_state(
            chat_id=chat_id, user_id=user_id, state=state
        )

    async def get_state(
        self, *, chat_id: int | None, user_id: int | None
    ) -> str | None:
        """Текущее состояние или ``None``."""
        state = await self._fsm.get_state(chat_id=chat_id, user_id=user_id)
        return str(state) if state is not None else None

    async def set_data(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        **values: Any,
    ) -> dict[str, Any]:
        """Дописать значения в данные пользователя и вернуть их."""
        if not values:
            return await self._fsm.get_data(chat_id=chat_id, user_id=user_id)
        return await self._fsm.update_data(
            chat_id=chat_id, user_id=user_id, **values
        )

    async def get_data(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        key: str | None = None,
    ) -> Any:
        """Данные пользователя: словарь или одно значение по ключу."""
        data = await self._fsm.get_data(chat_id=chat_id, user_id=user_id)
        if key is None:
            return data
        return data.get(key)

    async def reset(
        self, *, chat_id: int | None, user_id: int | None
    ) -> None:
        """Сбросить и состояние, и данные пользователя."""
        await self._fsm.clear(chat_id=chat_id, user_id=user_id)


def target_ids(
    event: Message | Callback | Started | None,
    *,
    chat_id: int | None = None,
    user_id: int | None = None,
    required: bool = True,
) -> tuple[int | None, int | None]:
    """Определить, к какому чату и пользователю относится действие.

    Args:
        event: Событие из обработчика.
        chat_id: ID чата, если событие не передано.
        user_id: ID пользователя, если событие не передано.
        required: Требовать ли хотя бы один идентификатор.

    Raises:
        MaxApiLibError: Если идентификаторы не удалось определить.
    """
    if event is not None:
        return event.chat_id, event.user_id

    if required and chat_id is None and user_id is None:
        raise MaxApiLibError(_MISSING_TARGET)

    return chat_id, user_id
