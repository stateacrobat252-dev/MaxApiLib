"""Общие фикстуры: тесты идут без сети, HTTP-слой ``maxapi`` подменяется."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

import pytest
from maxapi.connection import base as conn_base
from maxapi.utils.runtime import bind_bot

from .helpers import TOKEN, FakeTransport


@pytest.fixture
def bot(transport: FakeTransport) -> Any:
    """Готовый бот с подменённым HTTP-слоем."""
    from maxapilib import Bot

    return Bot(TOKEN)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeTransport]:
    """Подменить HTTP-слой ``maxapi`` заглушкой MAX Bot API."""
    fake = FakeTransport()

    async def request(
        _self: Any,
        method: Any,
        path: Any,
        model: Any = None,
        *,
        is_return_raw: bool = False,
        **kwargs: Any,
    ) -> Any:
        raw = await fake.handle(
            method=str(method),
            path=str(path),
            params=kwargs.get("params"),
            json=kwargs.get("json"),
        )
        if is_return_raw or model is None:
            return raw

        # Настоящий BaseConnection.request собирает модель и внедряет в неё
        # ссылку на бота — повторяем это поведение.
        built = model(**raw)
        with contextlib.suppress(RuntimeError):
            bind_bot(built, _self._ensure_bot())
        return built

    monkeypatch.setattr(conn_base.BaseConnection, "request", request)
    yield fake
