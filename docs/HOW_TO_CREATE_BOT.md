# 🤖 Полная инструкция: Как написать своего первого бота на MaxApiLib

> **Цель:** Сделать так, чтобы даже человек, никогда не писавший код, мог запустить своего бота за 15 минут.
> **Принцип:** «Не думай о сложном, просто пиши то, что хочешь, чтобы бот сделал».
> **Важно:** Библиотека работает с мессенджером **MAX** (не Telegram!).

---

## 📋 Шаг 0: Подготовка (5 минут)

Прежде чем писать код, нужно получить «ключ» от MAX и установить инструменты.

### 1. Получение токена (ключа доступа)

Бот не сможет работать без специального пароля — **токена**.

1. Откройте мессенджер **MAX** и найдите официального бота **@MasterBot** (у него синяя галочка).
2. Напишите ему команду `/newbot`.
3. Он попросит придумать имя боту (например: `Мой Супер Бот`). Это то, что видят пользователи.
4. Затем он попросит придумать **юзернейм** (ссылку). Он должен заканчиваться на `bot` (например: `SuperCoolTestBot`).
5. Если всё успешно, MasterBot пришлёт длинное сообщение с текстом вида:
   ```
   Use this token to access the HTTP API: 123456789:AAH...
   ```
6. **Скопируйте этот токен.** Никогда не показывайте его никому!

### 2. Установка Python

