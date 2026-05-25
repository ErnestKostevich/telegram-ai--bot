# Changelog

Все значимые изменения в проекте AI DISCO BOT.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии следуют [Semantic Versioning](https://semver.org/lang/ru/).

---

## [2.5.0] — 2026-05-25 🎤 Phase 2 closeout — TTS + multi-quiz + weekly LB + proactive memory

### 🎙 TTS voice reply (Phase 2.3)
- `/voice on|off` — bot speaks every AI answer as a Telegram voice message
- `/voice <name>` picks one of 6 OpenAI voices (alloy/echo/fable/onyx/nova/shimmer)
- Uses user's own OpenAI key (BYOK), OGG/opus format Telegram accepts natively
- Silent fallbacks if key missing or TTS errors — never breaks the text reply

### 🧠 Multi-question quiz session (Phase 2.2)
- `/quizgame [topic] [N]` — N questions on a topic (2 ≤ N ≤ 10, default 5)
- Each correct answer awards XP, weekly stats tracked
- Final scoreboard with medal (🏆/🥇/🥈/🥉/📚) based on % correct
- Auto-generates next question after each answer

### 🏆 Weekly leaderboard (Phase 2.5)
- `/leaderboard` — all-time top
- `/leaderboard weekly` — current ISO week only
- `award_weekly_xp()` fires +5 per successful AI turn
- `xp_by_week` capped at last 8 weeks per user (storage-bounded)

### 💾 Proactive memory (Phase 2.6) — the killer differentiator vs ChatGPT
- After every 6 message-pairs, bot quietly asks AI: "did the user reveal stable facts?"
- Suggests up to 3 with inline buttons: 💾 Save individually, 💾 Save all, ✕ Skip
- Sanitizes keys to snake_case, skips ones already in memory
- Fire-and-forget — never blocks AI replies
- Hard caps: 3 pending batches per user, 50 memory entries total

### 🐛 Critical bug fix (silent since v2.0.3)
- `t(lang, "key_name", key=value)` crashed silently with TypeError because the
  `t()` function parameter was also named `key`. The outer try/except in callers
  swallowed it, so /memorysave, /memoryget, /memorydel, /mem_value, /mem_not_found
  had been broken for HTML-escape paths for weeks.
- Fix: renamed `t()`'s second parameter from `key` → `i18n_key`. Callers unchanged.

### Plumbing
- New `bot/handlers/proactive.py` (~200 lines)
- TTS hooks at end of streaming reply (`media.maybe_speak_response`)
- Proactive memory hook via `asyncio.create_task(...)` — non-blocking
- `bot/handlers/__init__.py`, `main.py` updated with new commands and callback patterns
- 19 new i18n keys × 3 langs (243 keys/lang total, parity verified)
- BOT_VERSION 2.4.0 → 2.5.0

### Tested (23 in-session checks, all green)
1. main.py loads with v2.5.0 additions
2-4. i18n parity, version, handler exports
5-9. TTS module: 6 voices, no-ops when off / no key / error / errors swallowed
10-12. /voice command: on, off, refused without key, pick voice
13-14. award_weekly_xp accumulates in ISO week, caps at 8 weeks, ignores ≤ 0
15. /leaderboard weekly sorts by current-week XP
16-17. /quizgame creates session, N clamped [2..10] with default 5
18-19. Proactive memory: triggers after N turns, sanitizes keys, sends UI
20-22. memory_suggest_callback: msave/msaveall/mskip work correctly
23. No callback_data collisions with 40+ existing handlers

### ROADMAP Phase 2 status
- ✅ 2.2 Multi-quiz
- ✅ 2.3 TTS
- ✅ 2.4 Smart reminders (v2.4.0)
- ✅ 2.5 Weekly leaderboard
- ✅ 2.6 Proactive memory
- ⏳ 2.1 Morning digest (deferred — needs per-user timezone)

**Phase 2 effectively COMPLETE** (5 of 6 items; morning digest deferred).

---

## [2.4.0] — 2026-05-25 🔔 Smart reminders (Phase 2.4 from ROADMAP)

### Natural-language `/remind`
- `/remind завтра в 9 утра позвонить маме` — works
- `/remind tomorrow at 9am call mom` — works
- `/remind in 2 hours buy bread` — works
- Plus the classic `/remind 30 текст` still works as a fast path
  (no AI call when the first arg is a valid integer)

### Implementation
- New `_ai_parse_reminder()` asks the user's AI (uses their own key,
  BYOK-consistent) to extract `{minutes, text}` as strict JSON.
