"""Бот-админка с рассылкой и статистикой.

Демонстрирует:
- Администрирование бота
- Рассылку сообщений всем пользователям
- Сохранение статистики пользователей
- Работу с данными в памяти

Запуск::

    set MAX_BOT_TOKEN=ваш_токен      # Windows
    python examples/admin_bot.py
"""

from maxapilib import Bot, Button, TextBox, enable_logging

bot = Bot()

# ID администратора (замените на свой user_id)
# Узнать ID можно из логов: «сообщение от <user_id>»
ADMIN_ID = None  # <-- Замените на ваш ID!

# Хранилище пользователей (в реальном проекте используйте базу данных)
users_db = {}


@bot.on_started()
def welcome(event):
    """Пользователь запустил бота."""
    user_id = event.user_id
    
    # Сохранить пользователя в БД
    if user_id not in users_db:
        users_db[user_id] = {
            "messages_count": 0,
            "first_seen": "сейчас",
        }
    
    box = TextBox("👋 Привет! Я демонстрационный бот.\n\n")
    
    if user_id == ADMIN_ID:
        box.row(Button.callback("🛠 Админка", "admin_panel"))
    
    box.row(
        Button.callback("ℹ️ О боте", "about"),
        Button.callback("📊 Моя статистика", "my_stats"),
    )
    
    event.send(box)


@bot.on_command("start")
def start_command(message):
    """Команда /start."""
    message.reply("Нажмите кнопку «Начать» в профиле бота или выберите действие ниже.")


@bot.on_button("about")
def about(callback):
    """Информация о боте."""
    callback.answer()
    callback.send(
        "🤖 Это бот-админка на MaxApiLib.\n\n"
        "Он умеет:\n"
        "• Считать сообщения пользователей\n"
        "• Показывать статистику\n"
        "• Делать рассылки (для админа)\n\n"
        f"Всего пользователей: {len(users_db)}"
    )


@bot.on_button("my_stats")
def my_stats(callback):
    """Статистика пользователя."""
    callback.answer()
    
    user_id = callback.user_id
    data = users_db.get(user_id, {})
    messages = data.get("messages_count", 0)
    first_seen = data.get("first_seen", "неизвестно")
    
    callback.send(
        f"📊 Ваша статистика:\n\n"
        f"Сообщений отправлено: {messages}\n"
        f"Первое посещение: {first_seen}"
    )


@bot.on_button("admin_panel")
def admin_panel(callback):
    """Панель администратора."""
    if callback.user_id != ADMIN_ID:
        callback.answer("⛔ Доступ запрещён!")
        return
    
    callback.answer()
    
    box = TextBox("🛠 Панель администратора\n\n")
    box.row(Button.callback("📨 Рассылка", "broadcast_start"))
    box.row(Button.callback("📋 Список пользователей", "users_list"))
    box.row(Button.callback("🔄 Обновить статистику", "refresh_stats"))
    
    callback.send(box)


@bot.on_button("users_list")
def users_list(callback):
    """Список всех пользователей."""
    if callback.user_id != ADMIN_ID:
        callback.answer("⛔ Доступ запрещён!")
        return
    
    callback.answer()
    
    if not users_db:
        callback.send("Пока нет пользователей.")
        return
    
    text = "📋 Пользователи:\n\n"
    for uid, data in list(users_db.items())[:20]:  # Первые 20
        msgs = data.get("messages_count", 0)
        text += f"• ID `{uid}` — {msgs} сообщ.\n"
    
    if len(users_db) > 20:
        text += f"\n... и ещё {len(users_db) - 20} пользователей"
    
    callback.send(text)


@bot.on_button("broadcast_start")
def broadcast_start(callback):
    """Начало рассылки."""
    if callback.user_id != ADMIN_ID:
        callback.answer("⛔ Доступ запрещён!")
        return
    
    callback.answer()
    
    box = TextBox(
        "📨 Рассылка сообщений всем пользователям.\n\n"
        "⚠️ Внимание! Сейчас это демо-режим.\n"
        "В реальной версии бот попросит ввести текст рассылки.\n\n"
        "Для теста отправим тестовое сообщение."
    )
    box.row(Button.callback("✅ Отправить тест", "broadcast_confirm"))
    box.row(Button.callback("❌ Отмена", "admin_panel"))
    
    callback.send(box)


@bot.on_button("broadcast_confirm")
def broadcast_confirm(callback):
    """Подтверждение рассылки."""
    if callback.user_id != ADMIN_ID:
        callback.answer("⛔ Доступ запрещён!")
        return
    
    callback.answer("Отправляю рассылку...")
    
    sent_count = 0
    failed_count = 0
    
    # В реальности здесь был бы цикл по всем user_id
    # и отправка через bot.maxapi.send_message()
    for uid in users_db.keys():
        if uid == callback.user_id:
            continue  # Не отправлять самому себе
        # Эмуляция отправки
        sent_count += 1
    
    callback.send(
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено: {sent_count}\n"
        f"Ошибок: {failed_count}"
    )


@bot.on_button("refresh_stats")
def refresh_stats(callback):
    """Обновление статистики."""
    if callback.user_id != ADMIN_ID:
        callback.answer("⛔ Доступ запрещён!")
        return
    
    callback.answer("Статистика обновлена!")
    callback.send(f"📊 Всего пользователей: {len(users_db)}")


@bot.on_message()
def track_message(message):
    """Счётчик сообщений от пользователей."""
    user_id = message.user_id
    
    if user_id not in users_db:
        users_db[user_id] = {
            "messages_count": 0,
            "first_seen": "сейчас",
        }
    
    users_db[user_id]["messages_count"] += 1
    
    # Игнорировать команды и кнопки (они уже обработаны)
    if message.text.startswith("/"):
        return
    
    # Ответ пользователю
    count = users_db[user_id]["messages_count"]
    if count % 10 == 0:
        message.reply(f"🎉 Вы отправили {count} сообщений!")
    elif count == 1:
        message.reply("✨ Спасибо за первое сообщение!")


@bot.on_error()
def handle_error(error):
    """Обработка ошибок."""
    print(f"❌ Ошибка: {error.text}")
    
    # Уведомить админа
    if ADMIN_ID:
        try:
            bot.maxapi.send_message(ADMIN_ID, f"⚠️ Ошибка в боте:\n{error.text}")
        except Exception:
            pass


if __name__ == "__main__":
    enable_logging()
    
    if ADMIN_ID is None:
        print("⚠️ Внимание: ADMIN_ID не установлен!")
        print("   Замените ADMIN_ID = None на ваш user_id в коде.")
        print("   Узнать ID можно из логов после первого сообщения боту.\n")
    
    print("🚀 Бот запущен!")
    print(f"👥 Пользователей в базе: {len(users_db)}")
    bot.run()
