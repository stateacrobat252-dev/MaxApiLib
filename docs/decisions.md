# Decisions

This file contains all architectural decisions made during the development of `maxbot-easy`.

## Decisions
- [x] Use `asyncio.run_coroutine_threadsafe` for a synchronous API facade over an asynchronous core.
- [x] Use `threading.Thread` to run the `asyncio` event loop, allowing the main thread to remain synchronous for the user.
- [x] Implement a `Button` class with factory methods to simplify the creation of various button types (callback, link, contact, etc.).
- [x] Use a `TextBox` class to manage the structure of messages, including nested rows of buttons.
- [x] Use `re.search` for pattern matching in `on_text` decorators to support flexible command handling.
- [x] Use `Any` for `attachments` and `get_updates` return types in `MaxBotClient` to maintain compatibility with the `maxapi` package while keeping mypy happy.
- [x] Document all public APIs in Russian for a better user experience for Russian-speaking developers.
- [x] Ensure no `async`/`await` keywords are exposed in the public `maxbot_easy` API.
