# maxbot-easy

Простая библиотека для создания ботов в мессенджере MAX. 
Разработана для тех, кто хочет быстро запустить бота без знания асинхронного программирования (async/await).

## Установка

Для установки библиотеки выполните команду:
```bash
pip install .
```
*(Или `pip install -e .` для разработки)*

## Быстрый старт

Ниже пример простого бота, который отвечает на `/start` и отправляет кнопку:

```python
import os
from maxbot_easy import Bot, Button, TextBox

# Укажите ваш токен в переменных окружения
TOKEN = os.getenv("MAXBOT_TOKEN")

bot = Bot(token=TOKEN)

@bot.on_text("/start")
def start():
    menu = TextBox("Выберите действие:")
    menu.add(Button.callback("Сайт", "go_to_site"))
    menu.add(Button.link("Правила", "https://example.com"))
    bot.send(menu)

@bot.on_button("go_to_site")
def handle_click():
    bot.send(TextBox("Вы перешли на сайт!"))

if __name__ == "__main__":
    bot.run()
```

## Особенности
- **Синхронный интерфейс**: Никаких `async` и `await`.
- **Простые типы**: Вместо сложных конструкторов — удобные фабричные методы (`Button.callback`, `Button.link`).
- **Автоматическое управление циклом**: Бот запускается в отдельном потоке.

## Примеры
Дополнительные примеры можно найти в папке `examples/`:
- `echo_bot.py` — базовый бот с эхом.
- `timer_bot.py` — пример работы с таймерами (`later`, `every`).

## Требования
- Python 3.9+
- Библиотека `maxapi`

## Лицензия
MIT
