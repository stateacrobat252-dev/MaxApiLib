import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Any
from .exceptions import MaxBotEasyError, MaxBotEasyAPIError, MaxBotEasyNetworkError
from .types import Button, TextBox
from .client import MaxBotClient

logger = logging.getLogger("maxbot_easy")

class Bot:
    """Основной класс для управления ботом."""
    def __init__(self, token: str):
        if not token or len(token) < 10:
            raise ValueError(
                "Некорректный токен бота. Убедитесь, что вы передали валидный токен."
            )
        
        self.token = token
        self.is_running = False
        self.handlers: Dict[str, Callable] = {}
        self._client = MaxBotClient(token)
        self._loop = None

    def on_text(self, pattern: str) -> Callable:
        """Декоратор для обработки текстовых сообщений."""
        def decorator(func: Callable) -> Callable:
            self.handlers[f'text:{pattern}'] = func
            return func
        return decorator

    def on_button(self, payload: str) -> Callable:
        """Декоратор для обработки нажатий кнопок."""
        def decorator(func: Callable) -> Callable:
            self.handlers[f'button:{payload}'] = func
            return func
        return decorator

    def send(
        self, 
        content: TextBox, 
        chat_id: Optional[int] = None, 
        user_id: Optional[int] = None
    ) -> None:
        """Отправка сообщения пользователю (синхронно)."""
        if self._loop and self._loop.is_running():
            import asyncio
            asyncio.run_coroutine_threadsafe(
                self._client.send_message(content), self._loop
            )
        else:
            logger.error("Цикл событий бота не запущен.")

    def reply(self, message: Any, content: TextBox) -> None:
        """Ответ на полученное сообщение (синхронно)."""
        if self._loop and self._loop.is_running():
            import asyncio
            asyncio.run_coroutine_threadsafe(
                self._client.reply(message, content), self._loop
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
        \"\"\"Остановка бота.\"\"\"
        self.is_running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("Остановка бота...")
