# Changelog

## [1.1.0] - 2026-09-17
### Добавлено
- **Состояния (FSM) и данные пользователя**: `bot.set_state`, `bot.get_state`,
  `bot.set_data`, `bot.get_data`, `bot.reset_state`, декоратор `@bot.on_state("имя")`
  и параметр `state="имя"` у любых обработчиков. Хранение — через контексты
  `maxapi` (в памяти, можно Redis: `Bot(storage=RedisContext)`).
- **Вебхуки**: `bot.run_webhook(url)` поднимает aiohttp-сервер, сам подписывает бота,
  генерирует `secret` и проверяет заголовок `X-Max-Bot-Api-Secret`.
  Дополнительно: `bot.webhooks()` и `bot.delete_webhook()` для возврата к поллингу.
- **Мониторинг**: middleware считает каждое событие (даже без обработчика);
  `bot.stats` (читается глазами и отдаётся как `as_dict()`), в режиме вебхука —
  адреса `GET /health` и `GET /stats`.
- **Логирование**: включено по умолчанию (INFO) — в логе видно каждое событие
  и каждую отправку; `Bot(log_level=..., log_file=...)`, `enable_logging(level, file=)`.
- **Обработка ошибок**: ошибка в обработчике не роняет бота, а попадает в лог,
  в счётчики и в `@bot.on_error()`; можно получать уведомления в MAX
  (`Bot(admin_id=...)`).
- Отправка сообщений работает и без запуска бота: `bot.send(...)` для разовых
  уведомлений в своём временном цикле событий.
- Примеры `examples/form_bot.py` (анкета на состояниях) и
  `examples/webhook_bot.py` (вебхук + мониторинг); extra `webhook` для aiohttp.

### Изменено
- Логи библиотеки теперь включены по умолчанию (уровень INFO); `Bot(log_level=None)`
  оставляет настройку логирования приложению.
- Вместо ошибки «Бот не запущен» `bot.send()`/`bot.reply()` работают и вне
  запущенного бота (разовые вызовы).

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
  и проверяется моделями `maxapi`. Раньше отправлялся невалидный JSON,
  который не принимался API мессенджера MAX.
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
