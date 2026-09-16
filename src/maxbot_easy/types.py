from typing import Any


class Button:
    """Объект кнопки взаимодействия с пользователем."""
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
        return cls(text=text, payload=payload)

    @classmethod
    def link(cls, text: str, url: str) -> 'Button':
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(
                f"Некорректный URL: {url!r}. "
                "Должен начинаться с http:// или https://"
            )
        return cls(text=text, url=url)

    @classmethod
    def contact(cls) -> 'Button':
        return cls(text="Отправить контакт")

    @classmethod
    def location(cls) -> 'Button':
        return cls(text="Отправить геолокацию")

    @classmethod
    def chat(cls, text: str, title: str, description: str = "") -> 'Button':
        return cls(text=text, title=title, description=description)

    def to_dict(self) -> dict[str, Any]:
        """Сериализация для MAX API."""
        return {
            "text": self.text,
            "payload": self.payload,
            "url": self.url,
            "title": self.title,
            "description": self.description,
        }

class TextBox:
    """Сообщение с текстом и кнопками."""
    def __init__(self, text: str):
        self.text = text
        self.rows: list[list[Button]] = []

    def row(self, *buttons: Button) -> 'TextBox':
        self.rows.append(list(buttons))
        return self

    def add(self, button: Button) -> 'TextBox':
        if not self.rows:
            self.rows.append([button])
            return self
        
        for row in self.rows:
            if len(row) < 5:
                row.append(button)
                return self
        
        self.rows.append([button])
        return self

    def button(self, text: str, payload: str) -> 'TextBox':
        btn = Button.callback(text, payload)
        return self.add(btn)

    def to_attachments(self) -> list[dict[str, Any]] | None:
        """Превращает TextBox в формат данных для отправки сообщения."""
        if not self.rows:
            return None

        keyboard = []
        for row in self.rows:
            row_buttons = []
            for btn in row:
                btn_dict = btn.to_dict()
                # В MAX API для кнопок callback используется callback_data
                if btn.payload:
                    btn_dict["callback_data"] = btn.payload
                    btn_dict.pop("payload", None)
                row_buttons.append(btn_dict)
            keyboard.append(row_buttons)

        return [{"inline_keyboard": keyboard}]
