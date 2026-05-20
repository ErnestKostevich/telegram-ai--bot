translations = {
    "ru": {
        # === Welcome / Main ===
        "welcome": ("🤖 <b>Добро пожаловать в AI DISCO BOT!</b>\n\n"
                     "Я — многофункциональный ИИ-ассистент с памятью диалога.\n"
                     "Система <b>BYOK</b> даёт свободу выбора из 10+ провайдеров.\n\n"
                     "<b>С чего начать:</b>\n"
                     "1️⃣ ⚙️ Настройки → Провайдер\n"
                     "2️⃣ 🔑 Установить API-ключ\n"
                     "3️⃣ Просто пишите — бот помнит контекст\n\n"
                     "💎 <b>VIP:</b> анализ фото, документов, генерация картинок, напоминания.\n\n"
                     "📜 /changelog — что нового\n👇 <i>Меню ниже:</i>"),
        "help": "📚 <b>Справка по командам:</b>\n\nВыберите нужный раздел:",
        "lang_changed": "🇷🇺 Язык изменён на Русский.",
        # Reply keyboard buttons
        "btn_ai": "💬 AI Чат", "btn_mem": "🧠 Память", "btn_notes": "📝 Заметки", "btn_vip": "💎 VIP",
        "btn_settings": "⚙️ Настройки", "btn_games": "🎮 Игры", "btn_tools": "🛠 Утилиты", "btn_lang": "🌐 Язык",
        # Inline buttons
        "ik_provider": "⚡ Провайдер", "ik_model": "🧠 Модель", "ik_keys": "🔑 API Ключ",
        "ik_clear": "🧹 Очистить контекст",
        "ik_reminders": "⏰ Напоминания", "ik_generate": "🖼️ Генерация", "ik_guardian": "🛡️ Guardian",
        "ik_back": "🔙 Назад", "ik_profile": "👤 Профиль", "ik_disco": "🪩 Disco Mode",
        "vip_menu": "💎 <b>VIP Меню</b>", "settings_menu": "⚙️ <b>Настройки AI</b>",
        "games_menu": "🎮 <b>Игры и развлечения</b>\n\nВыберите игру:",
        "tools_menu": "🛠 <b>Утилиты</b>\n\nВыберите инструмент:",
        # Profile
        "profile_title": ("👤 <b>Профиль (Ур. {level})</b>\n\n"
                          "✨ XP: {xp}/{next_level_xp}\n"
                          "📊 {progress_bar} {progress}%\n\n"
                          "💎 VIP: {vip_status}\n"
                          "💬 Сообщений: {msgs}\n"
                          "📝 Заметок: {notes} · 📋 Задач: {tasks}\n"
                          "🧠 Memory: {memory} · 💭 История: {history}\n"
                          "⚡ Провайдер: <b>{provider}</b>\n"
                          "🧠 Модель: <code>{model}</code>"),
        "status_yes": "👑 Да", "status_no": "❌ Нет",
        # Info / status / version
        "info": ("ℹ️ <b>AI DISCO BOT v{version}</b>\n\n"
                 "⚙️ Архитектура: BYOK (10+ провайдеров)\n"
                 "🧠 Память диалога: ✅\n"
                 "👁 Анализ фото и документов: ✅ (VIP)\n"
                 "🌐 Языки: RU / EN / IT\n"
                 "🗄 Хранилище: GitHub API\n"
                 "📅 Сборка: {date}\n\n"
                 "👤 Создатель: @Ernest_Kostevich"),
        "status": ("📊 <b>Статус системы</b>\n\n"
                   "🚀 Версия: <b>v{version}</b>\n"
                   "👥 Пользователей: <b>{users}</b>\n"
                   "💬 Групп: <b>{groups}</b>\n"
                   "🗄 GitHub: Активно\n"
                   "⚡ BYOK: Активна"),
        "version_text": "🚀 <b>AI DISCO BOT v{version}</b>\n📅 {date}\n\n/changelog — что нового",
        "export_caption": "📦 Ваши данные. Сохраните этот файл в надёжном месте.",
        # AI
        "ai_no_query": "❓ Задайте вопрос: /ai [текст]\n\n💡 В личке просто пишите — бот помнит контекст.",
        "ai_thinking": "⏳ Генерирую ответ...",
        "ai_chat_hint": "💬 Просто напишите вопрос — бот помнит контекст диалога.\n\n🧹 /clear — сбросить контекст",
        "ai_cleared": "🧹 Контекст диалога очищен. ({count} пар сообщений удалено)",
        "ai_no_key": "❌ Ключ для {provider} не найден.\nУстановите: /setkey {provider} [ключ]",
        "provider_set": "✅ Провайдер: <b>{provider}</b>\nУстановите ключ: <code>/setkey {provider} [ключ]</code>",
        "provider_unknown": "❌ Неизвестный провайдер.\nДоступные: {list}",
        "provider_usage": "Использование: /setprovider [провайдер]\nДоступные: {list}",
        "key_saved": "✅ Ключ для <b>{provider}</b> сохранён!",
        "key_usage": "Использование: /setkey [провайдер] [ключ]",
        "key_group_refuse": "🚫 <b>Никогда не вводите API-ключи в группах!</b>\nОтправьте /setkey мне в <b>личные сообщения</b>.",
        "key_group_dm_hint": "👋 Пишите ключи мне сюда. Формат: <code>/setkey gemini ВАШ_КЛЮЧ</code>",
        "model_set": "🧠 Модель: <b>{model}</b>",
        "model_usage": "Использование: /setmodel [модель]\nТекущая: {current}",
        # Memory
        "mem_saved": "✅ Сохранено: {key} = {value}", "mem_usage": "Использование: /memorysave [ключ] [значение]",
        "mem_value": "🧠 {key}: {value}", "mem_not_found": "❌ Ключ '{key}' не найден.",
        "mem_empty": "📭 Память пуста.", "mem_title": "🧠 <b>Память:</b>\n\n",
        "mem_deleted": "🗑 '{key}' удалён.", "mem_del_usage": "Использование: /memorydel [ключ]",
        # Notes
        "note_saved": "✅ Заметка #{num} сохранена!", "note_usage": "Использование: /note [текст]",
        "notes_empty": "📭 Заметок нет.", "notes_title": "📝 <b>Заметки ({count}):</b>\n\n",
        "note_deleted": "✅ Заметка #{num} удалена.", "note_del_usage": "Использование: /delnote [номер]",
        "note_not_found": "❌ Заметка не найдена.",
        # Todo
        "todo_empty": "📭 Список задач пуст.\nДобавить: /todo [текст]", "todo_title": "📋 <b>Задачи:</b>\n\n",
        "todo_done": "✅ Задача #{num} выполнена!", "todo_deleted": "🗑 Задача удалена.",
        "todo_added": "✅ Задача добавлена!", "todo_bad_num": "❌ Укажите номер задачи.",
        # Games
        "coinflip_h": "Орёл 🦅", "coinflip_t": "Решка 🪙", "coinflip_text": "Монетка: <b>{result}</b>",
        "random_text": "🎲 Число от {min} до {max}: <b>{result}</b>",
        "random_usage": "Использование: /random [от] [до]",
        # Utils
        "time_usage": "Использование: /time [город]\nПример: /time Rome",
        "time_not_found": "❌ Часовой пояс не найден.",
        "weather_usage": "Использование: /weather [город]", "weather_error": "❌ Не удалось получить погоду.",
        "calc_usage": "Использование: /calc [выражение]\nПример: /calc 2+2*5",
        "calc_error": "❌ Ошибка вычисления.",
        "calc_result": "🧮 {expr} = <b>{result}</b>",
        "pwd_result": "🔑 <b>Пароль:</b>\n<code>{pwd}</code>", "pwd_error": "❌ Длина от 8 до 64.",
        # VIP
        "vip_status": ("💎 <b>VIP Статус:</b> {status}\n\n"
                       "VIP даёт доступ к:\n"
                       "🖼 Генерации изображений\n"
                       "👁 Анализу фото\n"
                       "📎 Анализу документов\n"
                       "⏰ Напоминаниям\n\n"
                       "Получить VIP: напишите создателю /feedback"),
        "remind_set": "⏰ Напоминание через {mins} мин!",
        "remind_usage": "Использование: /remind [минуты] [текст]\nПример: /remind 30 позвонить маме",
        "remind_bad_time": "❌ Введите минуты от 1 до 43200 (30 дней).",
        "reminders_empty": "📭 Нет активных напоминаний.",
        "reminders_title": "⏰ <b>Напоминания ({count}):</b>\n\n",
        "feedback_usage": "💬 Использование: /feedback [текст]\nВаш отзыв уйдёт создателю.",
        "feedback_thanks": "💌 Спасибо! Ваш отзыв отправлен создателю.",
        # Disco
        "disco_on": "🪩 <b>Disco Mode ВКЛЮЧЁН!</b> Бот будет творческим и весёлым!",
        "disco_off": "🪩 Disco Mode выключен.",
        "disco_status": "🪩 Disco Mode: <b>{status}</b>\nИспользование: /disco [on|off]",
        "disco_enabled": "ВКЛЮЧЁН", "disco_disabled": "ВЫКЛЮЧЕН",
        # Groups
        "group_only": "❌ Только для групп.", "admin_only": "❌ Нужны права администратора.",
        "reply_needed": "❌ Ответьте на сообщение пользователя.",
        "user_warned": "⚠️ <b>{user}</b> получил предупреждение!",
        "warn_count": "⚠️ <b>{user}</b>: предупреждение <b>{count}/3</b>",
        "warn_banned": "🚫 <b>{user}</b> забанен (3/3 предупреждений).",
        "warn_show": "⚠️ <b>{user}</b>: <b>{count}</b> предупр.",
        "warn_none": "✅ Активных предупреждений нет.",
        "warn_none_user": "✅ У <b>{user}</b> нет предупреждений.",
        "warn_removed": "✅ Снято варн с <b>{user}</b>. Осталось: {count}",
        "warn_list_title": "⚠️ <b>Активные предупреждения:</b>\n\n",
        "user_muted_for": "🔇 <b>{user}</b> в муте на {mins} мин.",
        "user_unmuted": "🔊 <b>{user}</b> размучен.",
        "user_banned": "🚫 <b>{user}</b> забанен.",
        "user_kicked": "👢 <b>{user}</b> кикнут.",
        "purge_done": "🗑 Удалено: {count} сообщений.",
        "purge_usage": "Использование: /purge [количество] (или ответом)",
        "antilink_on": "🔗 AntiLink: <b>ВКЛ</b>. Ссылки от не-админов удаляются.",
        "antilink_off": "🔗 AntiLink: <b>ВЫКЛ</b>.",
        "antispam_on": "🚨 AntiSpam: <b>ВКЛ</b>. Повтор одного сообщения 3 раза за 30с → авто-мут на 10 мин.",
        "antispam_off": "🚨 AntiSpam: <b>ВЫКЛ</b>.",
        "antispam_muted": "🚨 <b>{user}</b> замучен на {mins} мин за спам.",
        "welcome_status": "👋 Welcome: {status}\n\nСообщение:\n{msg}",
        "welcome_on": "✅ Welcome включено.",
        "welcome_off": "🔕 Welcome выключено.",
        "welcome_saved": "✅ Welcome-сообщение сохранено.",
        "goodbye_status": "👋 Goodbye: {status}\n\nСообщение:\n{msg}",
        "goodbye_on": "✅ Goodbye включено.",
        "goodbye_off": "🔕 Goodbye выключено.",
        "goodbye_saved": "✅ Goodbye-сообщение сохранено.",
        "guardian_on": "🛡️ AI Guardian <b>активирован!</b>",
        "guardian_off": "🛡️ AI Guardian <b>деактивирован.</b>",
        "rules_empty": "Правила не установлены.", "rules_title": "Правила группы",
        "rules_saved": "✅ Правила сохранены!",
        "setrules_usage": "Использование: /setrules [текст правил]",
        "groupstats_text": ("📊 <b>{title}</b>\n\n"
                            "👥 Участников: <b>{members}</b>\n"
                            "💬 Сообщений (бот видел): <b>{msgs}</b>\n"
                            "💭 Буфер /summary: <b>{buffer}</b>\n"
                            "🔧 Активно: {flags}"),
        # Generate / Vision
        "gen_drawing": "🎨 Рисую...", "gen_usage": "Использование: /generate [описание]",
        "gen_vip_only": "💎 Эта функция доступна только VIP.\nПолучить: /feedback с просьбой.",
        "gen_describe": "🖼️ <b>Генерация</b>\n\nОпишите что нарисовать:",
        "gen_needs_openai": "❌ Для генерации нужен ключ OpenAI.\nУстановите: <code>/setkey openai sk-...</code>",
        "vision_analyzing": "👁 Анализирую изображение...",
        "vision_default_prompt": "Опиши это изображение подробно.",
        "vision_unsupported": "❌ Провайдер <b>{provider}</b> не поддерживает анализ изображений.\nИспользуйте: openai, anthropic, gemini или openrouter.",
        "doc_reading": "📎 Читаю документ...",
        "doc_too_big": "❌ Файл слишком большой (макс 200 KB).",
        "doc_unsupported": "❌ Поддерживаются только текстовые файлы (.txt, .md, .json, .xml).",
        "doc_default_prompt": "Кратко расскажи о содержимом этого файла.",
        # Group AI
        "ask_usage": "Использование: /ask [вопрос]",
        "summary_generating": "📝 Генерирую сводку...",
        "summary_empty": "📭 Бот пока не видел сообщений в группе. Напишите что-нибудь и попробуйте снова.",
        "translate_usage": "Использование: /translate [язык] [текст]\nИли: /translate [язык] в reply на сообщение",
        "translate_generating": "🌍 Перевожу...",
    },
    "en": {
        "welcome": ("🤖 <b>Welcome to AI DISCO BOT!</b>\n\n"
                     "I'm a multi-functional AI assistant with conversation memory.\n"
                     "The <b>BYOK</b> system lets you pick from 10+ providers.\n\n"
                     "<b>Quick start:</b>\n"
                     "1️⃣ ⚙️ Settings → Provider\n"
                     "2️⃣ 🔑 Set your API key\n"
                     "3️⃣ Just type — I remember context\n\n"
                     "💎 <b>VIP:</b> photo & document analysis, image generation, reminders.\n\n"
                     "📜 /changelog — what's new\n👇 <i>Menu below:</i>"),
        "help": "📚 <b>Command Reference:</b>\n\nPick a section:",
        "lang_changed": "🇬🇧 Language changed to English.",
        "btn_ai": "💬 AI Chat", "btn_mem": "🧠 Memory", "btn_notes": "📝 Notes", "btn_vip": "💎 VIP",
        "btn_settings": "⚙️ Settings", "btn_games": "🎮 Games", "btn_tools": "🛠 Tools", "btn_lang": "🌐 Language",
        "ik_provider": "⚡ Provider", "ik_model": "🧠 Model", "ik_keys": "🔑 API Key",
        "ik_clear": "🧹 Clear context",
        "ik_reminders": "⏰ Reminders", "ik_generate": "🖼️ Generate", "ik_guardian": "🛡️ Guardian",
        "ik_back": "🔙 Back", "ik_profile": "👤 Profile", "ik_disco": "🪩 Disco Mode",
        "vip_menu": "💎 <b>VIP Menu</b>", "settings_menu": "⚙️ <b>AI Settings</b>",
        "games_menu": "🎮 <b>Games</b>\n\nPick a game:", "tools_menu": "🛠 <b>Tools</b>\n\nPick a tool:",
        "profile_title": ("👤 <b>Profile (Lv. {level})</b>\n\n"
                          "✨ XP: {xp}/{next_level_xp}\n"
                          "📊 {progress_bar} {progress}%\n\n"
                          "💎 VIP: {vip_status}\n"
                          "💬 Messages: {msgs}\n"
                          "📝 Notes: {notes} · 📋 Tasks: {tasks}\n"
                          "🧠 Memory: {memory} · 💭 History: {history}\n"
                          "⚡ Provider: <b>{provider}</b>\n"
                          "🧠 Model: <code>{model}</code>"),
        "status_yes": "👑 Yes", "status_no": "❌ No",
        "info": ("ℹ️ <b>AI DISCO BOT v{version}</b>\n\n"
                 "⚙️ Architecture: BYOK (10+ providers)\n"
                 "🧠 Conversation memory: ✅\n"
                 "👁 Photo & document analysis: ✅ (VIP)\n"
                 "🌐 Languages: RU / EN / IT\n"
                 "🗄 Storage: GitHub API\n"
                 "📅 Build: {date}\n\n"
                 "👤 Creator: @Ernest_Kostevich"),
        "status": ("📊 <b>System Status</b>\n\n"
                   "🚀 Version: <b>v{version}</b>\n"
                   "👥 Users: <b>{users}</b>\n"
                   "💬 Groups: <b>{groups}</b>\n"
                   "🗄 GitHub: Active\n"
                   "⚡ BYOK: Active"),
        "version_text": "🚀 <b>AI DISCO BOT v{version}</b>\n📅 {date}\n\n/changelog — what's new",
        "export_caption": "📦 Your data. Keep this file safe.",
        "ai_no_query": "❓ Ask a question: /ai [text]\n\n💡 In DM, just type — I remember context.",
        "ai_thinking": "⏳ Generating response...",
        "ai_chat_hint": "💬 Just type your question — I remember context.\n\n🧹 /clear — reset context",
        "ai_cleared": "🧹 Conversation cleared. ({count} message pairs removed)",
        "ai_no_key": "❌ Key for {provider} not found.\nSet it: /setkey {provider} [key]",
        "provider_set": "✅ Provider: <b>{provider}</b>\nSet key: <code>/setkey {provider} [key]</code>",
        "provider_unknown": "❌ Unknown provider.\nAvailable: {list}",
        "provider_usage": "Usage: /setprovider [provider]\nAvailable: {list}",
        "key_saved": "✅ Key for <b>{provider}</b> saved!", "key_usage": "Usage: /setkey [provider] [key]",
        "key_group_refuse": "🚫 <b>Never paste API keys in groups!</b>\nSend /setkey to me in a <b>private chat</b>.",
        "key_group_dm_hint": "👋 Send keys here. Format: <code>/setkey gemini YOUR_KEY</code>",
        "model_set": "🧠 Model: <b>{model}</b>", "model_usage": "Usage: /setmodel [model]\nCurrent: {current}",
        "mem_saved": "✅ Saved: {key} = {value}", "mem_usage": "Usage: /memorysave [key] [value]",
        "mem_value": "🧠 {key}: {value}", "mem_not_found": "❌ Key '{key}' not found.",
        "mem_empty": "📭 Memory is empty.", "mem_title": "🧠 <b>Memory:</b>\n\n",
        "mem_deleted": "🗑 '{key}' deleted.", "mem_del_usage": "Usage: /memorydel [key]",
        "note_saved": "✅ Note #{num} saved!", "note_usage": "Usage: /note [text]",
        "notes_empty": "📭 No notes.", "notes_title": "📝 <b>Notes ({count}):</b>\n\n",
        "note_deleted": "✅ Note #{num} deleted.", "note_del_usage": "Usage: /delnote [number]",
        "note_not_found": "❌ Note not found.",
        "todo_empty": "📭 No tasks.\nAdd: /todo [text]", "todo_title": "📋 <b>Tasks:</b>\n\n",
        "todo_done": "✅ Task #{num} done!", "todo_deleted": "🗑 Task deleted.",
        "todo_added": "✅ Task added!", "todo_bad_num": "❌ Enter a valid number.",
        "coinflip_h": "Heads 🦅", "coinflip_t": "Tails 🪙", "coinflip_text": "Coin: <b>{result}</b>",
        "random_text": "🎲 Number {min}-{max}: <b>{result}</b>", "random_usage": "Usage: /random [min] [max]",
        "time_usage": "Usage: /time [city]\nExample: /time Rome",
        "time_not_found": "❌ Timezone not found.",
        "weather_usage": "Usage: /weather [city]", "weather_error": "❌ Weather lookup failed.",
        "calc_usage": "Usage: /calc [expression]\nExample: /calc 2+2*5",
        "calc_error": "❌ Calculation error.",
        "calc_result": "🧮 {expr} = <b>{result}</b>",
        "pwd_result": "🔑 <b>Password:</b>\n<code>{pwd}</code>", "pwd_error": "❌ Length 8-64.",
        "vip_status": ("💎 <b>VIP Status:</b> {status}\n\n"
                       "VIP unlocks:\n"
                       "🖼 Image generation\n"
                       "👁 Photo analysis\n"
                       "📎 Document analysis\n"
                       "⏰ Reminders\n\n"
                       "Get VIP: message the creator via /feedback"),
        "remind_set": "⏰ Reminder in {mins} min!",
        "remind_usage": "Usage: /remind [minutes] [text]\nExample: /remind 30 call mom",
        "remind_bad_time": "❌ Minutes must be 1-43200 (30 days).",
        "reminders_empty": "📭 No active reminders.",
        "reminders_title": "⏰ <b>Reminders ({count}):</b>\n\n",
        "feedback_usage": "💬 Usage: /feedback [text]\nYour message goes to the creator.",
        "feedback_thanks": "💌 Thanks! Your feedback was sent to the creator.",
        "disco_on": "🪩 <b>Disco Mode ON!</b> Bot will be creative and fun!",
        "disco_off": "🪩 Disco Mode off.",
        "disco_status": "🪩 Disco Mode: <b>{status}</b>\nUsage: /disco [on|off]",
        "disco_enabled": "ON", "disco_disabled": "OFF",
        "group_only": "❌ Groups only.", "admin_only": "❌ Admin rights required.",
        "reply_needed": "❌ Reply to a user's message.",
        "user_warned": "⚠️ <b>{user}</b> warned!",
        "warn_count": "⚠️ <b>{user}</b>: warn <b>{count}/3</b>",
        "warn_banned": "🚫 <b>{user}</b> banned (3/3 warns).",
        "warn_show": "⚠️ <b>{user}</b>: <b>{count}</b> warns.",
        "warn_none": "✅ No active warnings.",
        "warn_none_user": "✅ <b>{user}</b> has no warnings.",
        "warn_removed": "✅ Warn removed from <b>{user}</b>. Left: {count}",
        "warn_list_title": "⚠️ <b>Active warnings:</b>\n\n",
        "user_muted_for": "🔇 <b>{user}</b> muted for {mins} min.",
        "user_unmuted": "🔊 <b>{user}</b> unmuted.",
        "user_banned": "🚫 <b>{user}</b> banned.",
        "user_kicked": "👢 <b>{user}</b> kicked.",
        "purge_done": "🗑 Deleted: {count} messages.",
        "purge_usage": "Usage: /purge [count] (or as a reply)",
        "antilink_on": "🔗 AntiLink: <b>ON</b>. Non-admin links are deleted.",
        "antilink_off": "🔗 AntiLink: <b>OFF</b>.",
        "antispam_on": "🚨 AntiSpam: <b>ON</b>. Same message 3× in 30s → auto-mute 10 min.",
        "antispam_off": "🚨 AntiSpam: <b>OFF</b>.",
        "antispam_muted": "🚨 <b>{user}</b> muted for {mins} min for spam.",
        "welcome_status": "👋 Welcome: {status}\n\nMessage:\n{msg}",
        "welcome_on": "✅ Welcome enabled.",
        "welcome_off": "🔕 Welcome disabled.",
        "welcome_saved": "✅ Welcome message saved.",
        "goodbye_status": "👋 Goodbye: {status}\n\nMessage:\n{msg}",
        "goodbye_on": "✅ Goodbye enabled.",
        "goodbye_off": "🔕 Goodbye disabled.",
        "goodbye_saved": "✅ Goodbye message saved.",
        "guardian_on": "🛡️ AI Guardian <b>activated!</b>",
        "guardian_off": "🛡️ AI Guardian <b>deactivated.</b>",
        "rules_empty": "No rules set.", "rules_title": "Group Rules",
        "rules_saved": "✅ Rules saved!",
        "setrules_usage": "Usage: /setrules [text]",
        "groupstats_text": ("📊 <b>{title}</b>\n\n"
                            "👥 Members: <b>{members}</b>\n"
                            "💬 Messages seen: <b>{msgs}</b>\n"
                            "💭 /summary buffer: <b>{buffer}</b>\n"
                            "🔧 Active: {flags}"),
        "gen_drawing": "🎨 Drawing...", "gen_usage": "Usage: /generate [description]",
        "gen_vip_only": "💎 This feature is VIP-only.\nGet it via /feedback.",
        "gen_describe": "🖼️ <b>Generate</b>\n\nDescribe what to draw:",
        "gen_needs_openai": "❌ Image generation needs OpenAI key.\nSet: <code>/setkey openai sk-...</code>",
        "vision_analyzing": "👁 Analyzing image...",
        "vision_default_prompt": "Describe this image in detail.",
        "vision_unsupported": "❌ Provider <b>{provider}</b> doesn't support image analysis.\nUse: openai, anthropic, gemini, or openrouter.",
        "doc_reading": "📎 Reading document...",
        "doc_too_big": "❌ File too large (max 200 KB).",
        "doc_unsupported": "❌ Only text files supported (.txt, .md, .json, .xml).",
        "doc_default_prompt": "Briefly summarize the contents of this file.",
        "ask_usage": "Usage: /ask [question]",
        "summary_generating": "📝 Generating summary...",
        "summary_empty": "📭 No messages tracked yet. Chat for a bit and try again.",
        "translate_usage": "Usage: /translate [lang] [text]\nOr: /translate [lang] as reply to a message",
        "translate_generating": "🌍 Translating...",
    },
    "it": {
        "welcome": ("🤖 <b>Benvenuto in AI DISCO BOT!</b>\n\n"
                     "Sono un assistente AI con memoria della conversazione.\n"
                     "Il sistema <b>BYOK</b> ti permette di scegliere tra 10+ provider.\n\n"
                     "<b>Come iniziare:</b>\n"
                     "1️⃣ ⚙️ Impostazioni → Provider\n"
                     "2️⃣ 🔑 Imposta la chiave\n"
                     "3️⃣ Scrivi — ricordo il contesto\n\n"
                     "💎 <b>VIP:</b> analisi foto, documenti, generazione immagini, promemoria.\n\n"
                     "📜 /changelog — novità\n👇 <i>Menu sotto:</i>"),
        "help": "📚 <b>Guida comandi:</b>\n\nSeleziona una sezione:",
        "lang_changed": "🇮🇹 Lingua cambiata in Italiano.",
        "btn_ai": "💬 Chat AI", "btn_mem": "🧠 Memoria", "btn_notes": "📝 Note", "btn_vip": "💎 VIP",
        "btn_settings": "⚙️ Impostazioni", "btn_games": "🎮 Giochi", "btn_tools": "🛠 Strumenti", "btn_lang": "🌐 Lingua",
        "ik_provider": "⚡ Provider", "ik_model": "🧠 Modello", "ik_keys": "🔑 Chiave API",
        "ik_clear": "🧹 Pulisci contesto",
        "ik_reminders": "⏰ Promemoria", "ik_generate": "🖼️ Genera", "ik_guardian": "🛡️ Guardian",
        "ik_back": "🔙 Indietro", "ik_profile": "👤 Profilo", "ik_disco": "🪩 Disco Mode",
        "vip_menu": "💎 <b>Menu VIP</b>", "settings_menu": "⚙️ <b>Impostazioni AI</b>",
        "games_menu": "🎮 <b>Giochi</b>\n\nScegli un gioco:",
        "tools_menu": "🛠 <b>Strumenti</b>\n\nScegli uno strumento:",
        "profile_title": ("👤 <b>Profilo (Lv. {level})</b>\n\n"
                          "✨ XP: {xp}/{next_level_xp}\n"
                          "📊 {progress_bar} {progress}%\n\n"
                          "💎 VIP: {vip_status}\n"
                          "💬 Messaggi: {msgs}\n"
                          "📝 Note: {notes} · 📋 Compiti: {tasks}\n"
                          "🧠 Memoria: {memory} · 💭 Storia: {history}\n"
                          "⚡ Provider: <b>{provider}</b>\n"
                          "🧠 Modello: <code>{model}</code>"),
        "status_yes": "👑 Sì", "status_no": "❌ No",
        "info": ("ℹ️ <b>AI DISCO BOT v{version}</b>\n\n"
                 "⚙️ Architettura: BYOK (10+ provider)\n"
                 "🧠 Memoria di conversazione: ✅\n"
                 "👁 Analisi foto e documenti: ✅ (VIP)\n"
                 "🌐 Lingue: RU / EN / IT\n"
                 "🗄 Storage: GitHub API\n"
                 "📅 Build: {date}\n\n"
                 "👤 Creatore: @Ernest_Kostevich"),
        "status": ("📊 <b>Stato del sistema</b>\n\n"
                   "🚀 Versione: <b>v{version}</b>\n"
                   "👥 Utenti: <b>{users}</b>\n"
                   "💬 Gruppi: <b>{groups}</b>\n"
                   "🗄 GitHub: Attivo\n"
                   "⚡ BYOK: Attivo"),
        "version_text": "🚀 <b>AI DISCO BOT v{version}</b>\n📅 {date}\n\n/changelog — novità",
        "export_caption": "📦 I tuoi dati. Conserva questo file.",
        "ai_no_query": "❓ Fai una domanda: /ai [testo]\n\n💡 In privato scrivi — ricordo il contesto.",
        "ai_thinking": "⏳ Genero risposta...",
        "ai_chat_hint": "💬 Scrivi la tua domanda — ricordo il contesto.\n\n🧹 /clear — reset contesto",
        "ai_cleared": "🧹 Contesto pulito. ({count} coppie di messaggi rimosse)",
        "ai_no_key": "❌ Chiave per {provider} non trovata.\nImposta: /setkey {provider} [chiave]",
        "provider_set": "✅ Provider: <b>{provider}</b>\nImposta chiave: <code>/setkey {provider} [chiave]</code>",
        "provider_unknown": "❌ Provider sconosciuto.\nDisponibili: {list}",
        "provider_usage": "Uso: /setprovider [provider]\nDisponibili: {list}",
        "key_saved": "✅ Chiave per <b>{provider}</b> salvata!", "key_usage": "Uso: /setkey [provider] [chiave]",
        "key_group_refuse": "🚫 <b>Mai inserire chiavi API nei gruppi!</b>\nInvia /setkey in <b>chat privata</b>.",
        "key_group_dm_hint": "👋 Invia le chiavi qui. Formato: <code>/setkey gemini TUA_CHIAVE</code>",
        "model_set": "🧠 Modello: <b>{model}</b>", "model_usage": "Uso: /setmodel [modello]\nAttuale: {current}",
        "mem_saved": "✅ Salvato: {key} = {value}", "mem_usage": "Uso: /memorysave [chiave] [valore]",
        "mem_value": "🧠 {key}: {value}", "mem_not_found": "❌ Chiave '{key}' non trovata.",
        "mem_empty": "📭 Memoria vuota.", "mem_title": "🧠 <b>Memoria:</b>\n\n",
        "mem_deleted": "🗑 '{key}' eliminato.", "mem_del_usage": "Uso: /memorydel [chiave]",
        "note_saved": "✅ Nota #{num} salvata!", "note_usage": "Uso: /note [testo]",
        "notes_empty": "📭 Nessuna nota.", "notes_title": "📝 <b>Note ({count}):</b>\n\n",
        "note_deleted": "✅ Nota #{num} eliminata.", "note_del_usage": "Uso: /delnote [numero]",
        "note_not_found": "❌ Nota non trovata.",
        "todo_empty": "📭 Nessun compito.\nAggiungi: /todo [testo]", "todo_title": "📋 <b>Compiti:</b>\n\n",
        "todo_done": "✅ Compito #{num} completato!", "todo_deleted": "🗑 Compito eliminato.",
        "todo_added": "✅ Compito aggiunto!", "todo_bad_num": "❌ Inserisci un numero valido.",
        "coinflip_h": "Testa 🦅", "coinflip_t": "Croce 🪙", "coinflip_text": "Moneta: <b>{result}</b>",
        "random_text": "🎲 Numero {min}-{max}: <b>{result}</b>", "random_usage": "Uso: /random [min] [max]",
        "time_usage": "Uso: /time [città]\nEsempio: /time Rome",
        "time_not_found": "❌ Fuso orario non trovato.",
        "weather_usage": "Uso: /weather [città]", "weather_error": "❌ Errore meteo.",
        "calc_usage": "Uso: /calc [espressione]\nEsempio: /calc 2+2*5",
        "calc_error": "❌ Errore di calcolo.",
        "calc_result": "🧮 {expr} = <b>{result}</b>",
        "pwd_result": "🔑 <b>Password:</b>\n<code>{pwd}</code>", "pwd_error": "❌ Lunghezza 8-64.",
        "vip_status": ("💎 <b>Stato VIP:</b> {status}\n\n"
                       "VIP sblocca:\n"
                       "🖼 Generazione immagini\n"
                       "👁 Analisi foto\n"
                       "📎 Analisi documenti\n"
                       "⏰ Promemoria\n\n"
                       "Per ottenere VIP: scrivi al creatore via /feedback"),
        "remind_set": "⏰ Promemoria tra {mins} min!",
        "remind_usage": "Uso: /remind [minuti] [testo]\nEsempio: /remind 30 chiama mamma",
        "remind_bad_time": "❌ Minuti 1-43200 (30 giorni).",
        "reminders_empty": "📭 Nessun promemoria attivo.",
        "reminders_title": "⏰ <b>Promemoria ({count}):</b>\n\n",
        "feedback_usage": "💬 Uso: /feedback [testo]\nIl tuo messaggio va al creatore.",
        "feedback_thanks": "💌 Grazie! Il tuo feedback è stato inviato.",
        "disco_on": "🪩 <b>Disco Mode ON!</b> Il bot sarà creativo!",
        "disco_off": "🪩 Disco Mode off.",
        "disco_status": "🪩 Disco Mode: <b>{status}</b>\nUso: /disco [on|off]",
        "disco_enabled": "ON", "disco_disabled": "OFF",
        "group_only": "❌ Solo per gruppi.", "admin_only": "❌ Servono diritti di amministratore.",
        "reply_needed": "❌ Rispondi al messaggio di un utente.",
        "user_warned": "⚠️ <b>{user}</b> avvertito!",
        "warn_count": "⚠️ <b>{user}</b>: warn <b>{count}/3</b>",
        "warn_banned": "🚫 <b>{user}</b> bannato (3/3 warn).",
        "warn_show": "⚠️ <b>{user}</b>: <b>{count}</b> warn.",
        "warn_none": "✅ Nessun warn attivo.",
        "warn_none_user": "✅ <b>{user}</b> non ha warn.",
        "warn_removed": "✅ Warn rimosso da <b>{user}</b>. Restano: {count}",
        "warn_list_title": "⚠️ <b>Warn attivi:</b>\n\n",
        "user_muted_for": "🔇 <b>{user}</b> silenziato per {mins} min.",
        "user_unmuted": "🔊 <b>{user}</b> non più silenziato.",
        "user_banned": "🚫 <b>{user}</b> bannato.",
        "user_kicked": "👢 <b>{user}</b> espulso.",
        "purge_done": "🗑 Eliminati: {count} messaggi.",
        "purge_usage": "Uso: /purge [numero] (o in risposta)",
        "antilink_on": "🔗 AntiLink: <b>ON</b>. I link dei non-admin vengono eliminati.",
        "antilink_off": "🔗 AntiLink: <b>OFF</b>.",
        "antispam_on": "🚨 AntiSpam: <b>ON</b>. Stesso msg 3× in 30s → auto-mute 10 min.",
        "antispam_off": "🚨 AntiSpam: <b>OFF</b>.",
        "antispam_muted": "🚨 <b>{user}</b> silenziato per {mins} min per spam.",
        "welcome_status": "👋 Welcome: {status}\n\nMessaggio:\n{msg}",
        "welcome_on": "✅ Welcome attivato.",
        "welcome_off": "🔕 Welcome disattivato.",
        "welcome_saved": "✅ Messaggio Welcome salvato.",
        "goodbye_status": "👋 Goodbye: {status}\n\nMessaggio:\n{msg}",
        "goodbye_on": "✅ Goodbye attivato.",
        "goodbye_off": "🔕 Goodbye disattivato.",
        "goodbye_saved": "✅ Messaggio Goodbye salvato.",
        "guardian_on": "🛡️ AI Guardian <b>attivato!</b>",
        "guardian_off": "🛡️ AI Guardian <b>disattivato.</b>",
        "rules_empty": "Nessuna regola impostata.", "rules_title": "Regole del gruppo",
        "rules_saved": "✅ Regole salvate!",
        "setrules_usage": "Uso: /setrules [testo]",
        "groupstats_text": ("📊 <b>{title}</b>\n\n"
                            "👥 Membri: <b>{members}</b>\n"
                            "💬 Messaggi visti: <b>{msgs}</b>\n"
                            "💭 Buffer /summary: <b>{buffer}</b>\n"
                            "🔧 Attivo: {flags}"),
        "gen_drawing": "🎨 Disegno...", "gen_usage": "Uso: /generate [descrizione]",
        "gen_vip_only": "💎 Solo per VIP.\nRichiedi via /feedback.",
        "gen_describe": "🖼️ <b>Genera</b>\n\nDescrivi cosa disegnare:",
        "gen_needs_openai": "❌ La generazione richiede chiave OpenAI.\nImposta: <code>/setkey openai sk-...</code>",
        "vision_analyzing": "👁 Analizzo l'immagine...",
        "vision_default_prompt": "Descrivi questa immagine in dettaglio.",
        "vision_unsupported": "❌ Il provider <b>{provider}</b> non supporta l'analisi immagini.\nUsa: openai, anthropic, gemini o openrouter.",
        "doc_reading": "📎 Leggo il documento...",
        "doc_too_big": "❌ File troppo grande (max 200 KB).",
        "doc_unsupported": "❌ Solo file di testo (.txt, .md, .json, .xml).",
        "doc_default_prompt": "Riassumi brevemente il contenuto di questo file.",
        "ask_usage": "Uso: /ask [domanda]",
        "summary_generating": "📝 Genero il riassunto...",
        "summary_empty": "📭 Nessun messaggio tracciato. Scrivete qualcosa e riprovate.",
        "translate_usage": "Uso: /translate [lingua] [testo]\nO: /translate [lingua] in risposta a un messaggio",
        "translate_generating": "🌍 Traduco...",
    }
}


def get_text(user_lang: str, key: str) -> str:
    lang = user_lang if user_lang in translations else "ru"
    return translations[lang].get(key, translations["ru"].get(key, key))


def t(user_id_or_lang, key, **kwargs):
    from bot.storage import storage
    if isinstance(user_id_or_lang, int):
        user = storage.get_user(user_id_or_lang)
        lang = user.get("language", "ru")
    else:
        lang = user_id_or_lang
    text = get_text(lang, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
