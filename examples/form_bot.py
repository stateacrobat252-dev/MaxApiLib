"""Анкета на состояниях (FSM) и данных пользователя.

Бот спрашивает имя и город и запоминает ответы.

Команды:
    /start — начать (или начать заново);
    /me    — что бот о вас знает.

Запуск::

    set MAX_BOT_TOKEN=ваш_токен      # Windows
    python examples/form_bot.py
"""

from maxapilib import Bot, Button, TextBox

bot = Bot()


@bot.on_command("start", "reset")
def start(message):
    """Вход в анкету: сбрасываем прошлое и ждём имя."""
    bot.reset_state(message)  # забыть старые ответы
    bot.set_state(message, "waiting_name")  # запомнить состояние
    message.reply("Как вас зовут?")


@bot.on_state("waiting_name")
def ask_city(message):
    """Сработает только пока бот ждёт имя."""
    bot.set_data(message, name=message.text)  # сохранили ответ
    bot.set_state(message, "waiting_city")
    message.reply(f"Приятно познакомиться, {message.text}! Из какого вы города?")


@bot.on_state("waiting_city")
def finish(message):
    """Последний шаг анкеты."""
    bot.set_data(message, city=message.text)
    data = bot.get_data(message)  # {'name': '...', 'city': '...'}
    bot.reset_state(message)  # вышли из анкеты

    box = TextBox(
        f"Записал: {data['name']} из города {data['city']}.\n"
        "Спасибо! Можете начать заново."
    )
    box.row(Button.callback("Заполнить заново", "restart"))
    message.reply(box)


@bot.on_command("me")
def show_data(message):
    """Показать, что бот о вас помнит."""
    data = bot.get_data(message)
    if not data:
        message.reply("Пока ничего не знаю. Начните с /start")
        return

    facts = ", ".join(f"{key}: {value}" for key, value in data.items())
    message.reply(f"Я о вас знаю — {facts}")


@bot.on_button("restart")
def restart(callback):
    """Кнопка из последнего сообщения: начать анкету заново."""
    callback.answer("Начинаем заново")
    bot.reset_state(callback)
    bot.set_state(callback, "waiting_name")
    callback.send("Как вас зовут?")


@bot.on_message()
def fallback(message):
    """Всё остальное — подсказка."""
    message.reply("Не понял. Напишите /start, чтобы заполнить анкету.")


if __name__ == "__main__":
    bot.run()
