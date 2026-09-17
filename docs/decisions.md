# Decisions

This file contains all architectural decisions made during the development of `MaxApiLib`.

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