- Markdown-fence stripping fallback (some models love wrapping JSON in
  ```json …``` despite instructions).
- Validation: `minutes >= 1`, `minutes <= MAX_REMIND_MINUTES`
  (1 year — generous for NL dates like "next Christmas").
- AI is bypassed entirely when the user uses the classic numeric form —
  saves a key call and keeps things instant.

### UX
- "Parsing the time..." indicator while AI thinks (1-3 sec usually).
- Friendly error if AI returns 0 minutes or bad JSON.
- "Needs AI key" hint with `/setkey` shortcut for users without a key.
- Success message renders human time ("⏰ Reminder in 1h 30min").
- `/remind` with no args shows the new triple-example usage card.

### Plumbing
- Cleaner `_humanize_minutes()` — handles 5m / 1h / 1h30m / 1d / 3d
  in all 3 langs.
- 4 new i18n keys × 3 langs (224 keys total per lang, parity verified).
- `BOT_VERSION` 2.3.0 → 2.4.0.

### Tested (15 in-session verifications, all green)
1. Symbols import; main.py loads
2. i18n parity 224 × 3, new reminder keys present
3. `_humanize_minutes`: 5m / 1h / 1h30m / 1d / 3d
4. `MAX_REMIND_MINUTES` is 1 year
5. `_ai_parse_reminder` happy path with valid JSON
6. Markdown-fenced JSON gets stripped
7. AI returning `minutes: 0` → None + reason
8. Malformed JSON → None + error
9. Time too far in future → rejected
10. Classic `/remind 30 text` doesn't call AI (verified by counter)
11. NL `/remind` triggers AI, reminder saved with parsed minutes+text
12. NL `/remind` without API key → friendly "needs key" error
13. `/remind` with no args → usage card
14. Non-VIP user blocked from `/remind`
15. BOT_VERSION == 2.4.0

---

## [2.3.0] — 2026-05-25 🌐 Inline mode (Phase 1.3 — Phase 1 COMPLETE)

### 💬 @AI_DISCO_BOT works in any Telegram chat
- Type `@AI_DISCO_BOT [question]` in any chat (DM, group, channel
  comments) → bot pops up an article card.
- Pick the card → a placeholder message with an **✨ Generate** button
  lands in the chat.
