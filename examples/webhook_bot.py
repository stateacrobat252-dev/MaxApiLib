"""Бот на вебхуке (так рекомендует MAX для продакшена).

Что нужно для запуска:
    1. Сервер, доступный из интернета по HTTPS, например
       ``https://bot.example.com/hook`` — этот адрес укажите в URL ниже.
    2. Токен бота в переменной окружения MAX_BOT_TOKEN.
    3. Запуск: python examples/webhook_bot.py

Подписка на вебхук оформляется автоматически. Дополнительно сервер отдаёт
адреса для мониторинга:
    GET /health — бот жив;
    GET /stats  — счётчики (события, отправленные сообщения, ошибки).

Остановить: Ctrl+C. После остановки бот печатает итоговую статистику.
"""

from maxapilib import Bot, Message

#: Замените на свой HTTPS-адрес: именно по нему MAX будет присылать события.
URL = "https://bot.example.com/hook"

#: Ваш user_id в MAX: сюда бот напишет, если в обработчике случится ошибка.
#: Узнать его можно из логов бота (строка «сообщение от <user_id>»).
ADMIN_ID: int | None = None

bot = Bot(log_file="bot.log", admin_id=ADMIN_ID)


@bot.on_started()
def hello(event) -> None:
    """Пользователь запустил бота."""
    event.send("Привет! Я работаю через вебхук.")


@bot.on_command("start", "help")
def help_command(message: Message) -> None:
    message.reply("Напишите что-нибудь — отвечу эхом.")


@bot.on_message()
def echo(message: Message) -> None:
    message.reply(f"Вы написали: {message.text}")


@bot.on_error()
def report_error(error) -> None:
    """Сюда попадают ошибки из обработчиков (бот при этом продолжает работу)."""
    print("Ошибка в обработчике:", error.text)


if __name__ == "__main__":
    print(f"Вебхук: {URL}")
    print("Мониторинг: /health и /stats на том же адресе")

    bot.run_webhook(URL, port=8080)

    print("Статистика за смену:", bot.stats)
