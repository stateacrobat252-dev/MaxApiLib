# MaxApiLib

Простая синхронная библиотека для создания ботов в мессенджере **MAX**.
Это обёртка над асинхронной библиотекой [`maxapi`](https://github.com/max-messenger/max-botapi-python):
вся асинхронность спрятана внутри, а вы пишете обычные функции без `async`
и `await`.

```python
from maxapilib import Bot, Button, TextBox

bot = Bot()  # токен из переменной окружения MAX_BOT_TOKEN


@bot.on_command("start")
def start(message):
    menu = TextBox("Выберите действие:")
    menu.row(
        Button.callback("Показать сайт", "site"),
        Button.link("Правила", "https://example.com"),
    )
    message.reply(menu)


@bot.on_button("site")
def site(callback):
    callback.answer("Открываю сайт")
    callback.send("Перехожу на https://example.com")


if __name__ == "__main__":
    bot.run()
```

## Установка

```bash
pip install .          # обычная установка
pip install -e .[dev]  # для разработки (тесты, линтеры, типы)
```

Требуется Python 3.10+ и библиотека `maxapi` (устанавливается автоматически).

## Токен бота

1. Откройте бота **@MasterBot** в MAX и создайте своего бота.
2. Скопируйте токен и положите его в переменную окружения:

```bash
set MAX_BOT_TOKEN=ваш_токен      # Windows
export MAX_BOT_TOKEN=ваш_токен   # Linux/macOS
```

Можно передать токен и явно: `Bot("ваш_токен")`.

## Что умеет

| Возможность | Как пользоваться |
| --- | --- |
| Команды (`/start`, `/help`) | `@bot.on_command("start", "help")` |
| Текст по регулярному выражению | `@bot.on_text(r"привет")` |
| Нажатие кнопки с нужным `payload` | `@bot.on_button("site")` |
| Любое нажатие кнопки | `@bot.on_callback()` |
| Любое сообщение (запасной вариант) | `@bot.on_message()` |
| Запуск бота пользователем | `@bot.on_started()` |
| Отправка сообщения | `bot.send("текст")`, `message.reply(...)` |
| Клавиатура | `TextBox` + `Button.callback/link/message/clipboard/contact/location/open_app` |
| Ответ на нажатие кнопки | `callback.answer("текст")`, `callback.answer(notification="...")` |
| Таймеры | `later(5, func)`, `every(60, func)` |
| Отправка по расписанию и из потока | `bot.send("текст", chat_id=42)` |

## Обработчики

```python
@bot.on_command("start")          # /start и /start@имя_бота
def start(message):
    print(message.command, message.args)   # "start", ["аргумент", "второй"]

@bot.on_text(r"меню|каталог")     # поиск по регулярному выражению
def menu(message):
    message.reply("Вот меню")

@bot.on_button("buy")             # payload кнопки
def buy(callback):
    callback.answer("Готово", notification="Покупка оформлена")

@bot.on_message()                 # сработает, если ничего выше не совпало
def fallback(message):
    message.reply("Не понял запрос")
```

Обработчики вызываются **в порядке регистрации**: срабатывает первый
подходящий. Поэтому `@bot.on_message()` ставьте последним.

Из обработчика доступны удобные объекты:

* `Message` — `text`, `chat_id`, `user_id`, `message_id`, `command`, `args`,
  `reply(...)`, `send(...)`, `raw` (исходный объект `maxapi` со вложениями
  и разметкой);
* `Callback` — `payload`, `callback_id`, `chat_id`, `user_id`, `message`,
  `answer(...)`, `send(...)`;
* `Started` — `chat_id`, `user_id`, `payload` (диплинк), `send(...)`.

## Отправка сообщений

```python
bot.send("Привет!", chat_id=42)            # в чат
bot.send("Привет!", user_id=7)             # в личку
bot.send(TextBox("Меню").button("Купить", "buy"))  # с клавиатурой
message.reply("Ответ с цитированием")      # ответ на сообщение
callback.send("Новое сообщение в тот же чат")
```

Внутри обработчика адрес можно не указывать — сообщение уйдёт в тот чат,
откуда пришло событие. Вызовы синхронные: функция вернётся, когда MAX API
ответит, а ошибка прилетит исключением (см. ниже).

Кнопки:

```python
Button.callback("Купить", "buy")                    # событие с payload
Button.link("Сайт", "https://example.com")          # ссылка
Button.message("Отправить текст")                   # отправляет текст боту
Button.clipboard("Скопировать", "ПРОМОКОД")         # копирует текст
Button.contact()                                    # запрос контакта
Button.location()                                   # запрос геолокации
Button.open_app("Открыть", web_app="my_app")        # мини-приложение
```

Ограничения клавиатуры MAX (проверяются библиотекой с понятными ошибками):
до 210 кнопок, до 30 рядов, до 7 кнопок в ряду — и до 3, если это кнопки
`link`, `open_app`, `request_contact` или `request_geo_location`.

## Таймеры

```python
from maxapilib import every, later, parse_time, humanize_delay

later(10, lambda: bot.send("Прошло 10 секунд", chat_id=42))

reminder = every(60, lambda: bot.send("Напоминание", chat_id=42))
reminder.cancel()          # остановить цикл

parse_time("2m")           # 120.0
humanize_delay(120)        # "2m"
```

Таймеры работают в фоновых демон-потоках: они не мешают программе
завершиться и не блокируют бота.

## Ошибки

Все исключения наследуются от `MaxApiLibError`, поэтому достаточно одного
`except`:

```python
from maxapilib import MaxApiLibError

try:
    bot.send("Привет", chat_id=42)
except MaxApiLibError as exc:
    print("Не получилось:", exc, exc.details)
```

| Исключение | Когда возникает |
| --- | --- |
| `MaxApiLibError` | базовая ошибка библиотеки (например, не указан получатель) |
| `MaxApiLibAPIError` | API MAX ответил ошибкой |
| `MaxApiLibAuthError` | токен неверен или не передан |
| `MaxApiLibNetworkError` | нет связи с API MAX |
| `MaxApiLibTimeoutError` | ответа нет дольше `call_timeout` |

## Отладка

```python
import maxapilib

maxapilib.enable_logging()          # INFO
maxapilib.enable_logging("DEBUG")   # подробно

bot = Bot(log_level="DEBUG")        # то же самое при создании бота
```

Если бот не отвечает, проверьте:

* токен (`MaxApiLibAuthError` при запуске — неверный токен);
* нет ли у бота установленного вебхука: при вебхуке MAX не отдаёт события
  через long polling, и библиотека предупредит об этом в логах;
* лимиты API MAX: не более 2 сообщений и 2 ответов на callback в секунду
  на один чат — при массовой рассылке делайте паузы;
* long polling подходит для разработки; для продакшена MAX рекомендует
  вебхуки.

## Примеры

* [`examples/echo_bot.py`](examples/echo_bot.py) — эхо-бот: команды, кнопки, регулярные выражения.
* [`examples/keyboard_bot.py`](examples/keyboard_bot.py) — все типы кнопок MAX.
* [`examples/timer_bot.py`](examples/timer_bot.py) — таймеры `later` и `every`.

## Переход с maxbot-easy 0.1

Версия 1.0 — переписанная библиотека (старое имя: `maxbot-easy`):

| Было | Стало |
| --- | --- |
| `import maxbot_easy` | `import maxapilib` |
| `MaxBotEasyError` | `MaxApiLibError` |
| `@bot.on_text("/start")` | `@bot.on_command("start")` |
| `msg.text` (не работало) | `msg.text` — текст сообщения |
| `bot.send(box)` без адреса | работает внутри обработчика; вне — укажите `chat_id`/`user_id` |
| `bot.run()` — сразу выходил | `bot.run()` блокирует поток до Ctrl+C; фон — `bot.run(blocking=False)` |

Подробности — в [CHANGELOG.md](CHANGELOG.md).

## Разработка

```bash
pip install -e .[dev]
python -m ruff check .     # линтер
python -m mypy src/        # типы
python -m pytest           # тесты (без сети: HTTP-слой maxapi подменён)
```

## Лицензия

MIT.
