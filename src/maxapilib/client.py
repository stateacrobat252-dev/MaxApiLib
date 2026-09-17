"""Асинхронное ядро MaxApiLib: аккуратные вызовы MAX Bot API.

Класс :class:`MaxApiClient` — тонкая обёртка над ``maxapi.Bot``.
Обычно его не нужно использовать напрямую: синхронный фасад
:class:`maxapilib.Bot` вызывает эти методы за вас. Клиент полезен тем,
кому нужен полный контроль над ``async``-кодом.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from maxapi.enums.parse_mode import TextFormat
from maxapi.exceptions.max import InvalidToken, MaxApiError, MaxConnection
from maxapi.types.attachments import AttachmentInput
from maxapi.types.message import Message as MaxApiMessage
from maxapi.types.message import NewMessageLink
from maxapi.types.updates.message_callback import MessageForCallback

from .exceptions import (
    MaxApiLibAPIError,
    MaxApiLibAuthError,
    MaxApiLibNetworkError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from maxapi import Bot as MaxApiBot
    from maxapi.methods.types.sended_callback import SendedCallback
    from maxapi.methods.types.sended_message import SendedMessage
    from maxapi.types.attachments.attachment import Attachment

__all__ = ["MaxApiClient", "is_api_error", "translate_error"]

#: Ошибки ``maxapi``, которые MaxApiLib переводит в свои исключения.
API_ERRORS = (InvalidToken, MaxApiError, MaxConnection, asyncio.TimeoutError, OSError)


def is_api_error(exc: BaseException) -> bool:
    """Относится ли ошибка к обмену данными с MAX API."""
    return isinstance(exc, API_ERRORS)


def translate_error(exc: BaseException, action: str) -> MaxApiLibAPIError:
    """Превратить ошибку ``maxapi`` в понятное исключение MaxApiLib.

    Args:
        exc: Исходная ошибка.
        action: Что библиотека пыталась сделать ("отправить сообщение").
    """
    if isinstance(exc, InvalidToken):
        return MaxApiLibAuthError(
            f"Не удалось {action}: MAX отклонил токен бота (401). "
            "Проверьте токен в Bot(token=...) или в переменной "
            "окружения MAX_BOT_TOKEN.",
            details={"action": action},
        )

    if isinstance(exc, (MaxConnection, asyncio.TimeoutError, OSError)):
        return MaxApiLibNetworkError(
            f"Не удалось {action}: нет связи с API MAX. "
            "Проверьте интернет и повторите попытку.",
            details={"action": action, "error": repr(exc)},
        )

    if isinstance(exc, MaxApiError):
        return MaxApiLibAPIError(
            f"Не удалось {action}: API MAX вернул ошибку {exc.code}: {exc.raw!r}",
            details={"action": action, "code": exc.code, "raw": exc.raw},
        )

    return MaxApiLibAPIError(
        f"Не удалось {action}: {exc!r}",
        details={"action": action, "error": repr(exc)},
    )


class MaxApiClient:
    """Вызовы методов MAX Bot API с понятными ошибками.

    Attributes:
        bot: Исходный объект ``maxapi.Bot``.
    """

    def __init__(self, bot: MaxApiBot) -> None:
        self.bot = bot

    async def send_message(
        self,
        *,
        text: str | None = None,
        chat_id: int | None = None,
        user_id: int | None = None,
        attachments: Sequence[Attachment] | None = None,
        reply_to: str | None = None,
        format: TextFormat | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
    ) -> SendedMessage | None:
        """Отправить сообщение в чат или пользователю.

        Args:
            text: Текст сообщения (до 4000 символов).
            chat_id: ID чата.
            user_id: ID пользователя (если сообщение личное).
            attachments: Вложения (например, клавиатура из
                :meth:`maxapilib.TextBox.to_attachments`).
            reply_to: ``mid`` сообщения, на которое отвечаем.
            format: ``"markdown"`` или ``"html"``.
            notify: Отправлять ли push-уведомление.
            disable_link_preview: Отключить превью ссылок.

        Returns:
            Отправленное сообщение или ``None``.

        Raises:
            MaxApiLibAPIError: Если API MAX вернул ошибку.
            MaxApiLibNetworkError: Если не удалось соединиться с API.
        """
        try:
            return await self.bot.send_message(
                chat_id=chat_id,
                user_id=user_id if chat_id is None else None,
                text=text,
                # maxapi ждёт список конкретных типов вложений, а у нас
                # элементы типизированы базовым Attachment.
                attachments=(
                    cast("list[AttachmentInput]", list(attachments))
                    if attachments
                    else None
                ),
                link=self._reply_link(reply_to),
                format=format,
                notify=notify,
                disable_link_preview=disable_link_preview,
            )
        except Exception as exc:
            raise translate_error(exc, "отправить сообщение") from exc

    async def reply(
        self,
        message: MaxApiMessage,
        *,
        text: str | None = None,
        attachments: Sequence[Attachment] | None = None,
        format: TextFormat | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
    ) -> SendedMessage | None:
        """Ответить на конкретное сообщение (с цитированием).

        Args:
            message: Сообщение ``maxapi``, на которое отвечаем.
            text: Текст ответа.
            attachments: Вложения ответа.
            format: ``"markdown"`` или ``"html"``.
            notify: Отправлять ли push-уведомление.
            disable_link_preview: Отключить превью ссылок.

        Raises:
            MaxApiLibAPIError: Если у сообщения нет ``mid`` или API вернул ошибку.
        """
        if message.body is None:
            msg = "Нельзя ответить: у сообщения нет тела (body)"
            raise MaxApiLibAPIError(msg)

        return await self.send_message(
            text=text,
            chat_id=message.recipient.chat_id,
            user_id=message.recipient.user_id,
            attachments=attachments,
            reply_to=message.body.mid,
            format=format,
            notify=notify,
            disable_link_preview=disable_link_preview,
        )

    async def answer_callback(
        self,
        callback_id: str,
        *,
        text: str | None = None,
        attachments: Sequence[Attachment] | None = None,
        notification: str | None = None,
    ) -> SendedCallback:
        """Ответить на нажатие inline-кнопки.

        Args:
            callback_id: Идентификатор нажатия из события ``message_callback``.
            text: Новый текст сообщения с клавиатурой.
            attachments: Новые вложения сообщения.
            notification: Текст одноразового уведомления пользователю.

        Raises:
            MaxApiLibAPIError: Если API MAX вернул ошибку.
        """
        message = (
            MessageForCallback(
                text=text,
                attachments=list(attachments) if attachments else None,
            )
            if text is not None or attachments
            else None
        )

        try:
            return await self.bot.send_callback(
                callback_id=callback_id,
                message=message,
                notification=notification,
            )
        except Exception as exc:
            raise translate_error(exc, "ответить на нажатие кнопки") from exc

    @staticmethod
    def _reply_link(mid: str | None) -> NewMessageLink | None:
        """Собрать объект связи «ответ» для MAX API."""
        if mid is None:
            return None
        return NewMessageLink.model_validate({"type": "reply", "mid": mid})
