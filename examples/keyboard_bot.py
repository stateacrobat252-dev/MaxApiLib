"""Все типы кнопок MAX в одном сообщении.

Полезно, чтобы посмотреть, как выглядят разные кнопки, и проверить,
что нажатия доходят до бота.

Запуск::

    set MAX_BOT_TOKEN=ваш_токен      # Windows
    python examples/keyboard_bot.py
"""

from maxapilib import Bot, Button, TextBox, parse_time

bot = Bot()


@bot.on_command("start", "keyboard")
def show_keyboard(message):
    """Показать клавиатуру со всеми типами кнопок."""
    box = TextBox("Примеры кнопок MAX:")
    box.row(
        Button.callback("Callback", "callback_demo"),
        Button.message("Отправить текст"),
        Button.clipboard("Скопировать промокод", "MAX-2026"),
    )
    box.row(
        Button.link("Сайт MAX", "https://max.ru"),
        Button.contact(),
        Button.location(),
    )
    message.reply(box)


@bot.on_button("callback_demo")
def callback_demo(callback):
    """Нажатие обычной callback-кнопки."""
    callback.answer("Кнопка работает!")
    callback.send(f"Payload кнопки: {callback.payload}")


@bot.on_callback()
def other_buttons(callback):
    """Остальные callback-кнопки (например, из мини-приложений)."""
    callback.answer(f"Получен payload: {callback.payload}")


@bot.on_message()
def fallback(message):
    """Текстовые кнопки и всё остальное приходит как обычное сообщение."""
    message.reply(
        f"Пришло сообщение: {message.text!r}. "
        "Команды: /start, /keyboard"
    )


if __name__ == "__main__":
    # Пример использования parse_time в подсказке:
    print("Подсказка: можно писать интервалы вида 10s, 5m, 1h, 1d")
    print("parse_time('2m') =", parse_time("2m"), "секунд")
    bot.run()
