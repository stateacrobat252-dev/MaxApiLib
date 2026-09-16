import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from .client import MaxBotClient
from .types import TextBox

logger = logging.getLogger("maxbot_easy")

class Bot:
    """Основной класс для управления ботом."""
    def __init__(self, token: str):
        if not token or len(token) < 10:
            raise ValueError("Некорректный токен бота. Убедитесь, что вы передали валидный токен.")

        self.token = token
        self.is_running = False
        self.handlers: dict[str, Callable] = {}
        self._client = MaxBotClient(token)
        self._loop = None

    def on_text(self, pattern: str) -> Callable:
        """Декоратор для обработки текстовых сообщений (поддерживает регулярные выражения)."""
        def decorator(func: Callable):
            self.handlers[f'text:{pattern}'] = func
            return func
        return decorator

    def on_button(self, payload: str) -> Callable:
        """Декоратор для обработки нажатий кнопок по payload."""
        def decorator(func: Callable):
            self.handlers[f'button:{payload}'] = func
            return func
        return decorator

    def on_message(self) -> Callable:
        """Декоратор для обработки всех входящих сообщений."""
        def decorator(func: Callable):
            self.handlers[f'message:all'] = func
            return func
        return decorator

    def send(self, content: TextBox, chat_id: int | None = None, user_id: int | None = None) -> None:
        """Отправка сообщения пользователю (синхронно)."""
        attachments = content.to_attachments()
        if self._loop and self._loop.is_running():
            import asyncio
            # If content has attachments, we might need to pass them separately depending on maxapi
            # For now, we pass the content object which should handle its own serialization
            asyncio.run_coroutine_threadsafe(
                self._client.send_message(content, attachments=attachments), self._loop
            )
        else:
            logger.error("Цикл событий бота не запущен.")

    def reply(self, message: Any, content: TextBox) -> None:
        """Ответ на полученное сообщение (синхронно)."""
        attachments = content.to_attachments()
        if self._loop and self._loop.is_running():
            import asyncio
            asyncio.run_coroutine_threadsafe(
                self._client.reply(message, content, attachments=attachments), self._loop
            )
        else:
            logger.error("Цикл событий бота не запущен.")

    def run(self) -> None:
        """Запуск основного цикла бота в отдельном потоке."""
        self.is_running = True
        logger.info("Запуск бота...")

        def _run_loop():
            import asyncio
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            # Здесь будет логика polling
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        time.sleep(1)

    def stop(self) -> None:
        """Остановка бота."""
        self.is_running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("Остановка бота...")
