from typing import Any


class MaxBotEasyError(Exception):
    """Базовое исключение для библиотеки maxbot-easy."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details

class MaxBotEasyAPIError(MaxBotEasyError):
    """Ошибка API при взаимодействии с MAX Bot."""
    pass

class MaxBotEasyNetworkError(MaxBotEasyError):
    """Ошибка сети при попытке соединения с MAX Bot."""
    pass
