"""Бот-викторина на состояниях (FSM).

Бот задаёт 3 вопроса по очереди и подсчитывает результат.
Демонстрирует сложную логику переходов между состояниями.

Запуск::

    set MAX_BOT_TOKEN=ваш_токен      # Windows
    python examples/quiz_bot.py
"""

from maxapilib import Bot, Button, TextBox

bot = Bot()

# Вопросы викторины
QUESTIONS = [
    {
        "text": "Столица России?",
        "options": [("Санкт-Петербург", False), ("Москва", True), ("Казань", False)],
    },
    {
        "text": "Сколько планет в Солнечной системе?",
        "options": [("7", False), ("8", True), ("9", False)],
    },
    {
        "text": "Какой язык программирования используется для Android?",
        "options": [("Kotlin", True), ("Swift", False), ("Ruby", False)],
    },
]


@bot.on_command("start", "quiz")
def start_quiz(message):
    """Начать викторину."""
    bot.reset_state(message)
    bot.set_data(message, score=0, question_index=0)
    bot.set_state(message, "waiting_answer")
    
    box = TextBox("🧠 Добро пожаловать в викторину!\n\n")
    box.row(Button.callback("Начать тест", "start_test"))
    message.reply(box)


@bot.on_button("start_test")
def first_question(callback):
    """Показать первый вопрос."""
    show_question(callback, 0)


def show_question(obj, index: int):
    """Показать вопрос с кнопками вариантов."""
    if index >= len(QUESTIONS):
        # Все вопросы заданы — показать результат
        finish_quiz(obj)
        return
    
    q = QUESTIONS[index]
    box = TextBox(f"❓ Вопрос {index + 1}/{len(QUESTIONS)}\n\n{q['text']}")
    
    for text, _ in q["options"]:
        box.row(Button.callback(text, f"answer_{text}"))
    
    obj.send(box)


@bot.on_callback()
def handle_answer(callback):
    """Обработка ответа на вопрос."""
    if not callback.payload.startswith("answer_"):
        callback.answer()  # Игнорировать другие кнопки
        return
    
    callback.answer("Ответ принят!")
    
    # Получить текущий прогресс
    data = bot.get_data(callback)
    index = data.get("question_index", 0)
    score = data.get("score", 0)
    
    # Проверить правильность ответа
    selected_answer = callback.payload.replace("answer_", "")
    q = QUESTIONS[index]
    
    is_correct = False
    for text, correct in q["options"]:
        if text == selected_answer and correct:
            is_correct = True
            break
    
    if is_correct:
        score += 1
    
    # Сохранить обновлённые данные
    bot.set_data(callback, score=score, question_index=index + 1)
    
    # Показать следующий вопрос или результат
    show_question(callback, index + 1)


def finish_quiz(obj):
    """Показать итоговый результат."""
    data = bot.get_data(obj)
    score = data.get("score", 0)
    total = len(QUESTIONS)
    
    # Определить сообщение в зависимости от результата
    if score == total:
        emoji = "🏆"
        text = "Идеально! Вы ответили правильно на все вопросы!"
    elif score >= total / 2:
        emoji = "👍"
        text = f"Хороший результат! {score} из {total} правильных ответов."
    else:
        emoji = "📚"
        text = f"Попробуйте ещё раз! {score} из {total} правильных ответов."
    
    box = TextBox(f"{emoji} Викторина завершена!\n\n{text}")
    box.row(Button.callback("🔄 Пройти заново", "restart_quiz"))
    obj.send(box)
    
    # Сбросить состояние
    bot.reset_state(obj)


@bot.on_button("restart_quiz")
def restart_quiz(callback):
    """Начать викторину заново."""
    callback.answer("Начинаем заново!")
    bot.reset_state(callback)
    bot.set_data(callback, score=0, question_index=0)
    bot.set_state(callback, "waiting_answer")
    show_question(callback, 0)


@bot.on_message()
def fallback(message):
    """Подсказка, если пользователь пишет текст вместо кнопок."""
    message.reply("Нажмите /quiz, чтобы начать викторину, или используйте кнопки.")


if __name__ == "__main__":
    bot.run()
