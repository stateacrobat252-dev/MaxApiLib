"""Тесты кнопок, клавиатуры и событий бота."""

from __future__ import annotations

from typing import Any

import pytest
from maxapi.enums.intent import Intent
from maxapi.types.updates import UpdateUnionAdapter

from maxapilib import Button, Callback, Message, TextBox
from maxapilib.types import (
    MAX_BUTTONS_PER_ROW,
    MAX_KEYBOARD_BUTTONS,
    MAX_KEYBOARD_ROWS,
    callback_from_update,
    message_from_update,
    started_from_update,
    text_of,
)

from .helpers import bot_started, message_callback, message_created


class FakeBot:
    """Заглушка бота: запоминает вызовы отправки."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def send(self, content: Any, **kwargs: Any) -> None:
        """Записать вызов send."""
        self.calls.append(("send", (content,), kwargs))

    def reply(self, message: Any, content: Any, **kwargs: Any) -> None:
        """Записать вызов reply."""
        self.calls.append(("reply", (message, content), kwargs))

    def answer_callback(
        self, callback_id: Any, text: Any = None, **kwargs: Any
    ) -> None:
        """Записать вызов answer_callback."""
        self.calls.append(("answer", (callback_id, text), kwargs))


def parsed(raw: dict[str, Any]) -> Any:
    """Разобрать сырое событие так, как это делает maxapi."""
    return UpdateUnionAdapter.validate_python(raw)


# ----------------------------------------------------------------------
# Кнопки
# ----------------------------------------------------------------------


def test_callback_button_format() -> None:
    button = Button.callback("Кнопка", "go")
    assert button.to_dict() == {"type": "callback", "text": "Кнопка", "payload": "go"}
    assert button.text == "Кнопка"
    assert button.type == "callback"
    assert button.payload == "go"
    assert button.url is None
    assert not button.is_narrow


def test_callback_button_intent() -> None:
    button = Button.callback("Кнопка", "go", intent=Intent.POSITIVE)
    assert button.to_dict()["intent"] == "positive"


def test_link_button_format() -> None:
    button = Button.link("Сайт", "https://example.com")
    assert button.to_dict() == {
        "type": "link",
        "text": "Сайт",
        "url": "https://example.com",
    }
    assert button.url == "https://example.com"
    assert button.is_narrow


def test_link_button_invalid_url() -> None:
    with pytest.raises(ValueError, match="должна начинаться"):
        Button.link("Сайт", "example.com")


def test_button_text_validation() -> None:
    with pytest.raises(ValueError, match="не может быть пустым"):
        Button.callback("   ", "go")
    with pytest.raises(ValueError, match="длиннее 64"):
        Button.callback("к" * 65, "go")


def test_button_payload_validation() -> None:
    with pytest.raises(ValueError, match="длиннее 256"):
        Button.callback("Кнопка", "p" * 257)


def test_other_button_types() -> None:
    assert Button.message("echo").to_dict() == {"type": "message", "text": "echo"}
    assert Button.clipboard("Скопировать", "1234").to_dict() == {
        "type": "clipboard",
        "text": "Скопировать",
        "payload": "1234",
    }
    assert Button.contact().to_dict() == {
        "type": "request_contact",
        "text": "Отправить контакт",
    }
    assert Button.location().to_dict() == {
        "type": "request_geo_location",
        "text": "Отправить геолокацию",
        "quick": False,
    }
    assert Button.open_app("Открыть", web_app="my_app").to_dict() == {
        "type": "open_app",
        "text": "Открыть",
        "web_app": "my_app",
    }


def test_open_app_requires_target() -> None:
    with pytest.raises(ValueError, match="web_app или contact_id"):
        Button.open_app("Открыть")


def test_button_repr() -> None:
    assert repr(Button.callback("Кнопка", "go")) == "<Button callback 'Кнопка'>"


# ----------------------------------------------------------------------
# Клавиатура
# ----------------------------------------------------------------------


def test_textbox_validation() -> None:
    with pytest.raises(ValueError, match="не может быть пустым"):
        TextBox("  ")
    with pytest.raises(ValueError, match="длиннее 4000"):
        TextBox("т" * 4001)


def test_textbox_row_and_add() -> None:
    box = TextBox("Меню")
    box.row(Button.callback("A", "a"), Button.callback("B", "b"))
    box.add(Button.callback("C", "c"))
    assert [button.text for row in box.rows for button in row] == ["A", "B", "C"]
    assert box.buttons_count == 3


def test_textbox_add_packs_rows() -> None:
    box = TextBox("Меню")
    for index in range(MAX_BUTTONS_PER_ROW + 1):
        box.add(Button.callback(f"B{index}", f"p{index}"))
    assert len(box.rows) == 2
    assert len(box.rows[0]) == MAX_BUTTONS_PER_ROW
    assert len(box.rows[1]) == 1


def test_textbox_narrow_button_needs_own_row() -> None:
    box = TextBox("Меню")
    for index in range(3):
        box.add(Button.link(f"L{index}", "https://example.com"))
    box.add(Button.link("L3", "https://example.com"))
    assert len(box.rows) == 2
    assert len(box.rows[0]) == 3


def test_textbox_button_helper() -> None:
    box = TextBox("Меню").button("Кнопка", "payload")
    assert box.rows[0][0].payload == "payload"


def test_textbox_row_validation() -> None:
    box = TextBox("Меню")
    with pytest.raises(ValueError, match="Ряд не может быть пустым"):
        box.row()
    with pytest.raises(ValueError, match="не более 7"):
        box.row(*[Button.callback(f"B{i}", f"p{i}") for i in range(8)])
    with pytest.raises(ValueError, match="не более 3"):
        box.row(*[Button.link(f"L{i}", "https://example.com") for i in range(4)])


def test_textbox_row_limit() -> None:
    box = TextBox("Меню")
    for _ in range(MAX_KEYBOARD_ROWS):
        box.row(Button.callback("B", "p"))

    with pytest.raises(ValueError, match=f"не более {MAX_KEYBOARD_ROWS} рядов"):
        box.row(Button.callback("B", "p"))


def test_textbox_add_after_row_limit() -> None:
    box = TextBox("Меню")
    for _ in range(MAX_KEYBOARD_ROWS):
        # Ряды из трёх «широких» кнопок: место в них уже не остаётся.
        box.row(
            Button.link("L", "https://example.com"),
            Button.link("L", "https://example.com"),
            Button.link("L", "https://example.com"),
        )

    with pytest.raises(ValueError, match=f"не более {MAX_KEYBOARD_ROWS} рядов"):
        box.add(Button.callback("B", "p"))


def test_open_app_with_contact_id() -> None:
    button = Button.open_app("Открыть", contact_id=777, payload="promo")
    assert button.to_dict() == {
        "type": "open_app",
        "text": "Открыть",
        "contact_id": 777,
        "payload": "promo",
    }


def test_location_quick() -> None:
    assert Button.location(quick=True).to_dict()["quick"] is True


def test_text_of_without_message() -> None:
    assert text_of(None) is None


def test_text_of_message_without_text() -> None:
    update = parsed(message_created(""))
    assert text_of(update.message) == ""  # type: ignore[union-attr]
    assert message_from_update(update, FakeBot()).text == ""  # type: ignore[arg-type]


def test_textbox_button_limit() -> None:
    box = TextBox("Меню")
    for _ in range(MAX_KEYBOARD_ROWS):
        box.row(*[Button.callback("B", "p")] * MAX_BUTTONS_PER_ROW)

    assert box.buttons_count == MAX_KEYBOARD_BUTTONS
    with pytest.raises(ValueError, match=f"не более {MAX_KEYBOARD_BUTTONS} кнопок"):
        box.add(Button.callback("B", "p"))


def test_textbox_to_attachments_matches_max_format() -> None:
    box = TextBox("Меню")
    box.row(Button.callback("Кнопка", "go"), Button.link("Сайт", "https://example.com"))

    attachments = box.to_attachments()
    assert attachments is not None
    assert attachments[0].model_dump(mode="json", exclude_none=True) == {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [
                    {
                        "type": "callback",
                        "text": "Кнопка",
                        "payload": "go",
                        # maxapi подставляет значение по умолчанию
                        "intent": "default",
                    },
                    {
                        "type": "link",
                        "text": "Сайт",
                        "url": "https://example.com",
                    },
                ]
            ]
        },
    }


def test_textbox_to_attachments_without_buttons() -> None:
    assert TextBox("Текст").to_attachments() is None
    assert TextBox("Текст").to_dict() == {"text": "Текст"}


def test_textbox_to_dict() -> None:
    box = TextBox("Меню").button("Кнопка", "go")
    assert box.to_dict() == {
        "text": "Меню",
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "callback",
                                "text": "Кнопка",
                                "payload": "go",
                                "intent": "default",
                            }
                        ]
                    ]
                },
            }
        ],
    }
    assert repr(box) == "<TextBox 'Меню' rows=1>"


# ----------------------------------------------------------------------
# События
# ----------------------------------------------------------------------


def test_message_view() -> None:
    bot = FakeBot()
    update = parsed(message_created("/echo привет мир"))
    message = message_from_update(update, bot)  # type: ignore[arg-type]

    assert isinstance(message, Message)
    assert message.text == "/echo привет мир"
    assert message.chat_id == 100
    assert message.user_id == 42
    assert message.message_id == "mid.1"
    assert message.command == "echo"
    assert message.args == ["привет", "мир"]


def test_message_view_without_command() -> None:
    bot = FakeBot()
    message = message_from_update(parsed(message_created("привет")), bot)  # type: ignore[arg-type]
    assert message.command is None
    assert message.args == []


def test_message_reply_and_send() -> None:
    bot = FakeBot()
    message = message_from_update(parsed(message_created("привет")), bot)  # type: ignore[arg-type]

    message.reply("ответ")
    message.send("просто сообщение")

    assert bot.calls[0][0] == "reply"
    assert bot.calls[0][1][1] == "ответ"
    assert bot.calls[1][0] == "send"
    assert bot.calls[1][2]["chat_id"] == 100


def test_callback_view() -> None:
    bot = FakeBot()
    update = parsed(message_callback("go", callback_id="cb-7"))
    callback = callback_from_update(update, bot)  # type: ignore[arg-type]

    assert isinstance(callback, Callback)
    assert callback.payload == "go"
    assert callback.callback_id == "cb-7"
    assert callback.chat_id == 100
    assert callback.user_id == 42
    assert callback.message is not None
    assert callback.message.text == "Меню"


def test_callback_answer_and_send() -> None:
    bot = FakeBot()
    callback = callback_from_update(parsed(message_callback("go")), bot)  # type: ignore[arg-type]

    callback.answer("Готово", notification="Уведомление")
    callback.send("Новое сообщение")

    assert bot.calls[0][0] == "answer"
    assert bot.calls[0][1] == ("cb-1", "Готово")
    assert bot.calls[0][2]["notification"] == "Уведомление"
    assert bot.calls[1][2]["chat_id"] == 100


def test_started_view() -> None:
    bot = FakeBot()
    started = started_from_update(parsed(bot_started(payload="promo")), bot)  # type: ignore[arg-type]

    assert started.chat_id == 100
    assert started.user_id == 42
    assert started.payload == "promo"

    started.send("Привет!")
    assert bot.calls[0][2]["chat_id"] == 100
