"""Простые типы MaxApiLib: кнопки, клавиатуры и события бота.

Кнопки и клавиатуры собираются синхронно и превращаются в модели
библиотеки ``maxapi`` (а значит — в корректный JSON для MAX API)::

    from maxapilib import Bot, Button, TextBox

    menu = TextBox("Выберите действие:")
    menu.row(Button.callback("Сайт", "site"), Button.link("Правила", "https://example.com"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from maxapi.enums.attachment import AttachmentType
from maxapi.enums.intent import Intent
from maxapi.types.attachments.attachment import Attachment
from maxapi.types.message import Message as MaxApiMessage
from maxapi.types.updates.bot_started import BotStarted as MaxApiBotStarted
from maxapi.types.updates.message_callback import (
    MessageCallback as MaxApiMessageCallback,
)
from maxapi.types.updates.message_created import (
    MessageCreated as MaxApiMessageCreated,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .bot import Bot

__all__ = [
    "Button",
    "Callback",
    "Message",
    "Started",
    "TextBox",
]

#: Текст сообщения MAX API: до 4000 символов.
MAX_TEXT_LENGTH = 4000
#: Текст на кнопке: от 1 до 64 символов.
MAX_BUTTON_TEXT_LENGTH = 64
#: Длина callback-payload: до 256 символов.
MAX_PAYLOAD_LENGTH = 256
#: Длина ссылки в кнопке: до 2048 символов.
MAX_URL_LENGTH = 2048
#: Ограничения клавиатуры MAX: до 30 рядов и до 210 кнопок.
MAX_KEYBOARD_ROWS = 30
MAX_KEYBOARD_BUTTONS = 210
#: До 7 обычных кнопок в ряду и до 3 «широких» (ссылки и запросы).
MAX_BUTTONS_PER_ROW = 7
MAX_NARROW_BUTTONS_PER_ROW = 3
_NARROW_BUTTON_TYPES = frozenset(
    {"link", "open_app", "request_contact", "request_geo_location"}
)

def _check_text(text: str, *, what: str = "Текст кнопки") -> str:
    """Проверить и нормализовать текст."""
    value = text.strip()
    if not value:
        message = f"{what} не может быть пустым"
        raise ValueError(message)
    if len(value) > MAX_BUTTON_TEXT_LENGTH:
        message = (
            f"{what} не может быть длиннее {MAX_BUTTON_TEXT_LENGTH} символов, "
            f"получено {len(value)}"
        )
        raise ValueError(message)
    return value


def _check_length(value: str, limit: int, *, what: str) -> str:
    """Проверить длину значения."""
    if len(value) > limit:
        message = (
            f"{what} не может быть длиннее {limit} символов, "
            f"получено {len(value)}"
        )
        raise ValueError(message)
    return value


class Button:
    """Кнопка inline-клавиатуры.

    Кнопки создаются фабриками:

    * :meth:`callback` — обычная кнопка, бот получает событие с ``payload``;
    * :meth:`link` — ссылка;
    * :meth:`message` — отправляет боту заранее заданный текст;
    * :meth:`clipboard` — копирует текст в буфер обмена;
    * :meth:`contact` — запрашивает у пользователя контакт;
    * :meth:`location` — запрашивает геолокацию;
    * :meth:`open_app` — открывает мини-приложение.

    Attributes:
        text: Подпись на кнопке.
        type: Тип кнопки (``"callback"``, ``"link"`` и т.д.).
    """

    __slots__ = ("_payload",)

    def __init__(self, *, payload: dict[str, Any]) -> None:
        self._payload = payload

    @classmethod
    def callback(
        cls, text: str, payload: str, *, intent: Intent | None = None
    ) -> Button:
        """Кнопка, по нажатию которой приходит событие с ``payload``.

        Args:
            text: Подпись на кнопке.
            payload: Данные кнопки (до 256 символов).
            intent: Визуальный стиль: ``Intent.DEFAULT``, ``POSITIVE``
                или ``NEGATIVE``.
        """
        data: dict[str, Any] = {
            "type": "callback",
            "text": _check_text(text),
            "payload": _check_length(payload, MAX_PAYLOAD_LENGTH, what="payload"),
        }
        if intent is not None:
            data["intent"] = str(intent)
        return cls(payload=data)

    @classmethod
    def link(cls, text: str, url: str) -> Button:
        """Кнопка-ссылка. Открывает ``url`` в новой вкладке.

        Raises:
            ValueError: Если ссылка не начинается с ``http://`` или ``https://``.
        """
        if not url.startswith(("http://", "https://")):
            message = (
                f"Некорректная ссылка {url!r}: она должна начинаться "
                "с http:// или https://"
            )
            raise ValueError(message)
        return cls(
            payload={
                "type": "link",
                "text": _check_text(text),
                "url": _check_length(url, MAX_URL_LENGTH, what="Ссылка"),
            }
        )

    @classmethod
    def message(cls, text: str) -> Button:
        """Кнопка, отправляющая боту текст, указанный на ней."""
        return cls(payload={"type": "message", "text": _check_text(text)})

    @classmethod
    def clipboard(cls, text: str, payload: str) -> Button:
        """Кнопка, копирующая ``payload`` в буфер обмена пользователя."""
        return cls(
            payload={
                "type": "clipboard",
                "text": _check_text(text),
                "payload": _check_length(payload, MAX_PAYLOAD_LENGTH, what="payload"),
            }
        )

    @classmethod
    def contact(cls, text: str = "Отправить контакт") -> Button:
        """Кнопка запроса контакта пользователя."""
        return cls(payload={"type": "request_contact", "text": _check_text(text)})

    @classmethod
    def location(
        cls, text: str = "Отправить геолокацию", *, quick: bool = False
    ) -> Button:
        """Кнопка запроса геолокации.

        Args:
            quick: ``True`` — запросить геолокацию без подтверждения.
        """
        return cls(
            payload={
                "type": "request_geo_location",
                "text": _check_text(text),
                "quick": quick,
            }
        )

    @classmethod
    def open_app(
        cls,
        text: str,
        *,
        web_app: str | None = None,
        contact_id: int | None = None,
        payload: str | None = None,
    ) -> Button:
        """Кнопка запуска мини-приложения бота.

        Args:
            text: Подпись на кнопке.
            web_app: Username бота, чьё мини-приложение открывается.
            contact_id: ID бота, чьё мини-приложение открывается.
            payload: Параметр запуска мини-приложения.

        Raises:
            ValueError: Если не указан ни ``web_app``, ни ``contact_id``.
        """
        if web_app is None and contact_id is None:
            message = "Для кнопки open_app укажите web_app или contact_id"
            raise ValueError(message)

        data: dict[str, Any] = {"type": "open_app", "text": _check_text(text)}
        if web_app is not None:
            data["web_app"] = web_app
        if contact_id is not None:
            data["contact_id"] = contact_id
        if payload is not None:
            data["payload"] = _check_length(
                payload, MAX_PAYLOAD_LENGTH, what="payload"
            )
        return cls(payload=data)

    @property
    def text(self) -> str:
        """Подпись на кнопке."""
        return str(self._payload["text"])

    @property
    def type(self) -> str:
        """Тип кнопки."""
        return str(self._payload["type"])

    @property
    def payload(self) -> str | None:
        """Данные кнопки (для callback- и clipboard-кнопок)."""
        value = self._payload.get("payload")
        return value if isinstance(value, str) else None

    @property
    def url(self) -> str | None:
        """Ссылка кнопки (только для кнопок типа ``link``)."""
        value = self._payload.get("url")
        return value if isinstance(value, str) else None

    @property
    def is_narrow(self) -> bool:
        """``True`` для «широких» кнопок: в ряду их помещается только 3."""
        return self.type in _NARROW_BUTTON_TYPES

    def to_dict(self) -> dict[str, Any]:
        """Кнопка в формате MAX API (то, что уходит на сервер)."""
        return dict(self._payload)

    def __repr__(self) -> str:
        return f"<Button {self.type} {self.text!r}>"


class TextBox:
    """Сообщение с текстом и inline-клавиатурой.

    Пример::

        menu = TextBox("Выберите действие:")
        menu.row(Button.callback("Сайт", "site"))
        menu.add(Button.link("Правила", "https://example.com"))
        bot.send(menu)

    Attributes:
        text: Текст сообщения.
        rows: Ряды кнопок.
    """

    def __init__(self, text: str) -> None:
        """Создать сообщение.

        Raises:
            ValueError: Если текст пустой или длиннее 4000 символов.
        """
        if not text.strip():
            message = "Текст сообщения не может быть пустым"
            raise ValueError(message)
        if len(text) > MAX_TEXT_LENGTH:
            message = (
                f"Текст сообщения не может быть длиннее {MAX_TEXT_LENGTH} "
                f"символов, получено {len(text)}"
            )
            raise ValueError(message)

        self.text = text
        self.rows: list[list[Button]] = []

    @property
    def buttons_count(self) -> int:
        """Сколько всего кнопок в сообщении."""
        return sum(len(row) for row in self.rows)

    def row(self, *buttons: Button) -> TextBox:
        """Добавить новый ряд кнопок.

        Raises:
            ValueError: Если превышены ограничения клавиатуры MAX.
        """
        if not buttons:
            message = "Ряд не может быть пустым"
            raise ValueError(message)
        if len(self.rows) >= MAX_KEYBOARD_ROWS:
            message = (
                f"В одной клавиатуре MAX может быть не более "
                f"{MAX_KEYBOARD_ROWS} рядов"
            )
            raise ValueError(message)

        capacity = (
            MAX_NARROW_BUTTONS_PER_ROW
            if any(button.is_narrow for button in buttons)
            else MAX_BUTTONS_PER_ROW
        )
        if len(buttons) > capacity:
            message = (
                f"В ряду может быть не более {capacity} таких кнопок "
                f"(передано {len(buttons)})"
            )
            raise ValueError(message)

        self._check_total(self.buttons_count + len(buttons))
        self.rows.append(list(buttons))
        return self

    def add(self, button: Button) -> TextBox:
        """Добавить кнопку в последний подходящий ряд.

        Кнопка встаёт в первый ряд, где есть место: до 7 обычных кнопок
        или до 3 «широких» (ссылки, запросы контакта и геолокации).
        Если места нет ни в одном ряду, создаётся новый.
        """
        for row in self.rows:
            capacity = (
                MAX_NARROW_BUTTONS_PER_ROW
                if button.is_narrow or any(item.is_narrow for item in row)
                else MAX_BUTTONS_PER_ROW
            )
            if len(row) < capacity:
                self._check_total(self.buttons_count + 1)
                row.append(button)
                return self

        self._check_total(self.buttons_count + 1)
        if len(self.rows) >= MAX_KEYBOARD_ROWS:
            message = (
                f"В одной клавиатуре MAX может быть не более "
                f"{MAX_KEYBOARD_ROWS} рядов"
            )
            raise ValueError(message)
        self.rows.append([button])
        return self

    def _check_total(self, total: int) -> None:
        """Проверить общее количество кнопок в клавиатуре.

        Raises:
            ValueError: Если кнопок больше, чем разрешает MAX.
        """
        if total > MAX_KEYBOARD_BUTTONS:
            message = (
                f"В одной клавиатуре MAX может быть не более "
                f"{MAX_KEYBOARD_BUTTONS} кнопок"
            )
            raise ValueError(message)

    def button(
        self, text: str, payload: str, *, intent: Intent | None = None
    ) -> TextBox:
        """Добавить callback-кнопку."""
        return self.add(Button.callback(text, payload, intent=intent))

    def to_attachments(self) -> list[Attachment] | None:
        """Клавиатура как вложения MAX API.

        Returns:
            Список вложений для ``attachments`` или ``None``,
            если кнопок нет.
        """
        if not self.rows:
            return None

        buttons = [[button.to_dict() for button in row] for row in self.rows]
        return [
            Attachment.model_validate(
                {
                    "type": str(AttachmentType.INLINE_KEYBOARD),
                    "payload": {"buttons": buttons},
                }
            )
        ]

    def to_dict(self) -> dict[str, Any]:
        """Тело сообщения в формате MAX API."""
        body: dict[str, Any] = {"text": self.text}
        attachments = self.to_attachments()
        if attachments is not None:
            body["attachments"] = [
                item.model_dump(mode="json", exclude_none=True)
                for item in attachments
            ]
        return body

    def __repr__(self) -> str:
        return f"<TextBox {self.text!r} rows={len(self.rows)}>"


@dataclass(slots=True)
class Message:
    """Входящее сообщение (то, что приходит в обработчики).

    Attributes:
        text: Текст сообщения (пустая строка, если текста нет).
        chat_id: ID чата, откуда пришло сообщение.
        user_id: ID отправителя.
        message_id: Идентификатор сообщения в MAX.
        raw: Исходный объект ``maxapi`` — доступ ко всем полям API
            (вложения, разметка, цитаты и т.д.).
        bot: Бот, которому пришло сообщение.
    """

    text: str
    chat_id: int | None
    user_id: int | None
    message_id: str | None
    raw: MaxApiMessage
    bot: Bot = field(repr=False)

    @property
    def command(self) -> str | None:
        """Команда без префикса, если сообщение начинается с ``/``."""
        first = self.text.split(maxsplit=1)[0] if self.text.split() else ""
        if not first.startswith("/"):
            return None
        name = first[1:].split("@", 1)[0]
        return name.lower() or None

    @property
    def args(self) -> list[str]:
        """Аргументы команды: слова после команды, если текст с ``/``."""
        if self.command is None:
            return []
        return self.text.split()[1:]

    def reply(
        self,
        content: str | TextBox,
        *,
        attachments: Sequence[Attachment] | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        format: str | None = None,
    ) -> None:
        """Ответить на сообщение (с цитированием)."""
        self.bot.reply(
            self,
            content,
            attachments=attachments,
            notify=notify,
            disable_link_preview=disable_link_preview,
            format=format,
        )

    def send(
        self,
        content: str | TextBox,
        *,
        attachments: Sequence[Attachment] | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        format: str | None = None,
    ) -> None:
        """Отправить сообщение в тот же чат (без цитирования)."""
        self.bot.send(
            content,
            chat_id=self.chat_id,
            user_id=self.user_id if self.chat_id is None else None,
            attachments=attachments,
            notify=notify,
            disable_link_preview=disable_link_preview,
            format=format,
        )


@dataclass(slots=True)
class Callback:
    """Нажатие inline-кнопки.

    Attributes:
        payload: Данные кнопки, на которую нажали.
        callback_id: Идентификатор нажатия (нужен для :meth:`answer`).
        chat_id: ID чата.
        user_id: ID пользователя, нажавшего кнопку.
        message: Сообщение с клавиатурой (``None``, если оно удалено).
        raw: Исходный объект ``maxapi``.
        bot: Бот, которому пришло событие.
    """

    payload: str | None
    callback_id: str
    chat_id: int | None
    user_id: int | None
    message: Message | None
    raw: MaxApiMessageCallback
    bot: Bot = field(repr=False)

    def answer(
        self,
        text: str | None = None,
        *,
        attachments: Sequence[Attachment] | None = None,
        notification: str | None = None,
    ) -> None:
        """Ответить на нажатие кнопки.

        MAX Bot API ждёт ответ на каждое нажатие: ``text`` меняет текущее
        сообщение, ``notification`` показывает всплывающее уведомление.

        Args:
            text: Новый текст сообщения с клавиатурой.
            attachments: Новые вложения сообщения.
            notification: Текст всплывающего уведомления.
        """
        self.bot.answer_callback(
            self.callback_id,
            text=text,
            attachments=attachments,
            notification=notification,
        )

    def send(
        self,
        content: str | TextBox,
        *,
        attachments: Sequence[Attachment] | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        format: str | None = None,
    ) -> None:
        """Отправить новое сообщение в чат, где нажали кнопку."""
        self.bot.send(
            content,
            chat_id=self.chat_id,
            user_id=self.user_id if self.chat_id is None else None,
            attachments=attachments,
            notify=notify,
            disable_link_preview=disable_link_preview,
            format=format,
        )


@dataclass(slots=True)
class Started:
    """Событие запуска бота: пользователь нажал «Начать».

    Attributes:
        chat_id: ID чата, где запустили бота.
        user_id: ID пользователя.
        payload: Данные диплинка (если бота запустили по ссылке).
        raw: Исходный объект ``maxapi``.
        bot: Бот, которому пришло событие.
    """

    chat_id: int
    user_id: int
    payload: str | None
    raw: MaxApiBotStarted
    bot: Bot = field(repr=False)

    def send(
        self,
        content: str | TextBox,
        *,
        attachments: Sequence[Attachment] | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        format: str | None = None,
    ) -> None:
        """Отправить сообщение пользователю, запустившему бота."""
        self.bot.send(
            content,
            chat_id=self.chat_id,
            attachments=attachments,
            notify=notify,
            disable_link_preview=disable_link_preview,
            format=format,
        )


def text_of(message: MaxApiMessage | None) -> str | None:
    """Текст сообщения MAX API (``None``, если текста нет)."""
    if message is None or message.body is None:
        return None
    return message.body.text


def message_from_update(event: MaxApiMessageCreated, bot: Bot) -> Message:
    """Превратить событие ``message_created`` в :class:`Message`."""
    message = event.message
    sender = message.sender
    return Message(
        text=text_of(message) or "",
        chat_id=message.recipient.chat_id,
        user_id=sender.user_id if sender is not None else None,
        message_id=message.body.mid if message.body is not None else None,
        raw=message,
        bot=bot,
    )


def callback_from_update(event: MaxApiMessageCallback, bot: Bot) -> Callback:
    """Превратить событие ``message_callback`` в :class:`Callback`."""
    source = event.message
    chat_id: int | None = None
    inner: Message | None = None

    if source is not None:
        inner = Message(
            text=text_of(source) or "",
            chat_id=source.recipient.chat_id,
            user_id=source.sender.user_id if source.sender is not None else None,
            message_id=source.body.mid if source.body is not None else None,
            raw=source,
            bot=bot,
        )
        chat_id = inner.chat_id

    return Callback(
        payload=event.callback.payload,
        callback_id=event.callback.callback_id,
        chat_id=chat_id,
        user_id=event.callback.user.user_id,
        message=inner,
        raw=event,
        bot=bot,
    )


def started_from_update(event: MaxApiBotStarted, bot: Bot) -> Started:
    """Превратить событие ``bot_started`` в :class:`Started`."""
    return Started(
        chat_id=event.chat_id,
        user_id=event.user.user_id,
        payload=event.payload,
        raw=event,
        bot=bot,
    )
