"""Таймеры в MaxApiLib: later() и every().

Бот напоминает о себе по расписанию и по команде.

Запуск::

    set MAX_BOT_TOKEN=ваш_токен      # Windows
    python examples/timer_bot.py
"""

from maxapilib import Bot, Timer, every, humanize_delay, later, parse_time

bot = Bot()

#: Активный циклический таймер напоминаний (если он запущен).
reminder: Timer | None = None


@bot.on_command("start", "help")
def help_command(message):
    """Подсказка по командам."""
    message.reply(
        "Команды:\n"
        "/timer 10s — напомнить через 10 секунд (s, m, h, d)\n"
        "/every 60s — напоминать каждые 60 секунд\n"
        "/stop — выключить напоминания"
    )


@bot.on_command("timer")
def timer_command(message):
    """Одноразовое напоминание: /timer 10s."""
    seconds = parse_time(message.args[0]) if message.args else 0.0
    if seconds <= 0:
        message.reply("Укажите время, например: /timer 10s или /timer 2m")
        return

    message.reply(f"Напомню через {humanize_delay(seconds)}.")
    # message.send запомнит чат: таймер сработает уже вне обработчика.
    later(seconds, lambda: message.send("Напоминаю!"))


@bot.on_command("every")
def every_command(message):
    """Циклические напоминания: /every 60s."""
    global reminder

    seconds = parse_time(message.args[0]) if message.args else 0.0
    if seconds <= 0:
        message.reply("Укажите интервал, например: /every 60s")
        return

    if reminder is not None:
        reminder.cancel()

    reminder = every(seconds, lambda: message.send("Прошёл ещё один интервал."))
    message.reply(
        f"Буду напоминать каждые {humanize_delay(seconds)}. "
        "Остановить: /stop"
    )


@bot.on_command("stop")
def stop_command(message):
    """Остановка напоминаний."""
    global reminder

    if reminder is None:
        message.reply("Напоминания и не были включены.")
        return

    reminder.cancel()
    reminder = None
    message.reply("Напоминания выключены.")


if __name__ == "__main__":
    bot.run()
