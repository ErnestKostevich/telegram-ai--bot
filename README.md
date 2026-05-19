<div align="center">

# 🤖 AI DISCO BOT

**Telegram-бот с искусственным интеллектом, памятью диалога и BYOK-архитектурой**

[![Telegram](https://img.shields.io/badge/Telegram-@AI__DISCO__BOT-26A5E4?logo=telegram&logoColor=white)](https://t.me/AI_DISCO_BOT)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PTB](https://img.shields.io/badge/python--telegram--bot-21+-2CA5E0)](https://docs.python-telegram-bot.org/)
[![Render](https://img.shields.io/badge/Hosted_on-Render-46E3B7?logo=render&logoColor=white)](https://render.com/)
[![Version](https://img.shields.io/badge/Version-v2.0.0-brightgreen)](https://github.com/ErnestKostevich/telegram-ai--bot/blob/main/CHANGELOG.md)

[Возможности](#-возможности) · [Команды](#-команды) · [Быстрый старт](#-быстрый-старт) · [Деплой](#%EF%B8%8F-деплой-на-render) · [Архитектура](#-архитектура) · [Roadmap](#%EF%B8%8F-roadmap)

</div>

---

## ✨ Возможности

| | |
|---|---|
| 🧠 **Память диалога** | Бот помнит до 10 пар сообщений — настоящий многоходовой чат, а не разовые запросы |
| 🔌 **BYOK** | Bring Your Own Key: 10+ AI-провайдеров на выбор, ключи остаются у пользователя |
| 👁 **Vision** | Анализ фотографий (OpenAI · Anthropic · Gemini · OpenRouter) |
| 📎 **Документы** | Разбор `.txt` / `.md` / `.json` / `.xml` файлов через AI |
| 🖼 **Генерация изображений** | DALL·E 3 (OpenAI) или FLUX.1-schnell (Together) |
| 🌐 **3 языка интерфейса** | RU / EN / IT — переключение в один клик |
| 💎 **VIP-система** | Срок: неделя / месяц / год / навсегда + авто-истечение |
| 👥 **Полноценное управление группами** | Модерация, AI-сводки, антиспам, антилинк, welcome/goodbye |
| ⏰ **Напоминания** | Точность до минуты, фоновый scheduler (VIP) |
| 🗄 **Персистентное хранилище** | JSON-файл в GitHub-репозитории через GitHub API — переживает рестарты Render |
| 🎮 **Геймификация** | XP, уровни, ежедневные награды со streak'ом, репутация, шутки, прожарка |

## 🔌 Поддерживаемые AI-провайдеры

| Провайдер | Модели по умолчанию | Vision | Где получить ключ |
|---|---|:---:|---|
| **Gemini** | `gemini-2.0-flash` | ✅ | [ai.google.dev](https://ai.google.dev/) |
| **OpenAI** | `gpt-4o-mini` | ✅ | [platform.openai.com](https://platform.openai.com/api-keys) |
| **Anthropic** | `claude-3-5-sonnet` | ✅ | [console.anthropic.com](https://console.anthropic.com/) |
| **Groq** | `llama-3.3-70b-versatile` | — | [console.groq.com](https://console.groq.com/keys) |
| **Together** | `Llama-3.3-70B` | — | [api.together.xyz](https://api.together.xyz/settings/api-keys) |
| **OpenRouter** | `llama-3.3-70b` | ✅ | [openrouter.ai](https://openrouter.ai/keys) |
| **Mistral** | `mistral-large-latest` | — | [console.mistral.ai](https://console.mistral.ai/) |
| **Cohere** | `command-r-plus` | — | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| **xAI** | `grok-3-mini` | — | [console.x.ai](https://console.x.ai/) |
| **DeepSeek** | `deepseek-chat` | — | [platform.deepseek.com](https://platform.deepseek.com/) |

## 🚀 Быстрый старт (для пользователя)

1. Откройте [@AI_DISCO_BOT](https://t.me/AI_DISCO_BOT) в Telegram
2. Нажмите **Start** или отправьте `/start`
3. ⚙️ **Настройки** → ⚡ Провайдер — выберите AI
4. 🔑 Установите ключ: `/setkey gemini ВАШ_КЛЮЧ`
5. Просто пишите боту — он запомнит контекст диалога

## 📚 Команды

<details open>
<summary><b>🏠 Базовые</b></summary>

| Команда | Описание |
|---|---|
| `/start` | Запуск бота, главное меню |
| `/help` | Интерактивная справка по разделам |
| `/info` | О боте, версия, сборка |
| `/status` | Состояние системы |
| `/version` | Версия бота |
| `/changelog` | История обновлений |
| `/profile` | Профиль, XP, уровень, статистика |
| `/export` | Скачать ваши данные одним JSON-файлом |
| `/feedback [текст]` | Отправить отзыв создателю |
| `/lang ru\|en\|it` | Сменить язык |
| `/disco on\|off` | Творческий режим AI |

</details>

<details>
<summary><b>💬 AI и память</b></summary>

| Команда | Описание |
|---|---|
| `/ai [вопрос]` | Спросить AI |
| _Просто напишите боту_ | В личке работает контекстный чат — бот помнит последние 10 пар сообщений |
| `/clear` | Сбросить контекст диалога |
| `/setprovider` | Выбрать провайдера AI (интерактивно) |
| `/setkey [пров] [ключ]` | Установить API-ключ (сообщение с ключом удаляется автоматически) |
| `/setmodel [модель]` | Выбрать конкретную модель |
| `/memorysave [ключ] [значение]` | Сохранить факт в долгую память |
| `/memoryget [ключ]` | Получить факт |
| `/memorylist` | Все сохранённые факты |
| `/memorydel [ключ]` | Удалить факт |

</details>

<details>
<summary><b>📝 Заметки и задачи</b></summary>

| Команда | Описание |
|---|---|
| `/note [текст]` | Создать заметку |
| `/notes` | Показать все |
| `/delnote [#]` | Удалить по номеру |
| `/todo [текст]` | Добавить задачу |
| `/todo` | Список задач |
| `/todo done [#]` | Отметить выполненной |
| `/todo del [#]` | Удалить задачу |

</details>

<details>
<summary><b>💎 VIP</b></summary>

| Команда | Описание |
|---|---|
| `/vip` | Статус VIP |
| `/remind [мин] [текст]` | Напоминание (1–43200 мин) |
| `/reminders` | Список активных напоминаний |
| `/generate [описание]` | Сгенерировать изображение |
| _Отправьте фото в личку_ | AI опишет содержимое |
| _Отправьте .txt/.md/.json_ | AI разберёт файл |
| `/daily` | Ежедневная награда + streak |

</details>

<details>
<summary><b>👥 Группы</b></summary>

**Модерация:**
| Команда | Описание |
|---|---|
| `/warn` (reply) | Предупреждение, 3-е = автобан |
| `/warnings` (reply / без аргументов) | Посмотреть варны |
| `/unwarn` (reply) | Снять варн |
| `/mute [мин]` (reply) | Замутить |
| `/unmute` (reply) | Размутить |
| `/ban` (reply) | Забанить |
| `/kick` (reply) | Кикнуть |
| `/purge [N]` | Удалить N сообщений (или удалить диапазон по reply) |
| `/antilink on\|off` | Авто-удаление ссылок от не-админов |
| `/antispam on\|off` | AntiSpam |
| `/guardian on\|off` | AI-модератор |

**AI в группах:**
| Команда | Описание |
|---|---|
| `/ask [вопрос]` | Спросить AI прямо в группе |
| `/summary` | Реальная сводка последних сообщений чата |
| `/translate [язык] [текст]` | Перевод |
| `/translate [язык]` (reply) | Перевести сообщение, на которое отвечаете |
| `@бот [вопрос]` | Ответ по упоминанию |

**Управление:**
| Команда | Описание |
|---|---|
| `/rules` · `/setrules [текст]` | Правила группы |
| `/welcome on\|off [текст]` | Приветствие новых участников (`{name}`, `{title}`) |
| `/goodbye on\|off [текст]` | Прощание уходящим |
| `/groupstats` | Статистика группы |
| `/grouphelp` | Полная справка по группе |

</details>

<details>
<summary><b>🎮 Игры и утилиты</b></summary>

| Команда | Описание |
|---|---|
| `/dice` | Кубик 🎲 |
| `/coinflip` | Монетка 🪙 |
| `/random [от] [до]` | Случайное число |
| `/joke` | Шутка |
| `/roast` (reply) | AI-прожарка |
| `/rep` (reply) | +1 к репутации |
| `/time [город]` | Время в городе |
| `/weather [город]` | Погода |
| `/calc [выражение]` | Калькулятор |
| `/password [длина]` | Генератор паролей (8–64) |

</details>

<details>
<summary><b>👑 Команды создателя</b></summary>

| Команда | Описание |
|---|---|
| `/grant_vip @user week\|month\|year\|forever` | Выдать VIP |
| `/grant_vip @user remove` | Снять VIP |
| `/users` | Список пользователей (топ по активности) |
| `/broadcast [текст]` | Рассылка всем (rate-limited ~25 msg/сек, live progress) |
| `/stats` | Детальная статистика бота |

</details>

## 🏗 Архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                    Telegram Bot API                          │
└──────────────────────────┬───────────────────────────────────┘
                           │ polling
                ┌──────────▼──────────┐
                │  python-telegram-bot │
                │     (PTB v21)        │
                └──────────┬───────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
   ┌─────▼─────┐   ┌──────▼──────┐   ┌──────▼──────┐
   │ Handlers  │   │  AIHandler  │   │  Scheduler   │
   │ (commands │   │  ┌────────┐ │   │ (APScheduler)│
   │  buttons, │   │  │ Gemini │ │   │              │
   │  inline)  │   │  │ OpenAI │ │   │   reminders  │
   │           │   │  │Anthropic│ │   │              │
   │           │   │  │  +7    │ │   │              │
   └─────┬─────┘   │  └────────┘ │   └──────┬───────┘
         │         └──────┬──────┘          │
         │                │                 │
         └────────────────▼─────────────────┘
                          │
                  ┌───────▼───────┐
                  │    Storage     │
                  │   (in-memory   │
                  │    dict)       │
                  └───────┬────────┘
                          │ save/load
                  ┌───────▼────────┐
                  │  GitHub API    │
                  │  bot_data.json │
                  └────────────────┘
```

### Структура проекта

```
telegram-ai--bot/
├── main.py                     # Точка входа, регистрация handlers
├── render.yaml                 # Конфиг деплоя на Render
├── requirements.txt
├── .env.example                # Шаблон переменных окружения
├── CHANGELOG.md                # История версий
└── bot/
    ├── config.py               # ENV + константы (BOT_VERSION, лимиты)
    ├── ai.py                   # Унифицированный AIHandler для всех провайдеров
    ├── storage.py              # In-memory storage + GitHub API persistence
    ├── scheduler.py            # APScheduler для напоминаний
    ├── keyboards.py            # Reply & Inline клавиатуры
    ├── i18n.py                 # 3-язычные строки (RU/EN/IT, 145 ключей × 3)
    └── handlers/
        ├── base.py             # /start /help /info /profile /version /changelog
        ├── ai_memory.py        # /ai /clear /setprovider /setkey /setmodel + memory
        ├── notes.py            # /note /notes /todo
        ├── vip_creator.py      # /vip /remind /feedback + creator commands
        ├── groups.py           # Модерация + AI в группах + tracker
        ├── games.py            # /dice /coinflip /random /joke
        ├── extended.py         # /daily /rep /roast
        ├── utils.py            # /time /weather /calc /password
        ├── media.py            # Vision + document analysis + /generate
        └── interactive.py      # Inline buttons, conversation states, default AI handler
```

## 🛠 Локальная разработка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/ErnestKostevich/telegram-ai--bot.git
cd telegram-ai--bot

# 2. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Скопировать .env.example в .env и заполнить
cp .env.example .env

# 5. Запустить
python main.py
```

### Получение токенов

| Переменная | Где взять |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `CREATOR_ID` | [@userinfobot](https://t.me/userinfobot) — ваш Telegram ID |
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) — fine-grained PAT с правом write на репо данных |
| `GITHUB_REPO` | Создайте репо для хранения JSON, например `username/telegram-ai-bot-db` |

## ☁️ Деплой на Render

1. Форкните репозиторий
2. На [Render](https://dashboard.render.com/) создайте новый **Background Worker** из этого репо
3. Render автоматически подхватит `render.yaml`
4. В Environment Variables укажите все ключи из таблицы выше
5. Render будет авто-деплоить каждый push в `main`

```yaml
# render.yaml (уже в репо)
services:
  - type: worker
    name: telegram-ai-bot
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
```

## 🔒 Безопасность

- Сообщения с командой `/setkey` **автоматически удаляются** после сохранения ключа
- Ключи хранятся только в JSON, доступном по GitHub-токену создателя
- Бот не отправляет данные третьим лицам — все AI-вызовы идут напрямую к выбранному провайдеру по ключу пользователя
- `/calc` ограничен `eval` с белым списком символов и лимитом длины
- AntiLink удаляет ссылки только от не-админов
- 3 предупреждения автоматически приводят к бану

## 🗺️ Roadmap

- [ ] 🎙 Голосовые сообщения (Whisper)
- [ ] 📊 Web-дашборд для создателя
- [ ] 🤝 Multi-creator support
- [ ] 📚 Сохранение и поиск по истории диалогов
- [ ] 🧩 Плагины / кастомные команды
- [ ] 💳 Опциональные платные подписки (Stars)
- [ ] 🌐 Больше языков (DE / ES / FR / ZH)

## 📜 Changelog

См. [CHANGELOG.md](CHANGELOG.md) — полная история версий.

**Текущая версия: v2.0.0** (2026-05-20) — память диалога, vision, реальные группы, broadcast rate-limit, и многое другое.

## 🤝 Вклад

Идеи, баги и фичи приветствуются:

- 🐛 [Открыть Issue](https://github.com/ErnestKostevich/telegram-ai--bot/issues)
- 💌 `/feedback [текст]` прямо в бот
- 📬 Telegram: [@Ernest_Kostevich](https://t.me/Ernest_Kostevich)

## 📄 Лицензия

Проект распространяется как есть, для образовательных и личных целей.

## 👤 Автор

**Ernest Kostevich**
[![Telegram](https://img.shields.io/badge/Telegram-@Ernest__Kostevich-26A5E4?logo=telegram&logoColor=white)](https://t.me/Ernest_Kostevich)
[![GitHub](https://img.shields.io/badge/GitHub-ErnestKostevich-181717?logo=github&logoColor=white)](https://github.com/ErnestKostevich)

---

<div align="center">

⭐ Если проект полезен — поставьте звезду на GitHub

[Запустить бота →](https://t.me/AI_DISCO_BOT)

</div>
