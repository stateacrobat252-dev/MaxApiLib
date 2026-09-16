import time

import pytest

from maxbot_easy.time_utils import (
    every,
    humanize_delay,
    later,
    now,
    parse_time,
    sleep,
)


def test_now():
    res = now()
    assert hasattr(res, 'year')
    assert hasattr(res, 'month')

def test_sleep():
    start = time.time()
    sleep(0.1)
    assert time.time() - start >= 0.1

def test_later():
    called = False
    def callback():
        nonlocal called
        called = True
    later(0.1, callback)
    time.sleep(0.2)
    assert called is True

def test_every():
    called = False
    def callback():
        nonlocal called
        called = True
    every(0.1, callback)
    time.sleep(0.2)
    assert called is True

@pytest.mark.parametrize("time_str, expected", [
    ("10s", 10.0),
    ("5m", 300.0),
    ("1h", 3600.0),
    ("1d", 86400.0),
    ("10", 10.0),
])
def test_parse_time(time_str, expected):
    assert parse_time(time_str) == expected

def test_parse_time_invalid():
    assert parse_time("invalid") == 0.0
    assert parse_time("") == 0.0
    assert parse_time(None) == 0.0

@pytest.mark.parametrize("seconds, expected", [
    (30, "30c"),
    (120, "2m"),
    (3600, "1h"),
    (86400, "1d"),
    (90000, "1d"),
])
def test_humanize_delay(seconds, expected):
    assert humanize_delay(seconds) == expected
