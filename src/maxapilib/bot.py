"""Синхронный фасад над ``maxapi``: класс :class:`Bot`.

Библиотека прячет ``async``/``await``: обработчики — обычные функции,
отправка сообщений — обычные вызовы. Поллинг и сетевые запросы идут в
фоне, в отдельном потоке с собственным ``asyncio``-циклом::

    from maxapilib import Bot, Button, TextBox

    bot = Bot("ТОКЕН")  # или Bot() — токен возьмётся из MAX_BOT_TOKEN

    @bot.on_command("start")
    def start(message):
        menu = TextBox("Выберите действие:")
        menu.add(Button.callback("Сайт", "site"))
        message.reply(menu)

    @bot.on_button("site")
    def site(callback):
        callback.answer("Открываю сайт")

    bot.run()
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import contextvars
import inspect
import logging
import os
import threading
import traceback
from collections.abc import Callable, Coroutine, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from maxapi import Bot as MaxApiBot
from maxapi import Dispatcher
from maxapi.context import MemoryContext
from maxapi.enums.parse_mode import TextFormat
from maxapi.filters.state import StateFilter
from maxapi.types.attachments.attachment import Attachment
from maxapi.types.message import Message as MaxApiMessage

from .client import MaxApiClient, is_api_error, translate_error
from .exceptions import MaxApiLibAuthError, MaxApiLibError, MaxApiLibTimeoutError
from .filters import CallbackPayload, CommandFilter, TextPattern
from .logs import enable_logging
from .monitoring import Monitor, Stats
from .states import StateManager, target_ids
from .types import (
    Callback,
    Error,
    Message,
    Started,
    TextBox,
    callback_from_update,
    message_from_update,
    started_from_update,
)
from .webhook import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    WebhookServer,
    generate_secret,
)

if TYPE_CHECKING:
    from maxapi.context import BaseContext
    from maxapi.dispatcher import Event

logger = logging.getLogger("maxapilib")

#: Имя переменной окружения, из которой ``maxapi`` берёт токен бота.
TOKEN_ENV_VAR = "MAX_BOT_TOKEN"

#: Сколько секунд синхронный вызов ждёт ответа MAX API.
DEFAULT_CALL_TIMEOUT = 30.0

#: Уровень логирования по умолчанию: видно события и отправки.
DEFAULT_LOG_LEVEL = "INFO"

#: Максимальная длина текста сообщения в MAX.
MAX_TEXT_LENGTH = 4000

F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")

#: Асинхронная обёртка, которую получает диспетчер ``maxapi``.
CoroHandler = Callable[[Any], Coroutine[Any, Any, None]]
#: Аргументы события: сообщение, нажатие кнопки или запуск бота.
EventView = Message | Callback | Started


def as_format(value: str | TextFormat | None) -> TextFormat | None:
    """Привести формат текста к ``TextFormat`` (``markdown``/``html``).

    Raises:
        ValueError: Если формат неизвестен.
    """
    if value is None or isinstance(value, TextFormat):
        return value

    try:
        return TextFormat(value.lower())
    except ValueError as exc:
        message = (
            f"Неизвестный формат {value!r}: используйте 'markdown' или 'html'"
        )
        raise ValueError(message) from exc


def _check_token(token: str | None) -> None:
    """Проверить токен бота до создания ``maxapi.Bot``.

    Raises:
        MaxApiLibAuthError: Если токен не передан и нет переменной окружения.
        ValueError: Если токен слишком короткий, чтобы быть настоящим.
    """
    if token is None:
        if not os.environ.get(TOKEN_ENV_VAR):
            message = (
                "Не указан токен бота: передайте его в Bot(token='...') "
                f"или задайте переменную окружения {TOKEN_ENV_VAR}."
            )
            raise MaxApiLibAuthError(message)
        return

    if len(token.strip()) < 10:
        message = (
            "Некорректный токен бота: он должен быть длиннее 10 символов. "
            "Проверьте, что скопировали токен целиком."
        )
        raise ValueError(message)


def unpack_content(
    content: object, attachments: Sequence[Attachment] | None
) -> tuple[str | None, list[Attachment] | None]:
    """Разобрать содержимое сообщения на текст и вложения.

    Raises:
        MaxApiLibError: Если передан не текст и не :class:`TextBox`.
    """
    keyboard: list[Attachment] | None = None

    if isinstance(content, TextBox):
        text: str | None = content.text
        keyboard = content.to_attachments()
    elif isinstance(content, str):
        if not content.strip():
            message = "Текст сообщения не может быть пустым"
            raise MaxApiLibError(message)
        text = content
    else:
        message = (
            "Сообщение должно быть строкой или TextBox, "
            f"получено {type(content).__name__}"
        )
        raise MaxApiLibError(message)

    packed = [*(keyboard or []), *(attachments or [])]
    return text, packed or None


class Bot:
    """Синхронный бот для мессенджера MAX.

    Обработчики регистрируются декораторами до запуска:

    * :meth:`on_command` — команды ``/start``, ``/help`` и т.д.;
    * :meth:`on_text` — текст по регулярному выражению;
    * :meth:`on_button` — нажатие кнопки с нужным ``payload``;
    * :meth:`on_callback` — любое нажатие inline-кнопки;
    * :meth:`on_message` — любое входящее сообщение (запасной вариант);
    * :meth:`on_started` — пользователь нажал «Начать»;
    * :meth:`on_state` — сообщение в нужном состоянии (`FSM` <состояния>`__);
    * :meth:`on_error` — ошибка в любом обработчике.

    Обработчики вызываются по порядку регистрации: срабатывает первый
    подходящий. У любого обработчика можно указать ``state="имя"``, чтобы
    он работал только в этом состоянии.

    Запуск: :meth:`run` (long polling) или :meth:`run_webhook` (вебхук).

    Attributes:
        maxapi: Исходный объект ``maxapi.Bot`` (доступ ко всем методам API).
        dispatcher: Диспетчер ``maxapi`` (фильтры, middleware, роутеры).
        stats: Счётчики работы бота (:class:`maxapilib.Stats`),
            в том числе для мониторинга.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        format: str | TextFormat | None = None,
        log_level: int | str | None = DEFAULT_LOG_LEVEL,
        log_file: str | Path | None = None,
        admin_id: int | None = None,
        call_timeout: float = DEFAULT_CALL_TIMEOUT,
        skip_updates: bool = False,
        auto_check_subscriptions: bool = True,
        storage: type[BaseContext] | None = None,
        storage_options: dict[str, Any] | None = None,
    ) -> None:
        """Создать бота.

        Args:
            token: Токен бота. Если ``None``, берётся из переменной
                окружения ``MAX_BOT_TOKEN``.
            format: Формат текста по умолчанию: ``"markdown"`` или ``"html"``.
            log_level: Уровень логирования (по умолчанию ``"INFO"``):
                видно каждое событие и каждую отправку.
                ``None`` — не настраивать логи вообще.
            log_file: Файл, куда дополнительно писать логи.
            admin_id: ID пользователя (ваш), которому бот пришлёт
                сообщение об ошибке в обработчике.
            call_timeout: Сколько секунд ждать ответа MAX API
                в синхронных вызовах.
            skip_updates: Не обрабатывать события, случившиеся до запуска
                бота (полезно, чтобы не отвечать на старые сообщения).
            auto_check_subscriptions: Проверять при запуске, нет ли у бота
                вебхука (вебхук отключает поллинг).
            storage: Где хранить состояния и данные
                (по умолчанию — в оперативной памяти).
            storage_options: Параметры хранилища, например
                ``{"url": "redis://localhost"}`` для Redis.

        Raises:
            MaxApiLibAuthError: Если токен не найден.
            ValueError: Если токен, формат или уровень логов указаны неверно.
        """
        _check_token(token)

        if log_level is not None or log_file is not None:
            enable_logging(
                log_level if log_level is not None else DEFAULT_LOG_LEVEL,
                file=log_file,
            )

        self.maxapi = MaxApiBot(
            token=token,
            format=as_format(format),
            auto_check_subscriptions=auto_check_subscriptions,
        )
        self.dispatcher = Dispatcher(
            router_id="maxapilib",
            storage=storage or MemoryContext,
            **(storage_options or {}),
        )

        #: Счётчики работы бота: print(bot.stats) или bot.stats.as_dict().
        self.stats = Stats()
        # Каждое событие (даже без подходящего обработчика) попадает
        # в счётчики и в лог.
        self.dispatcher.register_outer_middleware(Monitor(self.stats))

        self._client = MaxApiClient(self.maxapi)
        self._states = StateManager(self.dispatcher.fsm)
        self._admin_id = admin_id
        self._error_handlers: list[
            tuple[tuple[type[BaseException], ...], Callable[..., Any]]
        ] = []
        self._context: contextvars.ContextVar[EventView | None] = (
            contextvars.ContextVar("maxapilib_event", default=None)
        )
        self._call_timeout = call_timeout
        self._skip_updates = skip_updates
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._fatal: BaseException | None = None
        self._webhook_url: str | None = None
        self._webhook_secret: str | None = None
        self._webhook_host = DEFAULT_HOST
        self._webhook_requested_port = DEFAULT_PORT
        self._webhook_port: int | None = None
        self._webhook_subscribe = True
        self._webhook_server: WebhookServer | None = None

    @property
    def is_running(self) -> bool:
        """``True``, если бот запущен (поллинг или вебхук)."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def webhook_port(self) -> int | None:
        """Порт сервера вебхука (``None``, если бот работает на поллинге)."""
        return self._webhook_port

    @property
    def current(self) -> EventView | None:
        """Событие, которое обрабатывается прямо сейчас в этом потоке.

        Внутри обработчика возвращает :class:`Message`, :class:`Callback`
        или :class:`Started`, вне обработчика — ``None``.
        """
        return self._context.get()

    # ------------------------------------------------------------------
    # Регистрация обработчиков
    # ------------------------------------------------------------------

    def on_command(
        self, *commands: str, prefix: str = "/", state: str | None = None
    ) -> Callable[[F], F]:
        """Декоратор: обработка команд вида ``/start``.

        Args:
            *commands: Команды без префикса: ``"start"``, ``"help"``.
            prefix: Префикс команды (по умолчанию ``"/"``).
            state: Сработать только в этом состоянии (см. :meth:`on_state`).

        Example::

            @bot.on_command("start", "help")
            def handle(message):
                print(message.command, message.args)
        """
        return self._register(
            self.dispatcher.message_created,
            CommandFilter(commands, prefix=prefix),
            self._make_message_handler,
            state=state,
        )

    def on_text(
        self, pattern: str, *, state: str | None = None
    ) -> Callable[[F], F]:
        """Декоратор: обработка сообщений, подходящих под регулярное выражение.

        Args:
            pattern: Регулярное выражение, которое ищется в тексте.
            state: Сработать только в этом состоянии.

        Example::

            @bot.on_text(r"привет|здравствуй")
            def hello(message):
                message.reply("И вам привет!")
        """
        return self._register(
            self.dispatcher.message_created,
            TextPattern(pattern),
            self._make_message_handler,
            state=state,
        )

    def on_button(
        self, payload: str, *, state: str | None = None
    ) -> Callable[[F], F]:
        """Декоратор: обработка нажатия кнопки с указанным ``payload``.

        Args:
            payload: Данные кнопки.
            state: Сработать только в этом состоянии.

        Example::

            @bot.on_button("site")
            def site(callback):
                callback.answer("Открываю сайт")
        """
        return self._register(
            self.dispatcher.message_callback,
            CallbackPayload(payload),
            self._make_callback_handler,
            state=state,
        )

    def on_callback(self, *, state: str | None = None) -> Callable[[F], F]:
        """Декоратор: обработка любого нажатия inline-кнопки."""
        return self._register(
            self.dispatcher.message_callback,
            None,
            self._make_callback_handler,
            state=state,
        )

    def on_message(self, *, state: str | None = None) -> Callable[[F], F]:
        """Декоратор: обработка любого входящего сообщения.

        Ставьте его последним: срабатывает первый подходящий обработчик.

        Args:
            state: Сработать только в этом состоянии.
        """
        return self._register(
            self.dispatcher.message_created,
            None,
            self._make_message_handler,
            state=state,
        )

    def on_state(self, *states: str) -> Callable[[F], F]:
        """Декоратор: сообщение, пришедшее в одном из этих состояний.

        Самый простой способ сделать диалог-анкету:

        Example::

            @bot.on_command("start")
            def start(message):
                bot.set_state(message, "waiting_name")
                message.reply("Как вас зовут?")

            @bot.on_state("waiting_name")
            def get_name(message):
                bot.reset_state(message)
                message.reply(f"Привет, {message.text}!")

        Args:
            *states: Имена состояний. ``"*"`` — любое состояние.
        """
        return self._register(
            self.dispatcher.message_created,
            StateFilter(*states),
            self._make_message_handler,
        )

    def on_started(self) -> Callable[[F], F]:
        """Декоратор: пользователь запустил бота (нажал «Начать»)."""
        return self._register(
            self.dispatcher.bot_started, None, self._make_started_handler
        )

    def on_error(
        self, *exceptions: type[BaseException]
    ) -> Callable[[F], F]:
        """Декоратор: что делать, если в обработчике случилась ошибка.

        Без него ошибка попадает в лог и в счётчики, а бот продолжает
        работать. Аргументами можно ограничить типы ошибок:

        Example::

            @bot.on_error()
            def any_error(error):
                print("Упс:", error.text)

            @bot.on_error(ValueError)
            def only_value_error(error):
                print("Плохое значение:", error.text)
        """

        def decorator(func: F) -> F:
            self._check_handler(func)
            self._error_handlers.append((tuple(exceptions), func))
            logger.debug(
                "Зарегистрирован обработчик ошибок %s",
                getattr(func, "__name__", "handler"),
            )
            return func

        self._ensure_not_running()
        return decorator

    def _register(
        self,
        event: Event,
        filter_: Any,
        wrap: Callable[[Callable[..., Any]], CoroHandler],
        *,
        state: str | None = None,
    ) -> Callable[[F], F]:
        """Общий код регистрации обработчика в диспетчере ``maxapi``."""
        self._ensure_not_running()

        def decorator(func: F) -> F:
            self._check_handler(func)
            wrapper = wrap(func)
            filters: list[Any] = []
            if filter_ is not None:
                filters.append(filter_)
            if state is not None:
                filters.append(StateFilter(state))
            event(*filters)(wrapper)
            logger.debug(
                "Зарегистрирован обработчик %s",
                getattr(func, "__name__", "handler"),
            )
            return func

        return decorator

    def _ensure_not_running(self) -> None:
        """Запретить менять обработчики у работающего бота.

        Raises:
            MaxApiLibError: Если бот уже запущен.
        """
        if self.is_running:
            message = (
                "Нельзя добавлять обработчики после запуска бота: "
                "перенесите декораторы выше вызова bot.run()."
            )
            raise MaxApiLibError(message)

    def _check_handler(self, func: Callable[..., Any]) -> None:
        """Проверить обработчик перед регистрацией.

        Raises:
            MaxApiLibError: Если бот уже запущен или функция асинхронная.
        """
        self._ensure_not_running()

        if inspect.iscoroutinefunction(func):
            name = getattr(func, "__name__", "обработчик")
            message = (
                f"Обработчик {name} объявлен через async def, а MaxApiLib "
                "вызывает обычные функции. Уберите async и await: "
                "вся асинхронность внутри библиотеки."
            )
            raise MaxApiLibError(message)

    def _make_message_handler(self, func: Callable[..., Any]) -> CoroHandler:
        """Обёртка для событий ``message_created``."""

        async def handler(event: Any) -> None:
            await self._call_handler(func, message_from_update(event, self))

        _rename(handler, func)
        return handler

    def _make_callback_handler(self, func: Callable[..., Any]) -> CoroHandler:
        """Обёртка для событий ``message_callback``."""

        async def handler(event: Any) -> None:
            await self._call_handler(func, callback_from_update(event, self))

        _rename(handler, func)
        return handler

    def _make_started_handler(self, func: Callable[..., Any]) -> CoroHandler:
        """Обёртка для событий ``bot_started``."""

        async def handler(event: Any) -> None:
            await self._call_handler(func, started_from_update(event, self))

        _rename(handler, func)
        return handler

    async def _call_handler(
        self, func: Callable[..., Any], view: EventView
    ) -> None:
        """Вызвать синхронный обработчик пользователя в отдельном потоке.

        Пользовательский код может блокироваться (например, ``time.sleep``)
        и вызывать ``bot.send()``: выполнение идёт в рабочем потоке, поэтому
        цикл событий продолжает обслуживать сетевые запросы.

        Ошибка в обработчике не роняет бота: она попадает в лог, в счётчики
        и в обработчики :meth:`on_error`.
        """
        token = self._context.set(view)
        try:
            await asyncio.to_thread(func, view)
        except Exception as exc:
            await self._report_error(exc, view, traceback.format_exc())
        finally:
            self._context.reset(token)

    async def _report_error(
        self, exc: BaseException, view: EventView, traceback_text: str
    ) -> None:
        """Залогировать ошибку обработчика и сообщить о ней."""
        self.stats.count_error(exc)
        logger.error(
            "Ошибка в обработчике (%s): %s: %s\n%s",
            self._describe_view(view),
            type(exc).__name__,
            exc,
            traceback_text,
        )

        error = Error(
            exception=exc,
            traceback=traceback_text,
            event=view,
            bot=self,
        )

        if self._error_handlers:
            await asyncio.to_thread(self._call_error_handlers, error)

        if self._admin_id is not None:
            with contextlib.suppress(Exception):
                await self._client.send_message(
                    text=self._error_message(error), user_id=self._admin_id
                )

    def _call_error_handlers(self, error: Error) -> None:
        """Вызвать обработчики ошибок (в рабочем потоке)."""
        for exceptions, func in self._error_handlers:
            if exceptions and not isinstance(error.exception, exceptions):
                continue
            try:
                func(error)
            except Exception:  # обработчик ошибок не должен ломать бота
                logger.exception(
                    "Ошибка в обработчике on_error %s",
                    getattr(func, "__name__", "handler"),
                )

    def _error_message(self, error: Error) -> str:
        """Текст сообщения об ошибке для админа (``admin_id``)."""
        text = f"⚠️ Ошибка в боте: {error.text}"
        if error.event is not None:
            text = f"{text}\nСобытие: {self._describe_view(error.event)}"
        return text[:MAX_TEXT_LENGTH]

    @staticmethod
    def _describe_view(view: EventView) -> str:
        """Короткое описание события из обработчика."""
        if isinstance(view, Message):
            return (
                f"сообщение от {view.user_id} в чат {view.chat_id}: "
                f"{view.text!r}"
            )
        if isinstance(view, Callback):
            return (
                f"нажатие кнопки {view.payload!r}"
                f" (пользователь {view.user_id}, чат {view.chat_id})"
            )
        return f"запуск бота пользователем {view.user_id} (чат {view.chat_id})"

    # ------------------------------------------------------------------
    # Отправка сообщений (синхронные методы)
    # ------------------------------------------------------------------

    def send(
        self,
        content: str | TextBox,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
        attachments: Sequence[Attachment] | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        format: str | TextFormat | None = None,
    ) -> None:
        """Отправить сообщение (синхронно, с ожиданием ответа MAX API).

        Если ``chat_id`` и ``user_id`` не указаны, сообщение уходит в тот
        чат, откуда пришло текущее событие (то есть внутри обработчика
        адрес можно не указывать).

        Raises:
            MaxApiLibError: Если получатель неизвестен или бот не запущен.
            MaxApiLibAPIError: Если MAX API вернул ошибку.
        """
        text, packed = unpack_content(content, attachments)
        if chat_id is None and user_id is None:
            chat_id, user_id = self._target_from_context()
        if chat_id is None and user_id is None:
            message = (
                "Не указан получатель: передайте chat_id или user_id, "
                "либо вызывайте send() внутри обработчика."
            )
            raise MaxApiLibError(message)

        self._submit(
            self._client.send_message(
                text=text,
                chat_id=chat_id,
                user_id=user_id,
                attachments=packed,
                format=as_format(format),
                notify=notify,
                disable_link_preview=disable_link_preview,
            )
        )
        self.stats.count_sent()
        logger.info(
            "→ %s: %r",
            self._describe_target(chat_id, user_id),
            (text or "[вложения]")[:MAX_TEXT_LENGTH],
        )

    def reply(
        self,
        message: Message | MaxApiMessage,
        content: str | TextBox,
        *,
        attachments: Sequence[Attachment] | None = None,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        format: str | TextFormat | None = None,
    ) -> None:
        """Ответить на сообщение (с цитированием).

        Args:
            message: :class:`Message` из обработчика или объект сообщения
                ``maxapi``.
            content: Текст или :class:`TextBox`.
        """
        text, packed = unpack_content(content, attachments)
        raw = message.raw if isinstance(message, Message) else message

        self._submit(
            self._client.reply(
                raw,
                text=text,
                attachments=packed,
                format=as_format(format),
                notify=notify,
                disable_link_preview=disable_link_preview,
            )
        )
        self.stats.count_sent()
        logger.info(
            "→ ответ в чат %s: %r",
            raw.recipient.chat_id,
            (text or "[вложения]")[:MAX_TEXT_LENGTH],
        )

    def answer_callback(
        self,
        callback: Callback | str,
        text: str | None = None,
        *,
        attachments: Sequence[Attachment] | None = None,
        notification: str | None = None,
    ) -> None:
        """Ответить на нажатие inline-кнопки.

        MAX Bot API ждёт ответ на каждое нажатие: ``text`` меняет текущее
        сообщение с клавиатурой, ``notification`` показывает одноразовое
        уведомление.

        Args:
            callback: :class:`Callback` из обработчика или ``callback_id``.
            text: Новый текст сообщения.
            attachments: Новые вложения сообщения.
            notification: Текст всплывающего уведомления.
        """
        callback_id = (
            callback.callback_id if isinstance(callback, Callback) else callback
        )
        self._submit(
            self._client.answer_callback(
                callback_id,
                text=text,
                attachments=attachments,
                notification=notification,
            )
        )
        self.stats.count_answer()
        logger.debug("→ ответ на нажатие кнопки %s отправлен", callback_id)

    @staticmethod
    def _describe_target(chat_id: int | None, user_id: int | None) -> str:
        """Описание получателя для лога."""
        if chat_id is not None:
            return f"отправлено в чат {chat_id}"
        return f"отправлено пользователю {user_id}"

    def _target_from_context(self) -> tuple[int | None, int | None]:
        """Определить получателя по событию, которое сейчас обрабатывается."""
        view = self._context.get()
        if view is None:
            return None, None
        return view.chat_id, view.user_id

    # ------------------------------------------------------------------
    # Состояния и данные (FSM)
    # ------------------------------------------------------------------

    def set_state(
        self,
        target: EventView | str,
        state: str | None = None,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        """Запомнить состояние пользователя.

        Два способа вызова::

            bot.set_state(message, "waiting_name")       # из обработчика
            bot.set_state("waiting_name", chat_id=42)    # по ID чата

        ``state=None`` — сбросить состояние (то же делает
        :meth:`reset_state`).
        """
        if isinstance(target, str):
            state = target
            ids = target_ids(None, chat_id=chat_id, user_id=user_id)
        else:
            ids = target_ids(target)

        self._submit(
            self._states.set_state(
                chat_id=ids[0], user_id=ids[1], state=state
            )
        )
        logger.debug(
            "Состояние чата %s / пользователя %s: %r", ids[0], ids[1], state
        )

    def get_state(
        self,
        target: EventView | None = None,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> str | None:
        """Текущее состояние пользователя или ``None``.

        Example::

            if bot.get_state(message) == "waiting_name":
                ...
        """
        ids = target_ids(target, chat_id=chat_id, user_id=user_id)
        return self._submit(
            self._states.get_state(chat_id=ids[0], user_id=ids[1])
        )

    def set_data(
        self,
        target: EventView | None = None,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
        **values: Any,
    ) -> dict[str, Any]:
        """Сохранить данные пользователя.

        Example::

            bot.set_data(message, name="Иван", city="Москва")
            bot.get_data(message)          # {'name': 'Иван', 'city': 'Москва'}
            bot.get_data(message, "name")  # 'Иван'

        Returns:
            Все данные пользователя после сохранения.
        """
        ids = target_ids(target, chat_id=chat_id, user_id=user_id)
        return self._submit(
            self._states.set_data(
                chat_id=ids[0], user_id=ids[1], **values
            )
        )

    def get_data(
        self,
        target: EventView | None = None,
        key: str | None = None,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> Any:
        """Данные пользователя: весь словарь или одно значение по ключу.

        Example::

            bot.get_data(message)          # {'name': 'Иван'}
            bot.get_data(message, "name")  # 'Иван'
        """
        ids = target_ids(target, chat_id=chat_id, user_id=user_id)
        return self._submit(
            self._states.get_data(
                chat_id=ids[0], user_id=ids[1], key=key
            )
        )

    def reset_state(
        self,
        target: EventView | None = None,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        """Забыть состояние и данные пользователя (выйти из анкеты)."""
        ids = target_ids(target, chat_id=chat_id, user_id=user_id)
        self._submit(
            self._states.reset(chat_id=ids[0], user_id=ids[1])
        )
        logger.debug(
            "Состояние и данные чата %s / пользователя %s очищены",
            ids[0],
            ids[1],
        )

    # ------------------------------------------------------------------
    # Запуск и остановка
    # ------------------------------------------------------------------

    def run(self, *, blocking: bool = True) -> None:
        """Запустить бота.

        Args:
            blocking: ``True`` (по умолчанию) — блокирует поток до остановки
                бота или Ctrl+C; ``False`` — запускает бота в фоне, чтобы
                код после ``run()`` продолжал выполняться.

        Raises:
            MaxApiLibError: Если бот уже запущен.
            MaxApiLibError: Если при запуске произошла ошибка
                (например, :class:`MaxApiLibAuthError` из-за неверного токена).
        """
        self._launch(blocking=blocking, webhook=None)

    def run_webhook(
        self,
        url: str,
        *,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        secret: str | None = None,
        subscribe: bool = True,
        blocking: bool = True,
    ) -> None:
        """Запустить бота на вебхуке.

        Этот способ рекомендует MAX для продакшена: события приходят
        на ваш HTTPS-адрес сразу, без опроса API.

        Args:
            url: Публичный адрес, по которому MAX будет присылать события,
                например ``"https://bot.example.com/hook"``.
            host: На каком интерфейсе слушать (по умолчанию все).
            port: Порт сервера (по умолчанию 8080; ``0`` — любой свободный).
            secret: Секрет, по которому библиотека проверяет, что запрос
                пришёл от MAX. Если не указан, а ``subscribe=True`` —
                придумывается автоматически.
            subscribe: Подписать бота на события (``False`` — если подписка
                уже настроена или для проверки на своём компьютере).
            blocking: ``True`` (по умолчанию) — блокирует поток до Ctrl+C;
                ``False`` — работает в фоне.

        Example::

            bot.run_webhook("https://bot.example.com/hook")

        В режиме вебхука доступны адреса для мониторинга:
        ``GET /health`` и ``GET /stats``.
        """
        self._launch(
            blocking=blocking,
            webhook=(url, host, port, secret, subscribe),
        )

    def delete_webhook(self) -> None:
        """Удалить подписки на вебхук.

        Нужно, если бот раньше работал через вебхук, а теперь должен
        отвечать через long polling: пока подписка есть, MAX события
        в поллинг не отдаёт.
        """
        self._submit(self.maxapi.delete_webhook())
        logger.info(
            "Подписки на вебхук удалены: бот снова может работать "
            "на long polling"
        )

    def webhooks(self) -> list[str]:
        """Адреса вебхуков, на которые сейчас подписан бот.

        Если список не пустой, а бот запущен через :meth:`run`,
        события в поллинг не придут — нужен :meth:`delete_webhook`.
        """
        subscriptions = self._submit(self.maxapi.get_subscriptions())
        return [item.url for item in subscriptions.subscriptions]

    def _launch(
        self,
        *,
        blocking: bool,
        webhook: tuple[str, str, int, str | None, bool] | None,
    ) -> None:
        """Общий запуск для :meth:`run` и :meth:`run_webhook`."""
        if self.is_running:
            message = "Бот уже запущен: повторный вызов не нужен."
            raise MaxApiLibError(message)

        if webhook is None:
            self._webhook_url = None
            self._webhook_secret = None
            self._webhook_port = None
        else:
            url, host, port, secret, subscribe = webhook
            self._webhook_url = url
            self._webhook_host = host
            self._webhook_requested_port = port
            self._webhook_subscribe = subscribe
            if secret is not None:
                self._webhook_secret = secret
            elif subscribe:
                # Секрет нужен MAX, чтобы бот принимал только «свои»
                # запросы: придумываем его за пользователя.
                self._webhook_secret = generate_secret()
            else:
                self._webhook_secret = None

        self._fatal = None
        self._stop_requested.clear()
        self.stats.mark_started(reset=True)
        self._thread = threading.Thread(
            target=self._run_loop, name="maxapilib-bot", daemon=True
        )
        self._thread.start()

        if self._webhook_url is None:
            logger.info(
                "Бот запускается на long polling. "
                "Для остановки нажмите Ctrl+C."
            )
        else:
            logger.info(
                "Бот запускается на вебхуке %s. "
                "Для остановки нажмите Ctrl+C.",
                self._webhook_url,
            )

        if not blocking:
            return

        try:
            self.wait()
        except KeyboardInterrupt:
            logger.info("Получен Ctrl+C, останавливаю бота...")
        finally:
            self.stop()

        if self._fatal is not None:
            raise self._fatal

    def wait(self, timeout: float | None = None) -> None:
        """Дождаться остановки бота.

        Полезно после ``run(blocking=False)`` и в тестах.

        Raises:
            MaxApiLibError: Если бот не запущен.
        """
        thread = self._thread
        if thread is None:
            message = "Бот не запущен: сначала вызовите bot.run()."
            raise MaxApiLibError(message)
        thread.join(timeout)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Остановить бота и дождаться завершения поллинга.

        Метод безопасно вызывать повторно и из обработчика. Если поллинг
        не завершился за ``timeout`` секунд, выводится предупреждение.
        """
        # Флаг на threading.Event: его можно ставить до того, как фоновый
        # поток успел создать свой цикл событий (иначе stop() сразу после
        # run() мог не сработать).
        self._stop_requested.set()

        thread = self._thread
        if thread is None:
            return

        loop, stop_event = self._loop, self._stop_event
        if loop is not None and loop.is_running() and stop_event is not None:
            loop.call_soon_threadsafe(stop_event.set)

        if threading.current_thread() is thread:
            # stop() вызван из обработчика: дождаться не получится,
            # поток завершится сам после текущего события.
            return

        thread.join(timeout)
        if thread.is_alive():
            logger.warning("Бот не остановился за %.1f c", timeout)
            return

        self._thread = None
        self.stats.mark_stopped()
        logger.info("Бот остановлен. %s", self.stats)

    # ------------------------------------------------------------------
    # Служебные методы
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Тело фонового потока: свой цикл событий и поллинг."""
        loop = asyncio.new_event_loop()
        self._loop = loop
        self._stop_event = asyncio.Event()
        if self._stop_requested.is_set():
            self._stop_event.set()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._serve())
        except BaseException as exc:  # ошибку вернём из bot.run()
            translated = (
                translate_error(exc, "запустить бота") if is_api_error(exc) else exc
            )
            self._fatal = translated
            logger.error("Бот остановлен из-за ошибки: %r", translated)
        finally:
            with contextlib.suppress(Exception):
                loop.run_until_complete(self.maxapi.close_session())
            with contextlib.suppress(Exception):
                loop.run_until_complete(loop.shutdown_asyncgens())
            asyncio.set_event_loop(None)
            loop.close()
            self._loop = None
            self._stop_event = None

    async def _serve(self) -> None:
        """Работа бота до остановки: поллинг или вебхук."""
        if self._webhook_url is None:
            await self._serve_polling()
        else:
            await self._serve_webhook()

    async def _serve_webhook(self) -> None:
        """Поднять сервер вебхука и работать до остановки бота."""
        stop_event = self._stop_event
        url = self._webhook_url
        if stop_event is None or url is None:  # pragma: no cover - гонка
            return

        server = WebhookServer(
            dispatcher=self.dispatcher,
            bot=self.maxapi,
            url=url,
            host=self._webhook_host,
            port=self._webhook_requested_port,
            secret=self._webhook_secret,
            stats=self.stats,
        )
        await server.start()
        self._webhook_server = server
        self._webhook_port = server.bound_port
        logger.info("Вебхук: %s", server.describe())

        if self._webhook_subscribe:
            await self._subscribe_webhook(url)

        try:
            await stop_event.wait()
        finally:
            await server.stop()
            self._webhook_server = None
            self._webhook_port = None
            logger.info("Сервер вебхука остановлен")

    async def _subscribe_webhook(self, url: str) -> None:
        """Подписать бота на события через вебхук."""
        try:
            result = await self.maxapi.subscribe_webhook(
                url=url, secret=self._webhook_secret
            )
        except Exception as exc:
            logger.error("Не удалось подписаться на вебхук %s: %s", url, exc)
            logger.error(
                "Проверьте, что MAX может открыть этот адрес по HTTPS. "
                "Если подписка уже настроена, запускайте так: "
                "bot.run_webhook(url, subscribe=False)."
            )
            return

        if result.success:
            logger.info("Подписка на вебхук оформлена: %s", url)
        else:
            logger.error(
                "MAX отказал в подписке на %s: %s", url, result.message
            )

    async def _serve_polling(self) -> None:
        """Поллинг до остановки бота."""
        stop_event = self._stop_event
        if stop_event is None:  # pragma: no cover - защита от гонок
            return

        polling = asyncio.create_task(
            self.dispatcher.start_polling(
                self.maxapi, skip_updates=self._skip_updates
            ),
            name="maxapilib-polling",
        )
        stopping = asyncio.create_task(stop_event.wait(), name="maxapilib-stop")

        error: BaseException | None = None
        try:
            done, _ = await asyncio.wait(
                {polling, stopping}, return_when=asyncio.FIRST_COMPLETED
            )
            if polling in done and not polling.cancelled():
                error = polling.exception()
        finally:
            await self.dispatcher.stop_polling()
            for task in (polling, stopping):
                if not task.done():
                    task.cancel()
            await asyncio.gather(polling, stopping, return_exceptions=True)

        if error is not None:
            raise error

    def _submit(self, coro: Coroutine[Any, Any, T]) -> T:
        """Выполнить корутину и дождаться результата.

        Если бот запущен, работа идёт в его цикле событий. В ином случае
        (например, ``bot.send`` для разового уведомления) корутина
        выполняется в отдельном временном цикле.

        Raises:
            MaxApiLibError: Если метод вызван из асинхронного кода.
            MaxApiLibTimeoutError: Если ответа нет дольше ``call_timeout``.
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            if _running_loop() is not None:
                coro.close()
                message = (
                    "Синхронные методы нельзя вызывать из асинхронного "
                    "кода: используйте обычные функции-обработчики."
                )
                raise MaxApiLibError(message)
            return self._run_standalone(coro)

        if _running_loop() is loop:
            coro.close()
            message = (
                "Синхронные методы нельзя вызывать из цикла событий бота: "
                "используйте обычные функции-обработчики."
            )
            raise MaxApiLibError(message)

        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(self._call_timeout)
        except concurrent.futures.TimeoutError as exc:
            # Начиная с Python 3.11 concurrent.futures.TimeoutError — это
            # встроенный TimeoutError, поэтому отличаем собственный таймаут
            # (задача ещё не завершена) от ошибки внутри корутины.
            if future.done():
                raise
            future.cancel()
            message = (
                f"MAX API не ответил за {self._call_timeout:g} c. "
                "Увеличьте call_timeout, если сеть медленная."
            )
            raise MaxApiLibTimeoutError(
                message, details={"timeout": self._call_timeout}
            ) from exc

    def _run_standalone(self, coro: Coroutine[Any, Any, T]) -> T:
        """Выполнить корутину в отдельном цикле событий (бот не запущен)."""

        async def runner() -> T:
            try:
                return await asyncio.wait_for(coro, self._call_timeout)
            except asyncio.TimeoutError as exc:
                message = (
                    f"MAX API не ответил за {self._call_timeout:g} c. "
                    "Увеличьте call_timeout, если сеть медленная."
                )
                raise MaxApiLibTimeoutError(
                    message, details={"timeout": self._call_timeout}
                ) from exc
            finally:
                # Сессия aiohttp привязана к циклу: закрываем её, чтобы
                # следующий разовый вызов начал с чистой сессии.
                with contextlib.suppress(Exception):
                    await self.maxapi.close_session()

        return asyncio.run(runner())


def _rename(handler: CoroHandler, source: Callable[..., Any]) -> None:
    """Дать обёртке имя пользовательской функции (для логов maxapi)."""
    setattr(handler, "__name__", getattr(source, "__name__", "handler"))  # noqa: B010


def _running_loop() -> asyncio.AbstractEventLoop | None:
    """Вернуть цикл событий текущего потока, если он запущен."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None
