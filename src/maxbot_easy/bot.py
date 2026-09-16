import asyncio
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Any

from .client import MaxBotClient
from .types import TextBox

logger = logging.getLogger("maxbot_easy")

class Bot:
    """Основной класс для управления ботом.

    Позволяет создавать обработчики событий, отправлять сообщения
    и запускать основной цикл работы бота.
    """
    def __init__(self, token: str):
        if not token or len(token) < 10:
            raise ValueError(
                "Некорректный токен бота. "
                "Убедитесь, что вы передали валидный токен."
            )

        self.token = token
        self.is_running = False
        self.handlers: list[tuple[str, Callable[..., Any]]] = []
        self._client = MaxBotClient(token)
        self._loop: asyncio.AbstractEventLoop | None = None
        self.marker_updates: str | None = None

    def on_text(self, pattern: str) -> Callable[..., Any]:
        """Декоратор для обработки текстовых сообщений.
        Поддерживает регулярные выражения.
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers.append((f'text:{pattern}', func))
            return func
        return decorator

    def on_button(self, payload: str) -> Callable[..., Any]:
        """Декоратор для обработки нажатий кнопок по payload."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers.append((f'button:{payload}', func))
            return func
        return decorator

    def on_message(self) -> Callable[..., Any]:
        """Декоратор для обработки всех входящих сообщений."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers.append(('message:all', func))
            return func
        return decorator

    def send(
        self, content: TextBox, chat_id: int | None = None, user_id: int | None = None
    ) -> None:
        """Отправка сообщения пользователю (синхронно)."""
        attachments = content.to_attachments()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._client.send_message(content.text, attachments=attachments),
                self._loop
            )
        else:
            logger.error("Цикл событий бота не запущен.")

    def reply(self, message: Any, content: TextBox) -> None:
        """Ответ на полученное сообщение (синхронно)."""
        attachments = content.to_attachments()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._client.reply(message, content.text, attachments=attachments),
                self._loop
            )
        else:
            logger.error("Цикл событий бота не запущен.")

    def run(self) -> None:
        """Запуск основного цикла бота в отдельном потоке."""
        self.is_running = True
        logger.info("Запуск бота...")

        def _run_loop() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def poll() -> None:
                while self.is_running:
                    try:
                        updates = await self._client.get_updates()
                        for update in updates:
                            self._handle_update(update)
                    except Exception as e:
                        logger.error(f"Ошибка при получении обновлений: {e}")
                        await asyncio.sleep(5)
                    await asyncio.sleep(1)

            self._loop.create_task(poll())
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        time.sleep(1)

    def _handle_update(self, update: Any) -> None:
        """Внутренний обработчик обновлений."""
        if hasattr(update, 'message') and update.message:
            msg = update.message
            text = getattr(msg, 'text', '')

            for handler_key, func in self.handlers:
                if handler_key.startswith('text:'):
                    pattern = handler_key.replace('text:', '')
                    if re.search(pattern, text):
                        func(msg)
                        return
                elif handler_key == 'message:all':
                    func(msg)
                    return

        elif hasattr(update, 'callback_query') and update.callback_query:
            cq = update.callback_query
            payload = getattr(cq, 'data', '')

            for handler_key, func in self.handlers:
                if handler_key.startswith('button:'):
                    pattern = handler_key.replace('button:', '')
                    if pattern == payload:
                        func(cq)
                        return
                elif handler_key == 'message:all':
                    func(cq)
                    return

    def stop(self) -> None:
        """Остановка бота."""
        self.is_running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("Остановка бота...")
