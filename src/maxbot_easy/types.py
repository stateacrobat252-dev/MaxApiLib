from typing import Any


class Button:
    """Представление кнопки в интерфейсе бота."""
    def __init__(
        self,
        text: str,
        payload: str | None = None,
        url: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ):
        self.text = text
        self.payload = payload
        self.url = url
        self.title = title
        self.description = description

    @classmethod
    def callback(cls, text: str, payload: str) -> 'Button':
        """Создает кнопку обратного вызова (callback)."""
        return cls(text=text, payload=payload)

    @classmethod
    def link(cls, text: str, url: str) -> 'Button':
        """Создает кнопку-ссылку."""
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(
                "Ссылка должна начинаться с http:// или https://. "
                f"Пример: Button.link('Сайт', 'https://max.ru'). "
                f"Ты передал: {url!r}"
            )
        return cls(text=text, url=url)

    @classmethod
    def contact(cls) -> 'Button':
        """Создает кнопку отправки контакта."""
        return cls(text="Отправить контакт")

    @classmethod
    def location(cls) -> 'Button':
        """Создает кнопку отправки геолокации."""
        return cls(text="Отправить геолокацию")

    @classmethod
    def chat(cls, text: str, title: str, description: str = "") -> 'Button':
        """Создает кнопку перехода в чат."""
        return cls(text=text, title=title, description=description)

    def to_dict(self) -> dict[str, Any]:
        """Преобразует объект кнопки в словарь формата MAX API."""
        return {
            "text": self.text,
            "payload": self.payload,
            "url": self.url,
            "title": self.title,
            "description": self.description,
        }

class TextBox:
    """Сообщение с текстом и цепочкой кнопок."""
    def __init__(self, text: str):
        self.text = text
        self.rows: list[list[Button]] = []

    def row(self, *buttons: Button) -> 'TextBox':
        """Добавляет новый ряд кнопок."""
        self.rows.append(list(buttons))
        return self

    def add(self, button: Button) -> 'TextBox':
        """Добавляет кнопку в первый доступный ряд."""
        if not self.rows:
            self.rows.append([button])
        else:
            for row in self.rows:
                if len(row) < 5:  # MAX API limit
                    row.append(button)
                    break
        return self

    def button(self, text: str, payload: str) -> 'TextBox':
        """Быстрое создание кнопки и добавление в текст (упрощенно)."""
        # Note: This is a helper for easy building
        btn = Button.callback(text, payload)
        return self.add(btn)

    def to_attachments(self) -> list[dict[str, Any]] | None:
        """Преобразует TextBox в формат MAX API для вложений (attachments)."""
        # Внутренняя реализация, скрытая от пользователя
        # Для начала вернем пустой список или структуру для отладки
        return None

