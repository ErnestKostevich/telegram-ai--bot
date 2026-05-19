# Changelog

Все значимые изменения в проекте AI DISCO BOT.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии следуют [Semantic Versioning](https://semver.org/lang/ru/).

---

## [2.0.0] — 2026-05-20

### 🎉 Major release: "Memory & Vision"

#### Added
- 🧠 **Память диалога** — `AIHandler` теперь хранит и передаёт историю последних 10 пар сообщений на пользователя
- 👁 **Vision API** — анализ фотографий для OpenAI, Anthropic, Gemini, OpenRouter
- 📎 **Анализ документов** — разбор `.txt` / `.md` / `.json` / `.xml` файлов (VIP)
- 📝 **Реальный `/summary`** в группах: бот трекает последние 60 сообщений и делает настоящую AI-сводку (было: заглушка с фиктивным резюме)
- 🛡 **Полноценная модерация групп:**
  - `/warn` со счётчиком — на 3-м варне автобан
  - `/warnings` — посмотреть варны
  - `/unwarn` — снять предупреждение
  - `/unmute` — размутить
  - `/purge [N]` — реальное удаление сообщений (или диапазон по reply)
  - `/antilink on|off` — авто-удаление ссылок от не-админов
  - `/antispam on|off` — переключатель
- 👋 **Welcome / Goodbye** — настраиваемые приветствия и прощания с подстановкой `{name}` и `{title}`
- 💬 **Новые команды:**
  - `/clear` — сброс контекста диалога
  - `/feedback [текст]` — отправить отзыв создателю
  - `/export` — выгрузить ваши данные в JSON
  - `/changelog` — история обновлений в боте
  - `/version` — информация о версии
- 🌍 `/translate [язык]` теперь работает по reply на сообщение
- 🎁 `/daily` — теперь со streak'ом и бонусом за подряд идущие дни
- 📣 `/broadcast` теперь с rate-limit (~25 msg/сек) и живым прогресс-индикатором
- 📱 BotCommand-меню — Telegram теперь показывает правильное меню команд для личных и групповых чатов

#### Changed
- 🌐 AI ошибки локализованы для RU / EN / IT (раньше всё было захардкожено на русском)
- ⏱ Таймаут всех AI-вызовов — 60 секунд
- 🎨 Генерация изображений: Together использует FLUX.1-schnell, OpenAI — DALL·E 3, без cross-provider утечек ключей
- 👤 `/profile` показывает количество заметок, задач, memory-записей и длину истории диалога
- ⚙️ Settings keyboard теперь включает «🧹 Очистить контекст»
- 🌤 `/weather` URL-кодирует город, передаёт User-Agent и язык интерфейса
- ⏰ `/time` сначала ищет точное совпадение `Region/City`, потом по подстроке (исправляет случаи когда «us» матчилось на десятки таймзон)
- 🧮 `/calc` ограничен 200 символами входа
- 📜 Welcome-сообщение, `/info`, `/help` переписаны и упоминают новые возможности

#### Fixed
- 🐛 Backward-compatible storage: `chat_history`, `messages`, `warns` автоматически добавляются к существующим пользователям и группам
- 🐛 `disco_off` теперь корректно передаёт `parse_mode="HTML"` через `/disco off`
- 🐛 Group message tracker зарегистрирован с `group=-1`, что исключает конфликт с обработчиком @упоминаний

#### Removed
- ❌ Mock-команды-заглушки (`coming soon` стабы), вместо них — реальные реализации или удаление: `purge`, `antilink`, `antispam`, `welcome`, `goodbye`, `warnings`, `unwarn`, `unmute`

### 📊 Цифры релиза

- 17 файлов изменено
- +2039 / −523 строки
- 145 i18n-ключей × 3 языка = 435 переводов

---

## [1.0.0] — Comeback (BYOK Edition)

### Added
- 🔌 BYOK архитектура: 10+ AI-провайдеров (Gemini, OpenAI, Anthropic, Groq, Together, OpenRouter, Mistral, Cohere, xAI, DeepSeek)
- 🌐 Локализация на 3 языка: RU / EN / IT
- 💎 VIP-система с длительностью: неделя / месяц / год / навсегда + авто-истечение
- 👑 Команды создателя: `/grant_vip`, `/users`, `/broadcast`, `/stats`
- 🎮 Игры: dice, coinflip, random, joke, roast, daily, rep
- 🛠 Утилиты: time, weather, calc, password
- 🖼 Генерация изображений (DALL·E)
- ⏰ Напоминания (VIP)
- 🧠 Долгая память (key-value)
- 📝 Заметки и todo-задачи
- 👥 Базовая модерация групп (warn / mute / ban / kick)
- 🛡 AI Guardian
- 🪩 Disco Mode
- 🗄 Хранилище через GitHub API
- 📱 Интерактивный UI с inline-кнопками

---

## Условные обозначения

- 🎉 Major release
- ✨ Added — новые фичи
- 🔄 Changed — изменения существующих
- 🐛 Fixed — багфиксы
- ❌ Removed — удалено
- 🔒 Security — связано с безопасностью
- ⚠️ Deprecated — устаревшее
