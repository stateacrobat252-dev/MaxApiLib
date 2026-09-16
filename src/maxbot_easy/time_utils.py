import datetime
import threading
import time
from collections.abc import Callable
from typing import Any


def now() -> datetime.datetime:
    return datetime.datetime.now()

def sleep(seconds: float) -> None:
    time.sleep(seconds)

def later(seconds: float, callback: Callable[..., Any]) -> None:
    def delayed_call() -> None:
        time.sleep(seconds)
        callback()
    threading.Thread(target=delayed_call).start()

def every(seconds: float, callback: Callable[..., Any]) -> None:
    def loop() -> None:
        while True:
            time.sleep(seconds)
            callback()
    threading.Thread(target=loop).start()

def parse_time(time_str: str) -> float:
    units = {'s': 1.0, 'm': 60.0, 'h': 3600.0, 'd': 86400.0}
    if not time_str or not isinstance(time_str, str):
        return 0.0
    try:
        time_str = time_str.lower().strip()
        if time_str.endswith('s'):
            return float(time_str[:-1]) * units['s']
        elif time_str.endswith('m'):
            return float(time_str[:-1]) * units['m']
        elif time_str.endswith('h'):
            return float(time_str[:-1]) * units['h']
        elif time_str.endswith('d'):
            return float(time_str[:-1]) * units['d']
        else:
            return float(time_str)
    except ValueError:
        return 0.0

def humanize_delay(seconds: float) -> str:
    if seconds < 60:
        return f'{int(seconds)}c'
    elif seconds < 3600:
        return f'{int(seconds // 60)}m'
    elif seconds < 86400:
        return f'{int(seconds // 3600)}h'
    else:
        return f'{int(seconds // 86400)}d'
