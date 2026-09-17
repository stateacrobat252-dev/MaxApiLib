"""Эхо-бот на MaxApiLib: минимальный рабочий пример.

Перед запуском задайте токен бота в переменной окружения
``MAX_BOT_TOKEN`` (токен выдаёт @MasterBot в MAX)::

    set MAX_BOT_TOKEN=ваш_токен      # Windows
    export MAX_BOT_TOKEN=ваш_токен   # Linux/macOS

Затем запустите файл::

    python examples/echo_bot.py
"""

from maxapilib import Bot, Button, TextBox, enable_logging

# Bot() возьмёт токен из переменной окружения MAX_BOT_TOKEN.
# Можно передать явно: Bot("ваш_токен").
bot = Bot()


@bot.on_started()
def hello(event):
    """Пользователь нажал «Начать» в профиле бота."""
    box = TextBox("Привет! Я эхо-бот на MaxApiLib.")
    box.row(
        Button.callback("Что я умею", "help"),
        Button.link("Документация MAX", "https://dev.max.ru/docs-api"),
    )
    event.send(box)


@bot.on_command("start", "help")
def help_command(message):
    """Команды /start и /help."""
    message.reply(
        "Напишите любое сообщение — я повторю его. "
        "Или нажмите кнопку «Что я умею»."
    )


@bot.on_button("help")
def help_button(callback):
    """Нажатие inline-кнопки с payload «help»."""
    callback.answer("Отправляю подсказку")  # убирает «часики» с кнопки
    callback.send("Умею: /start, /help и повторять любой текст.")


@bot.on_text(r"привет|здравствуй")
def greet(message):
    """Текст по регулярному выражению."""
    message.reply("И вам привет!")


@bot.on_message()
def echo(message):
    """Всё остальное — эхо. Срабатывает, если ничего выше не совпало."""
    message.reply(f"Вы написали: {message.text}")


if __name__ == "__main__":
    enable_logging()  # видно, что происходит: INFO в консоли
    bot.run()  # блокирует поток до Ctrl+C
