from typing import Any


class MaxBotEasyError(Exception):
    """Базовое исключение для maxbot-easy."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details

class MaxBotEasyAPIError(MaxBotEasyError):
    """Ошибка взаимодействия с API."""
    pass

class MaxBotEasyNetworkError(MaxBotEasyError):
    """Ошибка сетевого соединения."""
    pass