- Tap **Generate** → AI runs (using the asker's own key) → message is
  edited in place with the answer + "via @AI_DISCO_BOT" footer.

### BYOK respected
- If the user invoking inline has no API key, results are empty and
  Telegram's `switch_pm_text` opens the bot in DM with parameter
  `from_inline` → automatically starts the onboarding wizard, with a
  small intro line "set up your key to use me anywhere".
- Generate button rejects non-askers with a polite alert ("only the
  original asker can generate, uses their key").

### Implementation
- New module `bot/handlers/inline.py` (~180 lines).
- 2-step UX because inline queries must answer within ~3s but AI takes
  much longer: the placeholder + Generate-button pattern works without
  needing BotFather's inline-feedback setting enabled.
- In-memory query cache (`_QUERY_CACHE`), `short_id` via `secrets.token_urlsafe(8)`,
  guaranteed to fit in Telegram's 64-byte callback_data limit when
  prefixed with `ig_`. 1-hour TTL, opportunistic GC on insert, hard cap
  at 5000 entries.
- User-supplied query is HTML-escaped before rendering in the placeholder.
- `_user_has_any_key()` detects empty strings as "no key" — supports
  partial state from older user records.

### Plumbing
- `main.py`: registers `InlineQueryHandler` and a dedicated
  `CallbackQueryHandler(pattern=r"^ig_")` BEFORE the catch-all.
- `start_command`: detects `/start from_inline` and shows a focused
  intro line before launching the wizard.
- 12 new i18n keys × 3 languages (220 keys total per lang, parity
  verified).
- `BOT_VERSION` 2.2.2 → 2.3.0 (Phase 1 complete = minor bump).

### Tested (16 in-session verifications)
1. inline module imports cleanly; main.py loads
2. i18n parity: 220 keys × 3 langs, 12 new inline keys present
3. `inline_ask_title` interpolates `{q}` correctly
4. Cache stores `(author_uid, query, ts)` and returns short_id
5. short_id is URL-safe and `ig_<sid>` fits in 64 bytes
6. `_gc_cache` drops entries older than TTL, keeps fresh ones
7. Cache hard-capped at 5000 entries
8. `_user_has_any_key` correctly detects empty-string-as-no-key
9. Keyless user → empty results + `switch_pm_text` + `from_inline` param
10. Empty query → hint card returned
11. Real query → article card with callback button, query cached
12. Non-asker tapping Generate → rejected with alert, cache entry preserved
13. Missing/expired cache entry → expired alert, no edit attempted
14. Successful generation: edit_message_text called with AI answer +
    "via @bot" footer, cache entry popped (consumed once)
15. BOT_VERSION == 2.3.0
16. HTML injection in user query (`<script>alert(1)</script>`) is
    escaped before being rendered in the placeholder

### ROADMAP Phase 1 status
- ~~1.1 Free Tier~~ — Not doing (BYOK)
- ✅ 1.2 Onboarding wizard (v2.2.2)
- ✅ 1.3 Inline mode (v2.3.0)
- ✅ 1.4 Action buttons (v2.2.0)
- ✅ 1.5 /share + referrals (v2.2.0)

**Phase 1 = COMPLETE.** Next: Phase 2 (retention) or pause to
collect user feedback first.

---

## [2.2.2] — 2026-05-25 — Onboarding wizard (Phase 1.2 from ROADMAP)

### 🎬 BYOK-first onboarding wizard
- New users (no API key set) who type `/start` in private chat are
  automatically dropped into an interactive 3-step wizard:
  - **Step 1:** language picker (RU / EN / IT) — done in inline buttons
  - **Step 2:** "get a free key" explainer card with three curated
    providers, each with a 🌐 signup-link button and a "✅ Use" pick
    button:
      - ⚡ **Groq** — fastest, Llama 3.3 70B
      - ✨ **Gemini** — Google, 60 req/min free
      - 🌐 **OpenRouter** — model catalog with free options
    Plus shortcuts: "🔑 I already have a key" and "⏭ Skip"
  - **Step 3:** bot puts the user in `awaiting_key_for_<provider>`
    state and shows a friendly send-the-key prompt
- After the user sends their first key, the bot fires a post-onboarding
  tour message and pins the main reply keyboard.
- The whole wizard is also runnable on demand via `/onboard`.

### Why this matters
- The Free Tier in v2.2.0 violated the BYOK principle (creator's money
  on the line). Reverted in v2.2.1.
- This wizard solves the same friction problem **without** creator-funded
  API costs: it makes getting a personal free key trivial by pointing at
  providers that genuinely have free tiers and pre-selecting them.

### Plumbing
- New module `bot/handlers/onboarding.py` (~100 lines, all callbacks
  prefixed `onb_*`).
- `start_command` checks `user["api_keys"]` — if empty and chat is
  private, auto-runs the wizard instead of the standard welcome.
- `awaiting_key_for_<provider>` handler now detects "this is the user's
  first key ever" and triggers the post-onboarding tour.
- `button_callback` dispatches all `onb_*` data to `onboarding_callback`.
- 8 new i18n keys × 3 languages (208 keys total per lang).
- `BOT_VERSION` bumped to 2.2.2.

### Tested (13 in-session verifications)
1. main.py loads with real PTB v21; /onboard registered
2. i18n parity (208 keys × 3 langs)
3. All 8 new onboarding keys present in ru/en/it
4. Provider placeholder interpolates correctly in onb_step3_text
5. 3 free providers configured with HTTPS signup URLs
6. Step-1 keyboard: 3 language buttons with correct callback_data
7. Step-2 keyboard: 3 provider rows × 2 buttons + have_key + skip
8. All callback_data within Telegram's 64-byte limit
9. No callback_data collisions with existing 40+ handlers
10. End-to-end simulated flow: lang → pick → back → skip
11. /start on fresh user auto-launches wizard (user.state="onboarding")
12. /start on existing user (with keys) does NOT trigger wizard
13. BOT_VERSION == 2.2.2

---

## [2.2.1] — 2026-05-25 — Revert Free Tier (BYOK reaffirmed)

### Reverted from v2.2.0
- Removed the creator-funded **Free Tier** entirely. The whole reason
  this bot is BYOK is so the creator doesn't pay for users' AI usage.
  Adding a shared-key fallback contradicted that intent.

What was removed:
- `bot/config.py`: `SHARED_KEYS`, `FREE_TIER_DAILY_LIMIT`,
  `FREE_TIER_FALLBACK_PROVIDER`, `has_shared_key_for()`,
  `best_shared_key()`.
- `bot/ai.py`: `_resolve_key()`, `_free_tier_remaining()`,
  `_free_tier_consume()`, `_free_tier_limit_msg()`. Restored
  `generate_response` and `stream_response` to read only from
  `user["api_keys"][provider]`.
- `bot/storage.py`: removed `free_tier` from new-user shape and from
  legacy backfill (referrals counter remains — that's a viral
  feature, not a cost feature).
- `.env.example`: removed all `FALLBACK_*_KEY` and `FREE_TIER_*` lines.
- `bot/i18n.py`: removed unused limit-reached message keys.

What was kept from v2.2.0:
- 🔘 **Action buttons** under AI replies (🔄 Regenerate, 💾 Save as note)
- 🤝 **Referral system** (`/share`, `/referrals`)

Verified post-revert (8 tests):
- main.py loads with real PTB v21
- No-key error returns cleanly (no free-tier path executed)
- Streaming with no key returns no-key error (no counter touched)
- BOT_VERSION = 2.2.1
- `SHARED_KEYS` is gone (ImportError if anything tried to use it)
- i18n parity holds (200 keys × 3 langs)
- /share and /referrals still wired
- Action buttons still attached to AI responses

---

## [2.2.0] — 2026-05-25 (PARTIALLY REVERTED in 2.2.1)

> Free Tier section below was added in v2.2.0 and reverted in v2.2.1.
> Action Buttons and Referral System sections remain in effect.

### 🆓 Free Tier — главный барьер снят
- Creator can set fallback API keys via env vars (`FALLBACK_GROQ_KEY`,
  `FALLBACK_GEMINI_KEY`, etc.). New users without their own key get
  10 free messages/day automatically.
- Smart provider resolution: if user's selected provider has no shared
  key, auto-falls-back to the best available (defaults to Groq —
  fastest free option).
- Daily counter resets at UTC midnight. Per-user, tracked in
  `user["free_tier"] = {"date": "YYYY-MM-DD", "count": N}`.
- Counter only debits on successful responses (errors don't burn quota).
- Clear localized message when limit hit, pointing to /setkey or /vip.

### 🔘 Action buttons под AI ответом
- After every AI reply in private chat: 🔄 **Regenerate** and 💾 **Save as note**.
- Regenerate re-runs the same prompt + system_prompt, edits the message
  in place. Buttons re-attach on the new response.
- Save-as-note creates a regular note from the AI text (subject to the
  100-note cap from v2.0.3). Toast confirmation via `query.answer`.
- `last_ai_turn` (prompt + response + system_prompt) stored per user
  for these actions to work across sessions.

### 🤝 Referral system + /share
- `/share` generates a personal deep-link
  (`https://t.me/AI_DISCO_BOT?start=ref_USERID`) ready to forward.
- New users who join via the link have `referred_by` recorded; the
  inviter's `referrals` counter increments and they receive a
  notification: "🎉 Bob joined via your link! Total: 3"
- Anti-cheat: can't refer yourself; can't be referred twice.
- `/referrals` shows your invite count.

### Polish
- `BOT_VERSION` bumped to 2.2.0.
- `.env.example` documents all FALLBACK_*_KEY vars.
- 200 i18n keys × 3 langs (added btn_regen/btn_save_note/regen_*/
  saved_as_note/share_text/ref_*).
- 20 functional tests added in-session covering: i18n parity, format
  strings, free tier config & counter (including reset, cap, idempotence),
  key resolution in all 3 cases (own/shared-direct/shared-fallback),
  action button rendering, callback uniqueness, referral parsing edges,
  /share link generation end-to-end.

---

## [2.1.0] — 2026-05-20 🎉 "Wow Effect"

### 🌊 Streaming responses
- AI responses now stream **live** like ChatGPT — text appears word by word
  with a blinking cursor (`▌`). Supports 9 providers: OpenAI, Anthropic,
  Gemini, Groq, Together, OpenRouter, Mistral, xAI, DeepSeek.
- Telegram message is re-edited every ~1.2s to stay within rate limits.
- Auto-falls-back to single-shot for providers without SSE support.
- Typing indicator (`...is typing`) is sent before and during AI work.

### 🎙 Voice input (VIP not required)
- Send a voice message — bot transcribes via **OpenAI Whisper** and answers.
- Works as long as the user has an OpenAI key set.
- The transcription is shown back so you see what was heard.
- Up to 20 MB voice files supported.

### 🎭 AI Personas
- `/persona [name]` switches the AI's character. Built-ins:
  `default`, `philosopher`, `comedian`, `teacher`, `coach`, `sarcastic`,
  `kid`, `pirate`. `/persona off` resets.
- Persona overlays the system prompt without breaking memory or context.

### 🎰 Telegram dice mini-games
- `/slots` 🎰 — slot machine. JACKPOT on 64, triples on 22 (🍒) and 43 (🍋).
- `/basket` 🏀 — score if dice lands 4 or 5.
- `/football` ⚽ — goal on 3, 4, 5.
- `/dart` 🎯 — bullseye only on 6.
- `/bowl` 🎳 — strike on 6.
- Per-game wins/plays tracked in your profile.

### 🔮 /today
- AI-generated personal "fortune of the day" with insight + tiny challenge
  + vibe number. Cached per (day, user), so repeat calls within a day
  return the same.

### 🧠 /quiz [topic]
- AI generates a single multiple-choice question on any topic.
- Answers via inline buttons. Cumulative correct/total score is tracked.
- Strict JSON parsing of the model's output with fence-stripping fallback.

### Polish
- `BOT_VERSION` bumped to 2.1.0.
- 172 i18n keys × 3 languages, no drift.
- Default-chat path uses streaming too — typing in private chat now
  feels like a real conversation.

---

## [2.0.3] — 2026-05-20

### Third-pass review fixes
- HTML-escape user content in `/notes`, `/memorylist`, `/todo`, `/rules`, `/reminders`
- Strict `/todo done|del` index validator (no more negative-index silent mutations)
- Per-user caps: notes 100×2000, tasks 100×1000, memory 50 entries
- `chat_history` per-message cap 4000 → 1500 chars
- Vision/document downloads: 30s aiohttp timeout, fallback size check
- `_int_env()` makes the bot resilient to garbage `CREATOR_ID`
- Memory injection into system prompt capped at 30 entries

## [2.0.2] — 2026-05-20

### Second-pass review fixes
- HTML-escape provider error details (avoid Telegram parser blowup)
- HTML-escape `/feedback` content before forwarding to creator
- Cap `/purge` reply-range at 200 message ids
- Wrap `reply_dice` and `delete` in try/except
- `/help` also clears interactive state
- Periodic spam-cache cleanup every 10 minutes

## [2.0.1] — 2026-05-20

### Ultrareview fixes
- Storage refuses to save if load never succeeded (prevents prod wipe)
- Save lock + auto-refresh-sha on 409 conflicts
- `/setkey` refused in groups (key-exposure protection)
- `/broadcast` HTML-escapes input
- Real AntiSpam: repeating same message 3× in 30s → 10-min mute
- Periodic save every 5 min (so group stats survive restart)
- `/profile` resolves actual default model
- `bot.get_me()` cached
- Interactive state cleared on `/start` and reply-button taps

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
