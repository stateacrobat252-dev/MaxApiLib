"""Проверки иерархии ошибок maxbot-easy."""

from __future__ import annotations

import pytest

from maxbot_easy.exceptions import (
    MaxBotEasyAPIError,
    MaxBotEasyError,
    MaxBotEasyNetworkError,
)


def test_base_error_is_exception() -> None:
    problem = MaxBotEasyError("что-то пошло не так")

    assert isinstance(problem, Exception)
    assert str(problem) == "что-то пошло не так"


def test_api_error_inherits_base_error() -> None:
    problem = MaxBotEasyAPIError("сервер отклонил запрос")

    assert isinstance(problem, MaxBotEasyError)
    assert problem.message == "сервер отклонил запрос"
    assert problem.code is None
    assert problem.original is None


def test_api_error_keeps_code_and_original() -> None:
    original = ValueError("внутренняя ошибка maxapi")
    problem = MaxBotEasyAPIError("неверный токен", code=401, original=original)

    assert problem.code == 401
    assert problem.original is original
    assert str(problem) == "неверный токен (код ошибки от сервера MAX: 401)"


def test_network_error_inherits_base_error() -> None:
    timeout = TimeoutError("долго не было ответа")
    problem = MaxBotEasyNetworkError("нет связи", original=timeout)

    assert isinstance(problem, MaxBotEasyError)
    assert problem.message == "нет связи"
    assert problem.original is timeout


def test_network_error_without_original() -> None:
    problem = MaxBotEasyNetworkError("нет связи")

    assert problem.original is None
    assert str(problem) == "нет связи"


def test_specific_errors_can_be_told_apart() -> None:
    api_problem = MaxBotEasyAPIError("сервер отклонил запрос")
    network_problem = MaxBotEasyNetworkError("нет связи")

    assert not isinstance(api_problem, MaxBotEasyNetworkError)
    assert not isinstance(network_problem, MaxBotEasyAPIError)


def test_pytest_raises_works_for_each_error() -> None:
    with pytest.raises(MaxBotEasyAPIError, match="сервер отклонил"):
        raise MaxBotEasyAPIError("сервер отклонил запрос")

    with pytest.raises(MaxBotEasyError, match="нет связи"):
        raise MaxBotEasyNetworkError("нет связи")