Если у вас его нет:
- Зайдите на [python.org](https://www.python.org/downloads/) и скачайте последнюю версию.
- При установке **обязательно** поставьте галочку ✅ "Add Python to PATH".

Проверьте установку, открыв терминал (командную строку) и написав:
```bash
python --version
```
Должно показать версию, например `Python 3.12.0`.

### 3. Установка библиотеки

Откройте терминал и введите одну команду:
```bash
pip install maxapilib
```

Если вы разрабатываете локально (из папки проекта):
```bash
pip install -e .
```

### 4. Настройка токена

Есть два способа передать токен боту:

**Способ А: Переменная окружения (рекомендуется)**
```bash
# Windows (Command Prompt)
set MAX_BOT_TOKEN=ваш_токен

# Windows (PowerShell)
$env:MAX_BOT_TOKEN="ваш_токен"

# Linux/macOS
export MAX_BOT_TOKEN=ваш_токен
```

**Способ Б: Прямо в коде** (только для тестов!)
```python
bot = Bot(token="123456789:AAH...")
```

---

## 🚀 Шаг 1: Ваш первый бот (Эхо-бот)

Создайте файл `bot.py` и вставьте туда этот код. Просто скопируйте и замените `'ВАШ_ТОКЕН'` на тот, что дал MasterBot (если не использовали переменную окружения).

```python
from maxapilib import Bot, Button, TextBox

# 1. Создаём бота
# Токен берётся из переменной окружения MAX_BOT_TOKEN
# Или можно явно: bot = Bot(token="ВАШ_ТОКЕН")
bot = Bot()


# 2. Обработчик нажатия кнопки «Начать» в профиле бота
@bot.on_started()
def start(event):
    """Пользователь впервые открыл бота."""
    box = TextBox("Привет! Я твой первый бот на MAX!")
    box.row(
        Button.callback("👋 Помахать", "wave"),
        Button.link("📖 Документация", "https://dev.max.ru/docs-api"),
    )
    event.send(box)


# 3. Обработчик команды /start
@bot.on_command("start", "help")
def help_command(message):
    """Команды /start и /help."""
    message.reply("Напишите любое сообщение — я повторю его!")


# 4. Обработчик нажатия кнопки
@bot.on_button("wave")
def wave_handler(callback):
    """Реакция на кнопку «Помашать»."""
    callback.answer("Машу в ответ! 👋")  # Убирает «часики» с кнопки
    callback.send("И тебе привет!")


# 5. Обработчик любого текста (эхо)
@bot.on_message()
def echo(message):
    """Отвечает на любое сообщение, если не сработало выше."""
    message.reply(f"Ты написал: {message.text}")


# 6. Запуск бота
if __name__ == "__main__":
    print("Бот запущен! Нажми Ctrl+C чтобы остановить.")
    bot.run()  # Запускает polling (опрос сервера MAX)
```

**Как запустить:**
```bash
python bot.py
```

Зайдите в своего бота в MAX, нажмите **«Начать»** или отправьте `/start` — и увидите магию!

---

## 🧠 Шаг 2: Магия состояний (FSM) — Бот-анкета

Иногда нужно запомнить, что пользователь ответил на предыдущий вопрос. Для этого есть **Состояния (FSM — Finite State Machine)**.

Представьте, что бот надевает разные шляпы:
- 🎩 «Шляпа ожидания имени»
- 🎩 «Шляпа ожидания города»

Когда пользователь в «шляпе ожидания имени», бот знает: сейчас нужно ждать именно имя!

```python
from maxapilib import Bot, Button, TextBox

bot = Bot()


@bot.on_command("start", "reset")
def start(message):
    """Начало анкеты: сбрасываем прошлое и ждём имя."""
    bot.reset_state(message)           # Забыть старые ответы
    bot.set_state(message, "waiting_name")  # Надеть шляпу «Ждём имя»
    message.reply("Как вас зовут?")


@bot.on_state("waiting_name")
def ask_city(message):
    """Сработает ТОЛЬКО пока у пользователя состояние 'waiting_name'."""
    # Сохраняем имя во временную память
    bot.set_data(message, name=message.text)
    
    # Меняем шляпу на «Ждём город»
    bot.set_state(message, "waiting_city")
    message.reply(f"Приятно познакомиться, {message.text}! Из какого вы города?")


@bot.on_state("waiting_city")
def finish(message):
    """Последний шаг анкеты."""
    # Сохраняем город
    bot.set_data(message, city=message.text)
    
    # Достаём все сохранённые данные
    data = bot.get_data(message)  # {'name': '...', 'city': '...'}
    
    # Снимаем все шляпы — анкета готова
    bot.reset_state(message)
    
    box = TextBox(
        f"✅ Записал: {data['name']} из города {data['city']}.\n\n"
        "Спасибо! Можете начать заново командой /start."
    )
    box.row(Button.callback("🔄 Заполнить заново", "restart"))
    message.reply(box)


@bot.on_command("me")
def show_data(message):
    """Показать, что бот о вас помнит."""
    data = bot.get_data(message)
    if not data:
        message.reply("Пока ничего не знаю. Начните с /start")
        return
    
    facts = ", ".join(f"{key}: {value}" for key, value in data.items())
    message.reply(f"📋 Я о вас знаю: {facts}")


@bot.on_button("restart")
def restart(callback):
    """Кнопка из последнего сообщения: начать анкету заново."""
    callback.answer("Начинаем заново!")
    bot.reset_state(callback)
    bot.set_state(callback, "waiting_name")
    callback.send("Как вас зовут?")


@bot.on_message()
def fallback(message):
    """Всё остальное — подсказка."""
    message.reply("Не понял. Напишите /start, чтобы заполнить анкету.")


if __name__ == "__main__":
    bot.run()
```

**Почему это просто?**
- ✅ Вам не нужно создавать базы данных
- ✅ Вы не думаете о том, как хранить данные
- ✅ Вы просто говорите: «Если пользователь в состоянии X, сделай Y»

---

## ⌨️ Шаг 3: Красивые кнопки (без боли)

Забудьте про сложные JSON и структуры. Кнопки создаются как обычный список списков внутри `TextBox`.

### Типы кнопок в MAX:

| Тип | Что делает | Пример |
|-----|-----------|--------|
| `Button.callback()` | Отправляет payload боту | `Button.callback("Купить", "buy_item_1")` |
| `Button.message()` | Отправляет текст в чат | `Button.message("Показать меню")` |
| `Button.link()` | Открывает ссылку | `Button.link("Сайт", "https://max.ru")` |
| `Button.clipboard()` | Копирует текст в буфер | `Button.clipboard("Промокод", "MAX2026")` |
| `Button.contact()` | Запрашивает контакт | `Button.contact()` |
| `Button.location()` | Запрашивает геолокацию | `Button.location()` |

### Пример клавиатуры:

```python
from maxapilib import Bot, Button, TextBox

bot = Bot()


@bot.on_command("menu")
def show_menu(message):
    """Показать меню с кнопками."""
    box = TextBox("🍕 Что будете заказывать?")
    
    # Первый ряд кнопок
    box.row(
        Button.callback("🍕 Пицца", "pizza"),
        Button.callback("🍔 Бургер", "burger"),
    )
    
    # Второй ряд
    box.row(
        Button.callback("🥗 Салат", "salad"),
        Button.callback("🍟 Фри", "fries"),
    )
    
    # Третий ряд — разные типы кнопок
    box.row(
        Button.link("🌐 Наш сайт", "https://pizzeria.example.com"),
        Button.clipboard("🎁 Промокод", "FIRSTORDER20"),
    )
    
    message.reply(box)


@bot.on_button("pizza")
def order_pizza(callback):
    callback.answer("Отличный выбор!")
    
    box = TextBox("Какую пиццу хотите?")
    box.row(
        Button.callback("Пепперони", "pepperoni"),
        Button.callback("Маргарита", "margarita"),
        Button.callback("4 сыра", "cheese"),
    )
    callback.send(box)


@bot.on_message()
def fallback(message):
    message.reply("Нажмите /menu, чтобы увидеть кнопки.")


if __name__ == "__main__":
    bot.run()
```

**Важно:** Текст кнопки в коде и текст, который приходит в обработчике, должны совпадать **до символа**. `"Пицца"` ≠ `"пицца"` (регистр имеет значение!).

---

## ⏰ Шаг 4: Таймеры и отложенные сообщения

Бот умеет ждать и напоминать. Есть два типа таймеров:

### 1. `later()` — одноразовое напоминание

```python
from maxapilib import Bot, later, humanize_delay

bot = Bot()


@bot.on_command("remind")
def remind_me(message):
    """Напомнить через 10 секунд."""
    message.reply(f"Напомню через {humanize_delay(10)}!")
    
    # Отправить сообщение через 10 секунд
    later(10, lambda: message.send("⏰ Прошло 10 секунд! Ку-ку!"))


@bot.on_command("remind_custom")
def remind_custom(message):
    """Напомнить через время, указанное пользователем."""
    # message.args[0] — первый аргумент после команды
    # Например: /remind_custom 30s или /remind_custom 5m
    from maxapilib import parse_time
    
    if not message.args:
        message.reply("Укажите время: /remind_custom 10s (секунды) или /remind_custom 5m (минуты)")
        return
    
    seconds = parse_time(message.args[0])
    if seconds <= 0:
        message.reply("Неверный формат. Используйте: 10s, 5m, 1h, 1d")
        return
    
    message.reply(f"Напомню через {humanize_delay(seconds)}.")
    later(seconds, lambda: message.send(f"⏰ Прошло {humanize_delay(seconds)}!"))


if __name__ == "__main__":
    bot.run()
```

### 2. `every()` — периодические напоминания

```python
from maxapilib import Bot, every, Timer

bot = Bot()

# Глобальная переменная для хранения таймера
reminder_timer: Timer | None = None


@bot.on_command("start_spam")
def start_spam(message):
    """Запустить периодические напоминания."""
    global reminder_timer
    
    # Остановить предыдущий таймер, если был
    if reminder_timer is not None:
        reminder_timer.cancel()
    
    # Запустить новый: каждые 5 секунд
    reminder_timer = every(
        5,  # интервал в секундах
        lambda: message.send("🔔 Тук-тук! Я всё ещё здесь!"),
    )
    
    message.reply("Буду напоминать каждые 5 секунд! Чтобы остановить: /stop_spam")


@bot.on_command("stop_spam")
def stop_spam(message):
    """Остановить периодические напоминания."""
    global reminder_timer
    
    if reminder_timer is None:
        message.reply("Напоминания и не были включены.")
        return
    
    reminder_timer.cancel()
    reminder_timer = None
    message.reply("✅ Напоминания остановлены.")


if __name__ == "__main__":
    bot.run()
```

### Форматы времени в `parse_time()`:

| Формат | Значение | Пример |
|--------|----------|--------|
| `10s` | 10 секунд | `parse_time("10s")` → `10.0` |
| `5m` | 5 минут | `parse_time("5m")` → `300.0` |
| `1h` | 1 час | `parse_time("1h")` → `3600.0` |
| `1d` | 1 день | `parse_time("1d")` → `86400.0` |
| `1.5h` | 1.5 часа | `parse_time("1.5h")` → `5400.0` |

---

## 🎣 Шаг 5: Режим Вебхуков (Для продакшена)

Когда бот вырастет и его нужно будет повесить на сервер, используйте **вебхуки** вместо опроса (polling).

### В чём разница?

| Polling (`bot.run()`) | Webhook (`bot.run_webhook()`) |
|----------------------|------------------------------|
| Бот сам спрашивает MAX: «Есть новые сообщения?» | MAX сам присылает сообщения на ваш сервер |
| Работает на любом компьютере | Нужен сервер с белым IP или HTTPS |
| Проще для разработки | Рекомендуется для продакшена |
| Тратит больше ресурсов | Эффективнее при большой нагрузке |

### Что нужно для вебхука:

1. **Сервер с HTTPS** (или туннель, например ngrok для тестов)
2. **Публичный URL**, например: `https://bot.example.com/hook`
3. **Порт**, на котором будет слушать сервер (обычно 8080)

### Пример кода:

```python
from maxapilib import Bot, Message

# Замените на свой HTTPS-адрес!
WEBHOOK_URL = "https://bot.example.com/hook"

# Ваш user_id в MAX (опционально): сюда бот напишет об ошибках
# Узнать ID можно из логов бота (строка «сообщение от <user_id>»)
ADMIN_ID: int | None = None

bot = Bot(log_file="bot.log", admin_id=ADMIN_ID)


@bot.on_started()
def hello(event):
    """Пользователь запустил бота."""
    event.send("Привет! Я работаю через вебхук. 🚀")


@bot.on_command("start", "help")
def help_command(message: Message):
    message.reply("Напишите что-нибудь — отвечу эхом.")


@bot.on_message()
def echo(message: Message):
    message.reply(f"Вы написали: {message.text}")


@bot.on_error()
def report_error(error):
    """Сюда попадают ошибки из обработчиков."""
    print(f"❌ Ошибка в обработчике: {error.text}")


if __name__ == "__main__":
    print(f"🔗 Вебхук URL: {WEBHOOK_URL}")
    print("📊 Мониторинг доступен:")
    print("   GET /health — проверить, жив ли бот")
    print("   GET /stats  — статистика (события, сообщения, ошибки)")
    
    # Запуск вебхука
    bot.run_webhook(WEBHOOK_URL, port=8080)
    
    # После остановки (Ctrl+C) покажет статистику
    print(f"\n📈 Статистика за смену: {bot.stats}")
```

### Запуск с ngrok (для тестов без сервера):

```bash
# 1. Установите ngrok (https://ngrok.com/download)
# 2. Запустите туннель на порт 8080
ngrok http 8080

# 3. Скопируйте HTTPS-адрес из вывода ngrok (например: https://abc123.ngrok.io)
# 4. Вставьте его в WEBHOOK_URL и запустите бота
python webhook_bot.py
```

---

## 📊 Шаг 6: Логирование и мониторинг

Библиотека автоматически ведёт логи и считает статистику.

### Включение логирования:

```python
from maxapilib import Bot, enable_logging, close_log_files

bot = Bot()

# Включить логи в консоль (уровень INFO)
enable_logging()

# Или с записью в файл
enable_logging(log_file="my_bot.log")

# Уровни логирования:
# - "DEBUG" — очень подробно (для отладки)
# - "INFO"  — события и отправки (по умолчанию)
# - "WARNING" — только предупреждения
# - "ERROR" — только ошибки

if __name__ == "__main__":
    bot.run()
    close_log_files()  # Закрыть файлы логов при выходе
```

### Просмотр статистики:

```python
from maxapilib import Bot

bot = Bot()

# ... обработчики ...

if __name__ == "__main__":
    bot.run()
    
    # После остановки показать статистику
    print(f"Всего событий: {bot.stats.events}")
    print(f"Отправлено сообщений: {bot.stats.messages_sent}")
    print(f"Ошибок: {bot.stats.errors}")
    
    # Или всё сразу
    print(f"Статистика: {bot.stats.as_dict()}")
```

### Эндпоинты мониторинга (для вебхука):

При запуске через `run_webhook()` доступны:
- `GET /health` — возвращает `{"status": "ok"}`, если бот жив
- `GET /stats` — возвращает JSON со статистикой

Пример запроса:
```bash
curl https://bot.example.com/health
curl https://bot.example.com/stats
```

---

## 🛠 Частые ошибки новичков (и как их избежать)

### 1. ❌ Бот не отвечает

**Проверьте:**
- Запущен ли скрипт (`python bot.py`)?
- Правильно ли установлен токен (нет ли лишних пробелов)?
- Смотрите в консоль — там будут красные буквы с ошибкой!

**Решение:**
```python
# Добавьте логирование, чтобы видеть ошибки
from maxapilib import enable_logging
enable_logging()

bot = Bot()
# ...
```

### 2. ❌ Бот забывает данные между сообщениями

**Проблема:** Вы не установили состояние перед ожиданием ответа.

**Решение:**
```python
@bot.on_command("start")
def start(message):
    bot.set_state(message, "waiting_name")  # ← Обязательно!
    message.reply("Как вас зовут?")

@bot.on_state("waiting_name")  # ← Сработает только в этом состоянии
def get_name(message):
    # ...
```

### 3. ❌ Кнопки не нажимаются / не срабатывают

**Проблема:** Текст payload не совпадает **до символа**.

```python
# В кнопке:
Button.callback("Купить", "buy_item")

# В обработчике — должно быть ТОЧНО ТАКОЕ ЖЕ значение:
@bot.on_button("buy_item")  # ✅ Правильно
@bot.on_button("Buy_item")  # ❌ Неправильно (регистр!)
@bot.on_button("buy_item ") # ❌ Неправильно (пробел!)
```

### 4. ❌ Бот отвечает на свои же сообщения

**Проблема:** Бот обрабатывает сообщения, которые сам отправил.

**Решение:** Используйте фильтры или проверяйте `message.from_user.id != bot.id`.

### 5. ❌ Таймер не срабатывает

**Проблема:** Вы используете `message` внутри `lambda`, но обработчик уже завершился.

**Решение:** Метод `message.send()` автоматически запоминает чат, поэтому вне обработчика можно использовать:
```python
later(10, lambda: message.send("Напоминание"))  # ✅ Работает
```

---

## 📚 Что дальше?

Вы освоили базу! Теперь вы можете:

### 🔹 Добавить обработку ошибок
```python
@bot.on_error()
def any_error(error):
    print(f"Упс: {error.text}")
    # Отправить уведомление админу
    # bot.send_message(ADMIN_ID, f"Ошибка: {error.text}")
```

### 🔹 Использовать регулярные выражения
```python
import re

@bot.on_text(r"\d+")  # Ловит сообщения с числами
def handle_numbers(message):
    message.reply(f"Вы ввели число: {message.text}")

@bot.on_text(r"привет|здравствуй|хай")  # Несколько вариантов
def greet(message):
    message.reply("И вам привет!")
```

### 🔹 Отправлять фото и файлы
```python
@bot.on_command("photo")
def send_photo(message):
    with open("cat.jpg", "rb") as f:
        message.reply_photo(f, caption="Смотрите, какой котик!")
```

### 🔹 Использовать контекст текущего события
```python
@bot.on_message()
def handler(message):
    # Получить текущее событие в любом месте кода
    current = bot.current
    if current is not None:
        print(f"Обрабатываю сообщение от {current.user_id}")
```

---

## 🎓 Полный шаблон бота «всё в одном»

```python
"""
Полный шаблон бота на MaxApiLib.
Скопируйте, замените токен и запускайте!
"""

from maxapilib import Bot, Button, TextBox, enable_logging, later, every

# ==================== НАСТРОЙКИ ====================

# Токен из @MasterBot (или переменная окружения MAX_BOT_TOKEN)
BOT_TOKEN = "ВАШ_ТОКЕН"

# ID админа для уведомлений об ошибках (опционально)
ADMIN_ID = None  # Замените на ваш user_id

# ==================== СОЗДАНИЕ БОТА ====================

bot = Bot(
    token=BOT_TOKEN,
    log_file="bot.log",      # Логирование в файл
    admin_id=ADMIN_ID,       # Уведомления об ошибках
)

# Включить логи в консоль
enable_logging()

# ==================== ОБРАБОТЧИКИ ====================

@bot.on_started()
def welcome(event):
    """Пользователь нажал «Начать»."""
    box = TextBox("👋 Привет! Я многофункциональный бот.")
    box.row(
        Button.callback("ℹ️ О боте", "about"),
        Button.callback("📋 Меню", "menu"),
    )
    event.send(box)


@bot.on_command("start", "help")
def help_command(message):
    """Команды /start и /help."""
    message.reply(
        "Доступные команды:\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/timer — установить таймер\n"
        "\nИли нажмите кнопки ниже!"
    )


@bot.on_button("about")
def about(callback):
    """Информация о боте."""
    callback.answer("Показываю информацию...")
    callback.send(
        "🤖 Этот бот написан на библиотеке MaxApiLib.\n"
        "Она максимально проста для новичков!"
    )


@bot.on_button("menu")
def menu(callback):
    """Главное меню."""
    callback.answer("Открываю меню...")
    
    box = TextBox("📋 Главное меню:")
    box.row(
        Button.callback("⏰ Таймер", "timer"),
        Button.callback("📊 Статистика", "stats"),
    )
    box.row(
        Button.link("🌐 Сайт", "https://max.ru"),
        Button.contact(),
    )
    callback.send(box)


@bot.on_command("timer")
@bot.on_button("timer")
def timer_handler(message_or_callback):
    """Установка таймера."""
    # Универсальный обработчик для команды и кнопки
    obj = message_or_callback
    
    obj.reply("⏰ Таймер установлен на 30 секунд!")
    later(30, lambda: obj.send("⏰ Время вышло!"))


@bot.on_message()
def fallback(message):
    """Все остальные сообщения."""
    message.reply(
        f"Я получил ваше сообщение: {message.text!r}\n"
        "Нажмите /help, чтобы узнать, что я умею."
    )


@bot.on_error()
def handle_error(error):
    """Обработка всех ошибок."""
    print(f"❌ Ошибка: {error.text}")
    # Можно отправить уведомление админу
    # if ADMIN_ID:
    #     bot.send_message(ADMIN_ID, f"Ошибка в боте: {error.text}")


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    print("🚀 Бот запущен! Нажмите Ctrl+C для остановки.")
    print("📊 Статистика будет показана после остановки.")
    
    try:
        bot.run()  # Polling режим
        # Или для вебхука:
        # bot.run_webhook("https://your-server.com/hook", port=8080)
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем.")
    finally:
        print(f"📈 Итоговая статистика: {bot.stats}")
```

---

## 🎉 Поздравляю!

Теперь вы умеете:
- ✅ Создавать бота и получать токен
- ✅ Обрабатывать команды, кнопки и сообщения
- ✅ Использовать состояния (FSM) для анкет
- ✅ Настраивать таймеры и отложенные сообщения
- ✅ Создавать красивые клавиатуры
- ✅ Запускать бота в режиме вебхука
- ✅ Включать логирование и мониторинг
- ✅ Обрабатывать ошибки

**Дальше — только ваша фантазия!** 🚀

---

## 📞 Поддержка

Если что-то не работает:
1. Проверьте логи (консоль или файл `bot.log`)
2. Убедитесь, что токен правильный
3. Посмотрите примеры в папке `examples/`
4. Прочитайте документацию MAX API: https://dev.max.ru/docs-api

Удачи в создании ботов! 🤖✨
