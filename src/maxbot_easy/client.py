import logging
import sys
from pathlib import Path
from typing import Any

from .exceptions import MaxBotEasyAPIError

# Добавляем путь к локальной библиотеке maxapi, если он не найден
if not Path("maxapi").exists():
    sys.path.append(str(Path().resolve()))

try:
    from maxapi.maxapi.bot import Bot as MaxBot
except ImportError:
    logger = logging.getLogger("maxbot_easy.client")
    logger.error("Не удалось импортировать maxapi. Убедитесь, что библиотека доступна.")
    raise

logger = logging.getLogger("maxbot_easy.client")

class MaxBotClient:
    """Обертка над стандартным maxapi.Bot."""
    def __init__(self, token: str):
        self.bot = MaxBot(token)

    async def send_message(self, content: Any) -> None:
        try:
            await self.bot.send_message(content)
        except Exception as e:
            logger.error(f"Ошибка при отправке: {e}")
            raise MaxBotEasyAPIError(f"Ошибка API: {e}") from e

    async def reply(self, message: Any, content: Any) -> None:
        try:
            await self.bot.reply(message, content)
        except Exception as e:
            logger.error(f"Ошибка при ответе: {e}")
            raise MaxBotEasyAPIError(f"Ошибка API: {e}") from e
