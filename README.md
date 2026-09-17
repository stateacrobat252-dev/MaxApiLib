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
| Диалоги-анкеты (состояния) | `bot.set_state(message, "имя")` + `@bot.on_state("имя")` |
| Память о пользователе | `bot.set_data(message, name="Иван")`, `bot.get_data(message)` |
| Вебхуки (для продакшена) | `bot.run_webhook("https://бот.example.com/hook")` |
| Логи и счётчики | `print(bot.stats)`, `Bot(log_file="bot.log")`, `GET /health`, `GET /stats` |

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

## Состояния (диалоги-анкеты)

Библиотека запоминает для каждого пользователя **состояние** и **данные**:

```python
@bot.on_command("start")
def start(message):
    bot.set_state(message, "waiting_name")        # вошли в состояние
    message.reply("Как вас зовут?")

@bot.on_state("waiting_name")                     # сработает только в нём
def get_name(message):
    bot.set_data(message, name=message.text)      # сохранили ответ
    bot.reset_state(message)                      # вышли
    message.reply(f"Привет, {bot.get_data(message, 'name')}!")
```

Полезные методы (работают и с событием, и по ID):

| Метод | Что делает |
| --- | --- |
| `bot.set_state(message, "имя")` | запомнить состояние (`None` — сбросить) |
| `bot.get_state(message)` | текущее состояние или `None` |
| `bot.set_data(message, name="Иван")` | сохранить данные пользователя |
| `bot.get_data(message)` / `bot.get_data(message, "name")` | все данные или одно значение |
| `bot.reset_state(message)` | забыть состояние и данные |
| `bot.set_state("имя", chat_id=42, user_id=7)` | то же самое вне обработчика |

Любой обработчик можно ограничить состоянием:

```python
@bot.on_button("next", state="in_menu")   # кнопка работает только в меню
@bot.on_text(r"да|нет", state="confirm")  # и текст
```

Состояния и данные хранятся в памяти процесса (теряются при перезапуске).
Для продакшена можно взять Redis:

```python
from maxapi.context import RedisContext

bot = Bot(storage=RedisContext, storage_options={"url": "redis://localhost:6379"})
```

## Вебхуки

Вебхук — способ, который MAX рекомендует для продакшена: события приходят
сразу на ваш HTTPS-адрес, а не выпрашиваются опросом.

```python
bot = Bot()

...обработчики...

if __name__ == "__main__":
    bot.run_webhook("https://bot.example.com/hook", port=8080)
```

Что делает библиотека:

* поднимает HTTP-сервер (порт по умолчанию 8080) на указанном пути;
* сама подписывает бота на вебхук (`POST /subscriptions`);
* придумывает `secret`, если вы его не указали, и проверяет заголовок
  `X-Max-Bot-Api-Secret` в каждом запросе (чужие запросы получают 403);
* отдаёт адреса для мониторинга: `GET /health` и `GET /stats`.

Важно: адрес должен быть доступен из интернета по HTTPS. Для локальной
проверки используйте `subscribe=False` — тогда сервер поднимется, но
подписка не оформляется.

Параметры: `host`, `port` (`0` — любой свободный), `secret`, `subscribe`,
`blocking` (как у `run`).

Если бот раньше работал через вебхук, а теперь должен отвечать в поллинге,
удалите подписку:

```python
print(bot.webhooks())     # какие адреса подписаны
bot.delete_webhook()      # убрать подписки, вернуть поллинг
```

## Логи и мониторинг

Логи включены по умолчанию: видно каждое событие и каждую отправку.

```
2026-09-17 12:00:01 INFO     maxapilib: ← сообщение от 42 в чат 100: '/start'
2026-09-17 12:00:01 INFO     maxapilib: → ответ в чат 100: 'Привет!'
```

Настроить можно при создании бота или отдельно:

```python
bot = Bot(log_level="DEBUG", log_file="bot.log")   # подробно и в файл

import maxapilib
maxapilib.enable_logging("WARNING")                # только предупреждения
```

Счётчики для мониторинга:

```python
print(bot.stats)
# статус: работает | события: 12 | сообщения: 9 | кнопки: 3 |
# отправлено: 11 | ответов на кнопки: 3 | ошибки: 0 | работает: 2m

bot.stats.as_dict()   # то же словарём — удобно отдавать в систему мониторинга
```

В режиме вебхука счётчики и здоровье доступны по HTTP:

```bash
curl http://localhost:8080/health   # {'status': 'ok', 'bot': {...}}
curl http://localhost:8080/stats    # счётчики в JSON
```

Ошибки в обработчиках не роняют бота: они попадают в лог, в счётчики
(`bot.stats.errors`) и в обработчики `on_error`:

```python
bot = Bot(admin_id=ВАШ_USER_ID)   # сообщение об ошибке придёт вам в MAX

@bot.on_error()
def any_error(error):
    print("Упс:", error.text)      # "ValueError: что-то пошло не так"
    print(error.traceback)         # полный стек вызовов

@bot.on_error(ValueError)          # только определённые ошибки
def only_value(error):
    ...
```

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

## Если бот не отвечает

* проверьте токен: при неверном токене бот падает с `MaxApiLibAuthError`;
* включите логи (`enable_logging("DEBUG")`) и посмотрите, приходит ли
  событие: строка `← сообщение от ...` означает, что событие дошло, значит
  дело в обработчике;
* нет ли установленного вебхука: при вебхуке MAX не отдаёт события через
  long polling. Посмотрите `print(bot.webhooks())` и при необходимости
  вызовите `bot.delete_webhook()`;
* лимиты API MAX: не более 2 сообщений и 2 ответов на callback в секунду
  на один чат — при массовой рассылке делайте паузы;
* long polling подходит для разработки; для продакшена MAX рекомендует
  вебхуки (см. раздел выше).

## Примеры

* [`examples/echo_bot.py`](examples/echo_bot.py) — эхо-бот: команды, кнопки, регулярные выражения.
* [`examples/keyboard_bot.py`](examples/keyboard_bot.py) — все типы кнопок MAX.
* [`examples/form_bot.py`](examples/form_bot.py) — анкета на состояниях (FSM) и данных пользователя.
* [`examples/timer_bot.py`](examples/timer_bot.py) — таймеры `later` и `every`.
* [`examples/webhook_bot.py`](examples/webhook_bot.py) — бот на вебхуке с логами и мониторингом.

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
