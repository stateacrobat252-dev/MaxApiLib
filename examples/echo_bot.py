import os

from maxbot_easy import Bot, Button, TextBox

# Замените на ваш настоящий токен
TOKEN = os.getenv("MAXBOT_TOKEN", "YOUR_TOKEN_HERE")

bot = Bot(token=TOKEN)

@bot.on_text("/start")
def start_command():
    menu = TextBox("Привет! Вот наше меню:")
    menu.row(
        Button.callback("Перейти на сайт", "go_to_site"),
        Button.link("Наши правила", "https://example.com/rules")
    )
    bot.send(menu)

@bot.on_button("go_to_site")
def handle_site_click():
    bot.send(TextBox("Вы нажали на кнопку сайта!"))

@bot.on_text(".echo")
def echo_command(message):
    text = message.text.replace(".echo", "").strip()
    if not text:
        bot.reply(message, TextBox("Напишите что-нибудь после .echo"))
    else:
        bot.reply(message, TextBox(f"Вы написали: {text}"))

@bot.on_message
def handle_anything(message):
    # Этот обработчик сработает на все сообщения, которые не были обработаны выше
    # В нашей реализации декораторы просто регистрируют функции,
    # а цикл обрабатывает их по порядку.
    pass

if __name__ == "__main__":
    bot.run()
