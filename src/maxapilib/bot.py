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
from collections.abc import Callable, Coroutine, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from maxapi import Bot as MaxApiBot
from maxapi import Dispatcher
from maxapi.enums.parse_mode import TextFormat
from maxapi.types.attachments.attachment import Attachment
from maxapi.types.message import Message as MaxApiMessage

from .client import MaxApiClient, is_api_error, translate_error
from .exceptions import MaxApiLibAuthError, MaxApiLibError, MaxApiLibTimeoutError
from .filters import CallbackPayload, CommandFilter, TextPattern
from .logs import enable_logging
from .types import (
    Callback,
    Message,
    Started,
    TextBox,
    callback_from_update,
    message_from_update,
    started_from_update,
)

if TYPE_CHECKING:
    from maxapi.dispatcher import Event

logger = logging.getLogger("maxapilib")

#: Имя переменной окружения, из которой ``maxapi`` берёт токен бота.
TOKEN_ENV_VAR = "MAX_BOT_TOKEN"

#: Сколько секунд синхронный вызов ждёт ответа MAX API.
DEFAULT_CALL_TIMEOUT = 30.0

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
    * :meth:`on_started` — пользователь нажал «Начать».

    Обработчики вызываются по порядку регистрации: срабатывает первый
    подходящий.

    Attributes:
        maxapi: Исходный объект ``maxapi.Bot`` (доступ ко всем методам API).
        dispatcher: Диспетчер ``maxapi`` (фильтры, middleware, роутеры).
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        format: str | TextFormat | None = None,
        log_level: int | str | None = None,
        call_timeout: float = DEFAULT_CALL_TIMEOUT,
        skip_updates: bool = False,
        auto_check_subscriptions: bool = True,
    ) -> None:
        """Создать бота.

        Args:
            token: Токен бота. Если ``None``, берётся из переменной
                окружения ``MAX_BOT_TOKEN``.
            format: Формат текста по умолчанию: ``"markdown"`` или ``"html"``.
            log_level: Если задан — сразу включает логирование
                (см. :func:`maxapilib.enable_logging`).
            call_timeout: Сколько секунд ждать ответа MAX API
                в синхронных вызовах.
            skip_updates: Не обрабатывать события, случившиеся до запуска
                бота (полезно, чтобы не отвечать на старые сообщения).
            auto_check_subscriptions: Проверять при запуске, нет ли у бота
                вебхука (вебхук отключает поллинг).

        Raises:
            MaxApiLibAuthError: Если токен не найден.
            ValueError: Если токен или формат указаны неверно.
        """
        _check_token(token)

        if log_level is not None:
            enable_logging(log_level)

        self.maxapi = MaxApiBot(
            token=token,
            format=as_format(format),
            auto_check_subscriptions=auto_check_subscriptions,
        )
        self.dispatcher = Dispatcher(router_id="maxapilib")

        self._client = MaxApiClient(self.maxapi)
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

    @property
    def is_running(self) -> bool:
        """``True``, если поллинг бота работает."""
        thread = self._thread
        return thread is not None and thread.is_alive()

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

    def on_command(self, *commands: str, prefix: str = "/") -> Callable[[F], F]:
        """Декоратор: обработка команд вида ``/start``.

        Args:
            *commands: Команды без префикса: ``"start"``, ``"help"``.
            prefix: Префикс команды (по умолчанию ``"/"``).

        Example::

            @bot.on_command("start", "help")
            def handle(message):
                print(message.command, message.args)
        """
        return self._register(
            self.dispatcher.message_created,
            CommandFilter(commands, prefix=prefix),
            self._make_message_handler,
        )

    def on_text(self, pattern: str) -> Callable[[F], F]:
        """Декоратор: обработка сообщений, подходящих под регулярное выражение.

        Args:
            pattern: Регулярное выражение, которое ищется в тексте.

        Example::

            @bot.on_text(r"привет|здравствуй")
            def hello(message):
                message.reply("И вам привет!")
        """
        return self._register(
            self.dispatcher.message_created,
            TextPattern(pattern),
            self._make_message_handler,
        )

    def on_button(self, payload: str) -> Callable[[F], F]:
        """Декоратор: обработка нажатия кнопки с указанным ``payload``.

        Example::

            @bot.on_button("site")
            def site(callback):
                callback.answer("Открываю сайт")
        """
        return self._register(
            self.dispatcher.message_callback,
            CallbackPayload(payload),
            self._make_callback_handler,
        )

    def on_callback(self) -> Callable[[F], F]:
        """Декоратор: обработка любого нажатия inline-кнопки."""
        return self._register(
            self.dispatcher.message_callback, None, self._make_callback_handler
        )

    def on_message(self) -> Callable[[F], F]:
        """Декоратор: обработка любого входящего сообщения.

        Ставьте его последним: срабатывает первый подходящий обработчик.
        """
        return self._register(
            self.dispatcher.message_created, None, self._make_message_handler
        )

    def on_started(self) -> Callable[[F], F]:
        """Декоратор: пользователь запустил бота (нажал «Начать»)."""
        return self._register(
            self.dispatcher.bot_started, None, self._make_started_handler
        )

    def _register(
        self,
        event: Event,
        filter_: Any,
        wrap: Callable[[Callable[..., Any]], CoroHandler],
    ) -> Callable[[F], F]:
        """Общий код регистрации обработчика в диспетчере ``maxapi``."""
        self._ensure_not_running()

        def decorator(func: F) -> F:
            self._ensure_not_running()
            if inspect.iscoroutinefunction(func):
                message = (
                    f"Обработчик {getattr(func, '__name__', '')} объявлен "
                    "через async def, а MaxApiLib вызывает обычные функции. "
                    "Уберите async и await: вся асинхронность внутри "
                    "библиотеки."
                )
                raise MaxApiLibError(message)
            wrapper = wrap(func)
            if filter_ is None:
                event()(wrapper)
            else:
                event(filter_)(wrapper)
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
        """
        token = self._context.set(view)
        try:
            await asyncio.to_thread(func, view)
        finally:
            self._context.reset(token)

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

    def _target_from_context(self) -> tuple[int | None, int | None]:
        """Определить получателя по событию, которое сейчас обрабатывается."""
        view = self._context.get()
        if view is None:
            return None, None
        return view.chat_id, view.user_id

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
        if self.is_running:
            message = "Бот уже запущен: повторный вызов bot.run() не нужен."
            raise MaxApiLibError(message)

        self._fatal = None
        self._stop_requested.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="maxapilib-bot", daemon=True
        )
        self._thread.start()
        logger.info("Бот запускается. Для остановки нажмите Ctrl+C.")

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
            logger.warning("Поллинг не остановился за %.1f c", timeout)
            return

        self._thread = None
        logger.info("Бот остановлен")

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
        """Выполнить корутину в цикле поллинга и дождаться результата.

        Raises:
            MaxApiLibError: Если бот не запущен или вызов идёт из самого
                цикла событий.
            MaxApiLibTimeoutError: Если ответа нет дольше ``call_timeout``.
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            coro.close()
            message = (
                "Бот не запущен: вызовите bot.run() (или run(blocking=False)) "
                "перед отправкой сообщений."
            )
            raise MaxApiLibError(message)

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


def _rename(handler: CoroHandler, source: Callable[..., Any]) -> None:
    """Дать обёртке имя пользовательской функции (для логов maxapi)."""
    setattr(handler, "__name__", getattr(source, "__name__", "handler"))  # noqa: B010


def _running_loop() -> asyncio.AbstractEventLoop | None:
    """Вернуть цикл событий текущего потока, если он запущен."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None
