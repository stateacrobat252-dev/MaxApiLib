from typing import Any

from maxapi.bot import Bot as MaxBot

from .exceptions import MaxBotEasyAPIError


class MaxBotClient:
    """Обертка над стандартным maxapi.Bot."""
    def __init__(self, token: str):
        self.bot = MaxBot(token)

    async def send_message(
        self, content: Any, attachments: Any = None
    ) -> None:
        try:
            await self.bot.send_message(content, attachments=attachments)
        except Exception as e:
            raise MaxBotEasyAPIError(
                f"Ошибка API при отправке сообщения: {e}"
            ) from e

    async def reply(
        self, message: Any, content: Any, attachments: Any = None
    ) -> None:
        try:
            if hasattr(self.bot, 'reply'):
                await self.bot.reply(message, content, attachments=attachments)
            else:
                await self.bot.send_message(content, attachments=attachments)
        except Exception as e:
            raise MaxBotEasyAPIError(
                f"Ошибка API при ответе: {e}"
            ) from e

    async def get_updates(self) -> Any:
        try:
            return await self.bot.get_updates()
        except Exception as e:
            raise MaxBotEasyAPIError(f"Ошибка API при получении обновлений: {e}") from e
