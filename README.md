# 🤖 AI DISCO BOT

Многофункциональный Telegram-бот с искусственным интеллектом, BYOK-архитектурой и памятью диалога.

**Telegram:** [@AI_DISCO_BOT](https://t.me/AI_DISCO_BOT)

## ⚡ Главное

- 🧠 **Память диалога** — бот помнит последние сообщения, как настоящий чат
- 🔌 **BYOK** — Bring Your Own Key: 10+ провайдеров (Gemini, OpenAI, Anthropic, Groq, Together, OpenRouter, Mistral, Cohere, xAI, DeepSeek)
- 👁 **Vision** — анализ фото для OpenAI / Anthropic / Gemini / OpenRouter
- 📎 **Документы** — разбор `.txt` / `.md` / `.json` / `.xml`
- 🖼 **Генерация изображений** — DALL·E 3 или Together FLUX
- 🌐 **3 языка** — RU / EN / IT
- 💎 **VIP-система** с длительностью (неделя/месяц/год/навсегда) и авто-истечением
- 👥 **Группы** — модерация (warn → авто-бан на 3-м), antilink, antispam, welcome/goodbye, реальный `/summary` чата
- ⏰ **Напоминания** с минутной точностью (VIP)
- 🗄 **Хранилище через GitHub API** — данные переживают рестарт хостинга

## 🚀 Команды

### 🏠 Базовые
- `/start` — запуск
- `/help` — справка
- `/info` — о боте
- `/status` — состояние
- `/version` `/changelog` — версия и история обновлений
- `/profile` — XP, провайдер, статистика
- `/export` — выгрузить ваши данные JSON
- `/feedback [текст]` — отправить отзыв создателю
- `/lang ru|en|it` — язык

### 💬 AI & память
- `/ai [вопрос]` — спросить AI
- В личке просто пишите — бот помнит контекст
- `/clear` — сбросить контекст диалога
- `/setprovider /setkey /setmodel` — настройка BYOK
- `/memorysave /memoryget /memorylist /memorydel` — постоянная память

### 📝 Заметки и задачи
- `/note /notes /delnote`
- `/todo` `/todo done [#]` `/todo del [#]`

### 💎 VIP
- `/vip` — статус
- `/remind [мин] [текст]` — напоминание
- `/generate [описание]` — картинка
- Фото / документ в личке — анализ AI
- `/daily` — ежедневная награда + streak

### 👥 Группы
- `/warn` `/warnings` `/unwarn` (3 варна = автобан)
- `/mute [мин]` `/unmute` `/ban` `/kick`
- `/purge [N]` — удалить N сообщений (или в reply)
- `/antilink on|off` — авто-удаление ссылок от не-админов
- `/antispam on|off` `/guardian on|off`
- `/ask` `/summary` `/translate [язык] [текст]` — AI в группе
- `/welcome on|off [текст]` `/goodbye on|off [текст]` (используйте `{name}` и `{title}`)
- `/rules` `/setrules` `/groupstats`
- `@бот [вопрос]` — отвечает по упоминанию

### 🎮 Игры и утилиты
- `/dice` `/coinflip` `/random` `/joke` `/roast` `/rep`
- `/time [город]` `/weather [город]` `/calc [выражение]` `/password [длина]`

### 👑 Создатель
- `/grant_vip [@user] [week|month|year|forever|remove]`
- `/users` — топ по активности
- `/broadcast` — рассылка с rate-limit (~25 msg/sec)
- `/stats` — детальная статистика бота

## 🔧 Технологии

- Python 3.11+, `python-telegram-bot` ≥ 21.5
- `aiohttp` для всех HTTP-вызовов AI
- `apscheduler` — напоминания
- GitHub API — хранилище JSON (репо `telegram-ai-bot-db`)
- Render — хостинг (free worker)

## ⚙️ Деплой

ENV переменные (на Render):

| Key | Назначение |
|-----|------------|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `GITHUB_TOKEN` | PAT с правом write на репо данных |
| `GITHUB_REPO` | `username/telegram-ai-bot-db` |
| `GITHUB_FILE_PATH` | `bot_data.json` (по умолчанию) |
| `CREATOR_ID` | Telegram ID создателя |

## 👤 Создатель

**Ernest Kostevich** ([@Ernest_Kostevich](https://t.me/Ernest_Kostevich))

---
*Деплой автоматический из ветки `main` через Render.*
