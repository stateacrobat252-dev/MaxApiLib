import os

from maxbot_easy import Bot, TextBox, every, later

TOKEN = os.getenv("MAXBOT_TOKEN", "YOUR_TOKEN_HERE")
bot = Bot(token=TOKEN)

@bot.on_text("/timer")
def timer_command():
    bot.send(TextBox(
        "Введите время (например, 10s, 5m), "
        "и я пришлю вам сообщение через это время."
    ))

@bot.on_text("/every")
def every_command():
    # Пример использования every() для отправки сообщений каждые 60 секунд
    # В реальном боте это лучше вызывать один раз при запуске
    every(60, lambda: bot.send(TextBox("Это сообщение отправляется каждую минуту!")))
    bot.send(TextBox("Настроен цикл отправки сообщений каждую минуту."))

@bot.on_text("/delayed")
def delayed_command():
    # Пример использования later()
    # Поскольку мы не знаем точный ввод, просто отправим через 10 секунд
    bot.send(TextBox("Я пришлю вам сообщение через 10 секунд..."))
    later(10, lambda: bot.send(TextBox("Прошло 10 секунд!")))

if __name__ == "__main__":
    bot.run()
