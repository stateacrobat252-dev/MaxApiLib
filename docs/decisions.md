# Decisions

This file contains all architectural decisions made during the development of `MaxApiLib`.

## Decisions (1.1)
- [x] FSM строится на контекстах `maxapi` (`Dispatcher.fsm`, `MemoryContext`/`RedisContext`), а не на своём хранилище: один источник правды, смена хранилища одним аргументом `Bot(storage=...)`.
- [x] Состояние — обычная строка (`"waiting_name"`), а не класс `StatesGroup`: для новичка это одна понятная строка, а `maxapi.StateFilter` умеет её сравнивать. Сложные состояния остаются доступны через `bot.maxapi`/`bot.dispatcher`.
- [x] Состояние задаётся и читается методами `bot.*` с событием первым аргументом (`bot.set_state(message, "...")`); для вызовов вне обработчика тот же метод принимает `chat_id`/`user_id` — без второго API.
- [x] Фильтр состояния — параметр `state=` у любого обработчика плюс шорткат `@bot.on_state(...)`: одна фраза «в этом состоянии» вместо отдельной подсистемы.
- [x] Вебхук поднимает **своё** aiohttp-приложение (`AiohttpMaxWebhook.setup`), а не `Dispatcher.handle_webhook`: нужны дополнительные маршруты `/health` и `/stats` для мониторинга.
- [x] При `subscribe=True` секрет вебхука генерируется автоматически (`token_hex`, только допустимые MAX символы): безопасно по умолчанию и без лишних вопросов у новичка.
- [x] Подписка и запуск сервера разведены: `subscribe=False` позволяет поднять сервер локально или когда подписка уже настроена; ошибка подписки логируется и не роняет сервер.
- [x] Порт `0` разрешён, а фактический порт доступен как `bot.webhook_port` — это нужно и тестам, и запуску за прокси.
- [x] Мониторинг — middleware диспетчера, а не счётчики внутри обработчиков: так учитываются все события, включая те, под которые не нашлось обработчика.
- [x] Ошибки обработчиков ловит сам `Bot` (вместо `error_handlers` из `maxapi`): получается простой объект `Error` с `text`/`traceback`/`event`, счётчики и уведомление админа в одном месте.
- [x] Логи включены по умолчанию на INFO: главная проблема новичка — «бот молчит», а лог сразу показывает, дошло ли событие и что бот отправил. `log_level=None` отключает настройку.
- [x] `bot.send()` работает и без запущенного бота (отдельный цикл событий с закрытием aiohttp-сессии): разовое уведомление не требует поднимать поллинг.

## Decisions (1.0)
- [x] Rewrite the wrapper against the real MAX Bot API contract (`maxapi` 1.2) instead of patching 0.1: polling, sending and keyboards were broken end to end.
- [x] Rename the library to `MaxApiLib` (distribution name `MaxApiLib`, import name `maxapilib`): the old name described a Telegram-like API, which MAX is not.
- [x] Build on top of `maxapi.Dispatcher` instead of a hand-written polling loop: the dispatcher already parses updates into models, stores the `marker`, retries on network errors and supports `skip_updates`.
- [x] Keep the synchronous facade: a dedicated background thread with its own `asyncio` loop, while user handlers stay plain functions.
- [x] Run user handlers via `asyncio.to_thread` so a blocking handler cannot stall polling, and so `bot.send()` can synchronously wait for the HTTP result from another thread (`run_coroutine_threadsafe(...).result()`).
- [x] Give handlers first-class event objects (`Message`, `Callback`, `Started`) with sync `reply()`, `send()` and `answer()`, plus `raw` for full access to `maxapi` models.
- [x] Track the event being processed in a `contextvars.ContextVar`, so `bot.send()` without `chat_id` replies to the chat that triggered the handler.
- [x] Register handlers through `maxapi` filters (`TextPattern`, `CommandFilter`, `CallbackPayload`) instead of matching text inside the loop: filtering now happens in the dispatcher, before the handler thread is spawned.
- [x] Reject `async def` handlers with a clear error: they would silently never run, since the library awaits plain functions in a worker thread.
- [x] Do not auto-answer callbacks: MAX requires an explicit answer (`callback.answer()`), and sending an empty answer on every press would add unverifiable API calls. The behaviour is documented instead.
- [x] Validate MAX limits (210 buttons, 30 rows, 7/3 buttons per row, text and payload lengths) in `TextBox`/`Button` with Russian error messages, taken from the official API docs.
- [x] Keep `intent: "default"` in serialized callback buttons: it is `maxapi`'s model default and the API accepts it, so the library does not fight the upstream models.
- [x] Make `bot.run()` blocking by default and add `run(blocking=False)` + `wait()`: the 0.1 behaviour (return immediately) made the README example exit instantly.
- [x] Make timers daemon threads with a `cancel()` handle, so `every()` cannot keep the interpreter alive (0.1 hung pytest forever).
- [x] Translate `maxapi` errors into `MaxApiLibError` subclasses (`Auth`, `Network`, `API`, `Timeout`) to keep MAX API specifics out of user code.
- [x] Test the whole chain offline: tests replace `BaseConnection.request` with a fake MAX Bot API, so the suite needs no token and no network.

## Decisions (0.1, superseded)
- [x] Use `asyncio.run_coroutine_threadsafe` for a synchronous API facade over an asynchronous core.
- [x] Use `threading.Thread` to run the `asyncio` event loop, allowing the main thread to remain synchronous for the user.
- [x] Implement a `Button` class with factory methods to simplify the creation of various button types.
- [x] Use a `TextBox` class to manage the structure of messages, including nested rows of buttons.
- [x] Use `re.search` for pattern matching in `on_text` decorators to support flexible command handling.
- [x] Document all public APIs in Russian for a better user experience for Russian-speaking developers.
- [x] Ensure no `async`/`await` keywords are exposed in the public API.
