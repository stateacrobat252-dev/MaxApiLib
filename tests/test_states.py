"""Тесты состояний (FSM) и данных пользователя.

Сценарии написаны так, как их будет писать новичок: «спросили имя —
сохранили, спросили город — сохранили, показали результат».
"""

from __future__ import annotations

from typing import Any

import pytest

from maxapilib import Bot, Button, Callback, MaxApiLibError, Message, TextBox

from .helpers import (
    CHAT_ID,
    FakeTransport,
    message_callback,
    message_created,
    wait_for,
)


def test_form_flow(transport: FakeTransport, bot: Bot) -> None:
    """Анкета: команда → состояние → ответ → данные → выход из состояния."""
    seen: list[tuple[Any, str | None]] = []

    @bot.on_command("start")
    def start(message: Message) -> None:
        bot.set_state(message, "waiting_name")
        message.reply("Как вас зовут?")

    @bot.on_state("waiting_name")
    def get_name(message: Message) -> None:
        bot.set_data(message, name=message.text)
        seen.append((bot.get_data(message, "name"), bot.get_state(message)))
        bot.reset_state(message)
        message.reply(f"Привет, {message.text}!")

    transport.push_updates(message_created("/start"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: len(transport.messages) >= 1)
        assert bot.get_state(chat_id=CHAT_ID, user_id=42) == "waiting_name"

        transport.push_updates(message_created("Иван", mid="mid.2"))
        wait_for(lambda: len(transport.messages) >= 2)
    finally:
        bot.stop()

    assert seen == [("Иван", "waiting_name")]
    assert transport.messages[-1]["json"]["text"] == "Привет, Иван!"

    # После выхода из анкеты состояние и данные пусты.
    assert bot.get_state(chat_id=CHAT_ID, user_id=42) is None
    assert bot.get_data(chat_id=CHAT_ID, user_id=42) == {}


def test_states_are_separate_for_users(transport: FakeTransport, bot: Bot) -> None:
    """Состояние одного пользователя не влияет на другого."""

    @bot.on_command("ask")
    def ask(message: Message) -> None:
        bot.set_state(message, "waiting")

    transport.push_updates(message_created("/ask"))
    bot.run(blocking=False)
    try:
        wait_for(
            lambda: bot.get_state(chat_id=CHAT_ID, user_id=42) == "waiting"
        )
    finally:
        bot.stop()

    assert bot.get_state(chat_id=CHAT_ID, user_id=42) == "waiting"
    assert bot.get_state(chat_id=CHAT_ID, user_id=999) is None


def test_message_without_state_falls_through(
    transport: FakeTransport, bot: Bot
) -> None:
    """Если состояния нет, обработчик on_state не срабатывает."""
    handled: list[str] = []

    @bot.on_state("waiting_name")
    def get_name(message: Message) -> None:
        handled.append("state")

    @bot.on_message()
    def catch_all(message: Message) -> None:
        handled.append("catch-all")

    transport.push_updates(message_created("просто текст"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(handled))
    finally:
        bot.stop()

    assert handled == ["catch-all"]


def test_state_filter_on_text_and_button(
    transport: FakeTransport, bot: Bot
) -> None:
    """state= работает и у других обработчиков: кнопок и текста."""
    order: list[str] = []

    @bot.on_command("menu")
    def menu(message: Message) -> None:
        bot.set_state(message, "in_menu")
        box = TextBox("Меню").button("Дальше", "next")
        message.reply(box)

    @bot.on_button("next", state="in_menu")
    def next_step(callback: Callback) -> None:
        order.append("кнопка в меню")
        callback.answer("Ок")

    @bot.on_text(r"привет", state="in_menu")
    def hello(message: Message) -> None:
        order.append("текст в меню")

    @bot.on_button("next")
    def next_anywhere(callback: Callback) -> None:
        order.append("кнопка вне меню")

    transport.push_updates(message_created("/menu"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bot.get_state(chat_id=CHAT_ID, user_id=42) == "in_menu")
        transport.push_updates(message_callback("next"))
        wait_for(lambda: bool(order))
        transport.push_updates(message_created("привет", mid="mid.3"))
        wait_for(lambda: len(order) >= 2)
    finally:
        bot.stop()

    assert order == ["кнопка в меню", "текст в меню"]


def test_button_state_filter_blocks_other_states(
    transport: FakeTransport, bot: Bot
) -> None:
    """Кнопка со state= не сработает, если состояние другое."""
    order: list[str] = []

    @bot.on_button("go", state="playing")
    def playing(callback: Callback) -> None:
        order.append("играем")

    @bot.on_button("go")
    def fallback(callback: Callback) -> None:
        order.append("запасной")

    transport.push_updates(message_callback("go"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(order))
    finally:
        bot.stop()

    assert order == ["запасной"]


def test_on_state_accepts_several_states(
    transport: FakeTransport, bot: Bot
) -> None:
    seen: list[str] = []

    @bot.on_command("one")
    def one(message: Message) -> None:
        bot.set_state(message, "one")

    @bot.on_command("two")
    def two(message: Message) -> None:
        bot.set_state(message, "two")

    @bot.on_state("one", "two")
    def any_of_two(message: Message) -> None:
        seen.append(message.text)

    transport.push_updates(message_created("/one"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bot.get_state(chat_id=CHAT_ID, user_id=42) == "one")
        transport.push_updates(message_created("раз", mid="mid.2"))
        wait_for(lambda: bool(seen))
    finally:
        bot.stop()

    assert seen == ["раз"]


def test_state_without_target_raises(bot: Bot) -> None:
    with pytest.raises(MaxApiLibError, match="для кого менять состояние"):
        bot.set_state("waiting_name")


def test_manual_state_by_chat_id(transport: FakeTransport, bot: Bot) -> None:
    """Состояние можно ставить вручную, зная chat_id и user_id."""
    bot.set_state("reminded", chat_id=CHAT_ID, user_id=42)
    assert bot.get_state(chat_id=CHAT_ID, user_id=42) == "reminded"

    bot.set_data(chat_id=CHAT_ID, user_id=42, city="Москва")
    assert bot.get_data(chat_id=CHAT_ID, user_id=42) == {"city": "Москва"}
    assert bot.get_data(chat_id=CHAT_ID, user_id=42, key="city") == "Москва"
    assert bot.get_data(chat_id=CHAT_ID, user_id=42, key="возраст") is None

    bot.reset_state(chat_id=CHAT_ID, user_id=42)
    assert bot.get_state(chat_id=CHAT_ID, user_id=42) is None


def test_set_data_returns_all_data(transport: FakeTransport, bot: Bot) -> None:
    bot.set_data(chat_id=CHAT_ID, user_id=42, name="Иван")
    data = bot.set_data(chat_id=CHAT_ID, user_id=42, city="Казань")

    assert data == {"name": "Иван", "city": "Казань"}


def test_state_inside_callback(transport: FakeTransport, bot: Bot) -> None:
    """Состояние можно читать и менять прямо в обработчике кнопки."""

    @bot.on_button("ready")
    def ready(callback: Callback) -> None:
        bot.set_data(callback, stage="готово")
        callback.answer("Записал")

    transport.push_updates(message_callback("ready"))
    bot.run(blocking=False)
    try:
        wait_for(lambda: bool(transport.answers))
    finally:
        bot.stop()

    assert bot.get_data(chat_id=CHAT_ID, user_id=42) == {"stage": "готово"}


def test_button_helper_in_state_flow(transport: FakeTransport, bot: Bot) -> None:
    """Кнопка из TextBox и состояние работают вместе."""
    assert Button.callback("Дальше", "next").payload == "next"
