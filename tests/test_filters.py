"""Тесты фильтров, которые MaxApiLib вешает на события ``maxapi``."""

from __future__ import annotations

from typing import Any

import pytest
from maxapi.types.updates import UpdateUnionAdapter

from maxapilib.filters import CallbackPayload, CommandFilter, TextPattern

from .helpers import message_callback, message_created


def parsed(raw: dict[str, Any]) -> Any:
    """Разобрать сырое событие в модель ``maxapi``."""
    return UpdateUnionAdapter.validate_python(raw)


def matches(filter_: Any, raw: dict[str, Any]) -> bool:
    """Применить фильтр к событию, как это делает диспетчер."""
    import asyncio

    return bool(asyncio.run(filter_(parsed(raw))))


def test_text_pattern_search() -> None:
    pattern = TextPattern(r"привет")
    assert matches(pattern, message_created("ну привет, бот"))
    assert not matches(pattern, message_created("пока"))
    assert repr(pattern) == "<TextPattern 'привет'>"


def test_text_pattern_requires_text() -> None:
    event = parsed(message_created(""))
    import asyncio

    assert asyncio.run(TextPattern(".*")(event)) is False


def test_text_pattern_validation() -> None:
    with pytest.raises(ValueError, match="Некорректное регулярное выражение"):
        TextPattern("([")


def test_command_filter() -> None:
    filter_ = CommandFilter(["start", "/help"])
    assert matches(filter_, message_created("/start"))
    assert matches(filter_, message_created("/start@maxapilib_bot"))
    assert matches(filter_, message_created("/HELP"))
    assert matches(filter_, message_created("/help аргумент"))
    assert not matches(filter_, message_created("/starter"))
    assert not matches(filter_, message_created("start"))
    assert not matches(filter_, message_created(""))


def test_command_filter_case_sensitive() -> None:
    filter_ = CommandFilter(["start"], case_sensitive=True)
    assert matches(filter_, message_created("/start"))
    assert not matches(filter_, message_created("/START"))
    assert "start" in repr(filter_)


def test_command_filter_validation() -> None:
    with pytest.raises(ValueError, match="хотя бы одну команду"):
        CommandFilter([])
    with pytest.raises(ValueError, match="хотя бы одну команду"):
        CommandFilter(["/"])


def test_command_filter_custom_prefix() -> None:
    assert matches(CommandFilter(["start"], prefix="!"), message_created("!start"))
    assert not matches(CommandFilter(["start"], prefix="!"), message_created("/start"))


def test_callback_payload_filter() -> None:
    filter_ = CallbackPayload("go")
    assert matches(filter_, message_callback("go"))
    assert not matches(filter_, message_callback("other"))
    assert not matches(filter_, message_created("просто текст"))
    assert repr(filter_) == "<CallbackPayload 'go'>"
