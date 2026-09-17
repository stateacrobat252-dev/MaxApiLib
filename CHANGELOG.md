# Changelog

## [1.0.0] - 2026-09-17
### Изменено
- Библиотека переименована: `maxbot-easy` → **MaxApiLib** (пакет `maxapilib`).
- Обёртка полностью переписана под реальный контракт MAX Bot API
  (`maxapi` 1.2). Версия 0.1 не работала: события не обрабатывались,
  сообщения уходили не туда, клавиатура не принималась API.

### Исправлено
- `Bot.send`/`Message.reply` передают `chat_id`/`user_id` и текст в
  правильные параметры `maxapi.Bot.send_message` (раньше текст уходил
  в `chat_id`).
- Обновления читаются через `Dispatcher` библиотеки `maxapi`: события
  разбираются в модели, сохраняется `marker`, есть retry при сбоях сети
  (раньше итерация шла по ключам словаря `{"updates": [...], "marker": N}`,
  то есть события не доходили до обработчиков вообще).
- Клавиатура собирается в формате MAX API
  (`{"type": "inline_keyboard", "payload": {"buttons": [[...]]}}`)
  и проверяется моделями `maxapi`. Раньше отправлялся невалидный JSON
  с полем `callback_data` из Telegram.
- Текст сообщения читается из `message.body.text`; нажатие кнопки — из
  `callback.payload` (раньше использовались несуществующие `msg.text`
  и `callback_query`).
- `later()` и `every()` работают в демон-потоках и возвращают `Timer`
  с `cancel()`: раньше `every()` держал процесс навсегда (тесты и боты
  не завершались).
- `bot.run()` по умолчанию блокирует поток до Ctrl+C (раньше возвращал
  управление сразу, и скрипт из README завершался вместе с ботом).
- Ошибки API превращаются в понятные исключения MaxApiLib
  (`MaxApiLibAuthError` при 401, `MaxApiLibNetworkError` при обрыве связи).

### Добавлено
- Обработчики `on_command`, `on_text`, `on_button`, `on_callback`,
  `on_message`, `on_started`; порядок регистрации = порядок проверки.
- Удобные объекты событий `Message`, `Callback`, `Started` с готовыми
  `reply()`, `send()`, `answer()` и доступом к исходным моделям `maxapi`.
- Кнопки `message`, `clipboard`, `open_app` (кроме `callback`, `link`,
  `contact`, `location`); проверка лимитов MAX (210 кнопок, 30 рядов,
  7/3 кнопки в ряду, длины текста, payload и ссылок).
- `enable_logging()` для отладки, `call_timeout` для синхронных вызовов,
  `skip_updates` для пропуска старых событий.
- Тесты на сквозной путь (поллинг → обработчик → отправка) без сети:
  122 теста, покрытие 98%, прогон ~2 секунды.

### Удалено
- `Button.chat()` — тип кнопки устарел в самом MAX API (`maxapi` помечает
  его DeprecationWarning).

## [0.1.0] - 2024-05-20
### Added
- Initial release of `maxbot-easy`.
- Support for synchronous bot interaction.
- Core types: `TextBox`, `Button`.
- Time utilities: `later`, `every`, `parse_time`.
- Handlers: `on_text`, `on_button`, `on_message`.
