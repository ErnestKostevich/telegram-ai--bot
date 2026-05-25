translations = {
    "ru": {
        # === Welcome / Main ===
        "welcome": ("🤖 <b>Добро пожаловать в AI DISCO BOT v2.1!</b>\n\n"
                     "Я — AI-ассистент со <b>стримингом ответов</b>, как ChatGPT,\n"
                     "прямо внутри Telegram.\n\n"
                     "<b>С чего начать:</b>\n"
                     "1️⃣ ⚙️ Настройки → ⚡ Провайдер (выбери AI)\n"
                     "2️⃣ 🔑 API Ключ (выбери провайдера → пришли ключ)\n"
                     "3️⃣ Просто пиши — бот помнит контекст\n\n"
                     "<b>Что попробовать:</b>\n"
                     "🎙 Голосовое сообщение → распознаю и отвечу\n"
                     "🎭 /persona → 8 характеров AI\n"
                     "🎰 /slots /basket /football → мини-игры\n"
                     "🔮 /today → AI-прогноз дня\n"
                     "🧠 /quiz [тема] → квиз с кнопками\n\n"
                     "💎 <b>VIP:</b> картинки, анализ фото/документов, напоминания.\n\n"
                     "📜 /changelog — что нового\n👇 <i>Меню ниже:</i>"),
        "help": "📚 <b>Справка по командам:</b>\n\nВыберите нужный раздел:",
        "lang_changed": "🇷🇺 Язык изменён на Русский.",
        # Reply keyboard buttons
        "btn_ai": "💬 AI Чат", "btn_mem": "🧠 Память", "btn_notes": "📝 Заметки", "btn_vip": "💎 VIP",
        "btn_settings": "⚙️ Настройки", "btn_games": "🎮 Игры", "btn_tools": "🛠 Утилиты", "btn_lang": "🌐 Язык",
        # Inline buttons
        "ik_provider": "⚡ Провайдер", "ik_model": "🧠 Модель", "ik_keys": "🔑 API Ключ",
        "ik_persona": "🎭 Персона",
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
        "key_saved_dm": "🔐 Ключ для <b>{provider}</b> сохранён и сообщение в группе удалено. Можно пользоваться!",
        "key_saved_no_dm": "🔐 Ключ для пользователя сохранён, сообщение удалено. (Откройте бот в личке чтобы получать подтверждения там.)",
        # v2.1.x additions
        "reminders_hint": "Отменить: /unremind [#] или /unremind all",
        "unremind_usage": "Использование: /unremind [номер] или /unremind all",
        "unremind_ok": "✅ Напоминание #{num} удалено.",
        "unremind_bad_num": "❌ Введите номер от 1 до {max}.",
        "unremind_all": "🗑 Удалено напоминаний: {count}",
        "cancel_done": "✅ Текущее действие отменено.",
        "cancel_nothing": "ℹ️ Сейчас ничего не выполняется.",
        "leaderboard_empty": "📭 Пока никого в рейтинге.",
        "leaderboard_title": "🏆 <b>Топ пользователей:</b>\n",
        "reset_warn": ("⚠️ <b>Сброс данных</b>\n\nЭто <b>навсегда</b> удалит:\n"
                       "• Все ваши заметки, задачи и memory\n"
                       "• Историю диалога и настройки AI\n"
                       "• Все ваши напоминания\n\n"
                       "Перед удалением я отправлю вам экспорт JSON.\n\n"
                       "Подтвердить: <code>/reset confirm</code>"),
        "reset_done": "🗑 Все ваши данные удалены. Чтобы начать заново — /start",
        # v2.2.0: action buttons under AI reply
        "btn_regen": "🔄 Ещё раз",
        "btn_save_note": "💾 В заметки",
        "regen_no_turn": "Нечего регенерировать — сначала задайте вопрос.",
        "regen_loading": "🔄 Генерирую заново...",
        "saved_as_note": "💾 Сохранено как заметка #{num}",
        # v2.2.0: share / referrals
        "share_text": ("👋 <b>Поделись AI DISCO BOT с друзьями!</b>\n\n"
                       "AI-ассистент со стримингом ответов как в ChatGPT, "
                       "10+ моделей на выбор, голосовой ввод, мини-игры — внутри Telegram.\n\n"
                       "🔗 Твоя реферальная ссылка:\n{link}\n\n"
                       "<i>Перешли друзьям — за активных рефералов будут бонусы.</i>"),
        "share_stats": "📊 Уже пригласили: <b>{count}</b>",
        "ref_stats": "🤝 <b>Ваши приглашения:</b> {count}\n\nПолучить ссылку: /share",
        "ref_inviter_notify": "🎉 <b>{name}</b> присоединился по вашей ссылке!\nВсего рефералов: <b>{total}</b>",
        # v2.2.2: onboarding wizard
        "onb_step2_text": ("✅ Язык: <b>Русский</b>\n\n"
                            "🔑 <b>Шаг 2/3: Получи бесплатный API-ключ</b>\n\n"
                            "Я работаю по системе <b>BYOK</b> — ты используешь свой ключ "
                            "от AI-провайдера. Это значит:\n"
                            "• Запросы идут <b>напрямую</b> к AI, минуя меня\n"
                            "• Никто не видит твои данные кроме тебя\n"
                            "• На бесплатных тарифах — <b>$0/мес</b>\n\n"
                            "<b>Самые быстрые бесплатные опции:</b>\n"
                            "• ⚡ <b>Groq</b> — реально быстро, Llama 3.3 70B\n"
                            "• ✨ <b>Gemini</b> — от Google, 60 запросов/мин\n"
                            "• 🌐 <b>OpenRouter</b> — каталог моделей, есть бесплатные\n\n"
                            "Жми <b>🌐</b> чтобы открыть страницу регистрации, "
                            "потом <b>Использовать</b> когда получишь ключ:"),
        "onb_use_btn": "Использовать ✅",
        "onb_have_key": "🔑 У меня уже есть ключ",
        "onb_skip": "⏭ Пропустить",
        "onb_step3_text": ("🔑 <b>Шаг 3/3: Пришли ключ от {provider}</b>\n\n"
                            "Скопируй ключ со страницы провайдера и пришли его сюда "
                            "одним сообщением.\n\n"
                            "<i>Сообщение с ключом удалится автоматически — никто его не увидит.</i>"),
        "onb_back_btn": "🔙 Назад к выбору",
        "onb_skipped": ("👌 Хорошо, настроишь позже.\n\n"
                         "Когда будешь готов — /onboard или ⚙️ Настройки → 🔑 API Ключ"),
        "onb_done": ("🎉 <b>Готово! Ты в строю.</b>\n\n"
                      "Теперь можно:\n"
                      "💬 Просто писать сообщения — бот помнит контекст\n"
                      "🎙 Прислать голосовое — распознаю и отвечу\n"
                      "🎭 /persona — сменить характер AI\n"
                      "🔮 /today — получить AI-прогноз дня\n"
                      "🧠 /quiz [тема] — сгенерировать квиз\n"
                      "🎰 /slots /basket /football — мини-игры\n"
                      "💬 <code>@AI_DISCO_BOT [вопрос]</code> — спрашивай меня прямо в любом чате\n\n"
                      "/help — полный список команд"),
        # v2.3.0: inline mode
        "inline_setup_btn": "🔑 Открой бот и установи ключ — это бесплатно",
        "inline_hint_title": "💬 Напиши вопрос после @AI_DISCO_BOT",
        "inline_hint_desc": "Например: @AI_DISCO_BOT как работают словари в Python",
        "inline_hint_msg": "💡 Использование: @AI_DISCO_BOT [вопрос]\n\nНапиши вопрос — AI ответит inline.",
        "inline_ask_title": "🤖 Спросить AI: «{q}»",
        "inline_ask_desc": "Отправить плейсхолдер. Жми «Сгенерировать» в чате — AI ответит.",
        "inline_tap_to_generate": "Жми кнопку чтобы получить ответ AI...",
        "inline_generate_btn": "✨ Сгенерировать",
        "inline_working": "🤖 Генерирую...",
        "inline_expired": "⌛ Запрос устарел. Открой inline снова: @AI_DISCO_BOT [вопрос]",
        "inline_not_author": "🔐 Только тот, кто задал вопрос, может сгенерировать ответ (используется его ключ).",
        "from_inline_intro": "👋 Привет! Чтобы пользоваться <code>@AI_DISCO_BOT</code> в любом чате, нужно настроить свой AI-ключ:",
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
        "notes_full": "❌ Лимит заметок: {max}. Удалите старые: /delnote [#]",
        "tasks_full": "❌ Лимит задач: {max}. Очистите: /todo del [#]",
        "mem_full": "❌ Лимит memory-записей: {max}. Удалите старые: /memorydel [ключ]",
        # WOW: voice
        "voice_needs_openai": "🎙 Чтобы я распознавал голосовые, добавьте ключ OpenAI:\n<code>/setkey openai sk-...</code>",
        "voice_transcribing": "🎙 Распознаю голос...",
        "voice_too_big": "❌ Голосовое слишком большое (>20 MB).",
        "voice_empty": "🤔 Не удалось распознать речь.",
        "voice_got": "🎙 <i>«{text}»</i>",
        # WOW: persona
        "persona_status": "🎭 <b>Текущая персона:</b> <code>{current}</code>\n\nДоступные: {list}\n\nСменить: <code>/persona [имя]</code> или <code>/persona off</code>",
        "persona_set": "🎭 Персона установлена: <b>{name}</b>",
        "persona_off": "🎭 Персона сброшена.",
        "persona_unknown": "❌ Неизвестная персона.\nДоступные: {list}",
        # WOW: mini-games
        "game_win": "🎉 <b>{label}</b>\nПобед: <b>{wins}</b> / {plays}",
        "game_lose": "🎲 Не повезло в этот раз.\nПобед: {wins} / {plays}",
        # WOW: today
        "today_loading": "🔮 Составляю прогноз дня...",
        "today_text": "🔮 <b>Сегодня — {date}</b>\n\n{body}",
        # WOW: quiz
        "quiz_default_topic": "общие знания",
        "quiz_loading": "🧠 Готовлю вопрос про «{topic}»...",
        "quiz_error": "❌ Не получилось сгенерировать квиз: {err}",
        "quiz_question": "🧠 <b>Квиз: {topic}</b>\n\n{q}",
        "quiz_correct": "✅ <b>Правильно!</b> Ответ <b>{chosen}</b> — {text}",
        "quiz_wrong": "❌ Неверно. Вы выбрали <b>{chosen}</b> ({chosen_text}).\nПравильный: <b>{correct}</b> — {correct_text}",
        "quiz_score": "Счёт: <b>{correct}/{total}</b>",
        "quiz_expired": "⌛ Этот квиз уже завершён или устарел.",
        # WOW: picker prompts
        "provider_pick": "⚡ <b>Выберите провайдера AI:</b>\n\nТекущий помечен ✅",
        "key_pick_provider": "🔑 <b>Для какого провайдера ключ?</b>\n\nВыберите — потом я попрошу сам ключ.",
        "key_send_for": "🔑 Пришлите API-ключ для <b>{provider}</b>.\n\n<i>Сообщение с ключом будет удалено автоматически.</i>",
        "persona_pick": "🎭 <b>Выберите персону:</b>\n\nТекущая помечена ✅",
        "persona_set_short": "✅ Персона: <b>{name}</b>",
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
        "welcome": ("🤖 <b>Welcome to AI DISCO BOT v2.1!</b>\n\n"
                     "AI assistant with <b>streaming responses</b> like ChatGPT,\n"
                     "right inside Telegram.\n\n"
                     "<b>Quick start:</b>\n"
                     "1️⃣ ⚙️ Settings → ⚡ Provider (pick an AI)\n"
                     "2️⃣ 🔑 API Key (pick provider → send the key)\n"
                     "3️⃣ Just type — I remember context\n\n"
                     "<b>Try this:</b>\n"
                     "🎙 Voice message → I'll transcribe and answer\n"
                     "🎭 /persona → 8 AI characters\n"
                     "🎰 /slots /basket /football → mini-games\n"
                     "🔮 /today → AI fortune of the day\n"
                     "🧠 /quiz [topic] → quiz with buttons\n\n"
                     "💎 <b>VIP:</b> image gen, photo/doc analysis, reminders.\n\n"
                     "📜 /changelog — what's new\n👇 <i>Menu below:</i>"),
        "help": "📚 <b>Command Reference:</b>\n\nPick a section:",
        "lang_changed": "🇬🇧 Language changed to English.",
        "btn_ai": "💬 AI Chat", "btn_mem": "🧠 Memory", "btn_notes": "📝 Notes", "btn_vip": "💎 VIP",
        "btn_settings": "⚙️ Settings", "btn_games": "🎮 Games", "btn_tools": "🛠 Tools", "btn_lang": "🌐 Language",
        "ik_provider": "⚡ Provider", "ik_model": "🧠 Model", "ik_keys": "🔑 API Key",
        "ik_persona": "🎭 Persona",
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
        "key_saved_dm": "🔐 Key for <b>{provider}</b> saved and the group message was deleted. You're good to go!",
        "key_saved_no_dm": "🔐 Key saved, message deleted. (Open me in a DM to get confirmations there instead.)",
        # v2.1.x additions
        "reminders_hint": "Cancel: /unremind [#] or /unremind all",
        "unremind_usage": "Usage: /unremind [number] or /unremind all",
        "unremind_ok": "✅ Reminder #{num} cancelled.",
        "unremind_bad_num": "❌ Enter a number from 1 to {max}.",
        "unremind_all": "🗑 Cancelled reminders: {count}",
        "cancel_done": "✅ Current action cancelled.",
        "cancel_nothing": "ℹ️ Nothing in progress.",
        "leaderboard_empty": "📭 No one on the leaderboard yet.",
        "leaderboard_title": "🏆 <b>Top users:</b>\n",
        "reset_warn": ("⚠️ <b>Reset data</b>\n\nThis will <b>permanently</b> delete:\n"
                       "• All your notes, tasks and memory\n"
                       "• Chat history and AI settings\n"
                       "• All your reminders\n\n"
                       "I'll send you a JSON export first.\n\n"
                       "Confirm: <code>/reset confirm</code>"),
        "reset_done": "🗑 All your data has been deleted. To start again — /start",
        # v2.2.0: action buttons under AI reply
        "btn_regen": "🔄 Regenerate",
        "btn_save_note": "💾 Save as note",
        "regen_no_turn": "Nothing to regenerate — ask a question first.",
        "regen_loading": "🔄 Regenerating...",
        "saved_as_note": "💾 Saved as note #{num}",
        # v2.2.0: share / referrals
        "share_text": ("👋 <b>Share AI DISCO BOT with friends!</b>\n\n"
                       "AI assistant with ChatGPT-style streaming, 10+ models, "
                       "voice input, mini-games — right inside Telegram.\n\n"
                       "🔗 Your referral link:\n{link}\n\n"
                       "<i>Forward to friends — active referrals earn bonuses.</i>"),
        "share_stats": "📊 Invited so far: <b>{count}</b>",
        "ref_stats": "🤝 <b>Your invites:</b> {count}\n\nGet link: /share",
        "ref_inviter_notify": "🎉 <b>{name}</b> joined via your link!\nTotal referrals: <b>{total}</b>",
        # v2.2.2: onboarding wizard
        "onb_step2_text": ("✅ Language: <b>English</b>\n\n"
                            "🔑 <b>Step 2/3: Get a free API key</b>\n\n"
                            "I work on a <b>BYOK</b> system — you use your own key "
                            "from an AI provider. That means:\n"
                            "• Requests go <b>directly</b> to the AI, not through me\n"
                            "• Nobody sees your data but you\n"
                            "• On free tiers — <b>$0/month</b>\n\n"
                            "<b>Fastest free options:</b>\n"
                            "• ⚡ <b>Groq</b> — actually fast, Llama 3.3 70B\n"
                            "• ✨ <b>Gemini</b> — from Google, 60 req/min\n"
                            "• 🌐 <b>OpenRouter</b> — model catalog, free ones included\n\n"
                            "Tap <b>🌐</b> to open the signup page, "
                            "then <b>Use</b> once you have a key:"),
        "onb_use_btn": "Use ✅",
        "onb_have_key": "🔑 I already have a key",
        "onb_skip": "⏭ Skip",
        "onb_step3_text": ("🔑 <b>Step 3/3: Send your {provider} key</b>\n\n"
                            "Copy the key from the provider's page and send it here "
                            "as a single message.\n\n"
                            "<i>The message with the key will be deleted automatically — nobody will see it.</i>"),
        "onb_back_btn": "🔙 Back to providers",
        "onb_skipped": ("👌 OK, you can set it up later.\n\n"
                         "When you're ready — /onboard or ⚙️ Settings → 🔑 API Key"),
        "onb_done": ("🎉 <b>All set! You're good to go.</b>\n\n"
                      "Now you can:\n"
                      "💬 Just type messages — I remember context\n"
                      "🎙 Send a voice message — I'll transcribe & answer\n"
                      "🎭 /persona — switch AI character\n"
                      "🔮 /today — get an AI fortune of the day\n"
                      "🧠 /quiz [topic] — generate a quiz\n"
                      "🎰 /slots /basket /football — mini-games\n"
                      "💬 <code>@AI_DISCO_BOT [question]</code> — ask me right inside any chat\n\n"
                      "/help — full list of commands"),
        # v2.3.0: inline mode
        "inline_setup_btn": "🔑 Open bot and set your key — it's free",
        "inline_hint_title": "💬 Type a question after @AI_DISCO_BOT",
        "inline_hint_desc": "Example: @AI_DISCO_BOT how do dicts work in Python",
        "inline_hint_msg": "💡 Usage: @AI_DISCO_BOT [question]\n\nType a question — AI will answer inline.",
        "inline_ask_title": "🤖 Ask AI: \"{q}\"",
        "inline_ask_desc": "Send a placeholder. Tap \"Generate\" in chat — AI will reply.",
        "inline_tap_to_generate": "Tap the button to get the AI answer...",
        "inline_generate_btn": "✨ Generate",
        "inline_working": "🤖 Generating...",
        "inline_expired": "⌛ This query is stale. Open inline again: @AI_DISCO_BOT [question]",
        "inline_not_author": "🔐 Only the original asker can generate (uses their key).",
        "from_inline_intro": "👋 Hi! To use <code>@AI_DISCO_BOT</code> in any chat, you need to set up your AI key first:",
        "model_set": "🧠 Model: <b>{model}</b>", "model_usage": "Usage: /setmodel [model]\nCurrent: {current}",
        "mem_saved": "✅ Saved: {key} = {value}", "mem_usage": "Usage: /memorysave [key] [value]",
        "mem_value": "🧠 {key}: {value}", "mem_not_found": "❌ Key '{key}' not found.",
        "mem_empty": "📭 Memory is empty.", "mem_title": "🧠 <b>Memory:</b>\n\n",
        "mem_deleted": "🗑 '{key}' deleted.", "mem_del_usage": "Usage: /memorydel [key]",
        "note_saved": "✅ Note #{num} saved!", "note_usage": "Usage: /note [text]",
        "notes_empty": "📭 No notes.", "notes_title": "📝 <b>Notes ({count}):</b>\n\n",
        "note_deleted": "✅ Note #{num} deleted.", "note_del_usage": "Usage: /delnote [number]",
        "note_not_found": "❌ Note not found.",
        "notes_full": "❌ Notes limit: {max}. Delete old ones: /delnote [#]",
        "tasks_full": "❌ Tasks limit: {max}. Clean up: /todo del [#]",
        "mem_full": "❌ Memory entries limit: {max}. Delete old: /memorydel [key]",
        # WOW: voice
        "voice_needs_openai": "🎙 To transcribe voice messages, add an OpenAI key:\n<code>/setkey openai sk-...</code>",
        "voice_transcribing": "🎙 Transcribing voice...",
        "voice_too_big": "❌ Voice file too large (>20 MB).",
        "voice_empty": "🤔 Couldn't understand the voice message.",
        "voice_got": "🎙 <i>“{text}”</i>",
        # WOW: persona
        "persona_status": "🎭 <b>Current persona:</b> <code>{current}</code>\n\nAvailable: {list}\n\nSwitch: <code>/persona [name]</code> or <code>/persona off</code>",
        "persona_set": "🎭 Persona set: <b>{name}</b>",
        "persona_off": "🎭 Persona reset.",
        "persona_unknown": "❌ Unknown persona.\nAvailable: {list}",
        # WOW: mini-games
        "game_win": "🎉 <b>{label}</b>\nWins: <b>{wins}</b> / {plays}",
        "game_lose": "🎲 Better luck next time.\nWins: {wins} / {plays}",
        # WOW: today
        "today_loading": "🔮 Reading the cosmic signals...",
        "today_text": "🔮 <b>Today — {date}</b>\n\n{body}",
        # WOW: quiz
        "quiz_default_topic": "general knowledge",
        "quiz_loading": "🧠 Cooking up a question about “{topic}”...",
        "quiz_error": "❌ Couldn't generate quiz: {err}",
        "quiz_question": "🧠 <b>Quiz: {topic}</b>\n\n{q}",
        "quiz_correct": "✅ <b>Correct!</b> Answer <b>{chosen}</b> — {text}",
        "quiz_wrong": "❌ Wrong. You chose <b>{chosen}</b> ({chosen_text}).\nCorrect: <b>{correct}</b> — {correct_text}",
        "quiz_score": "Score: <b>{correct}/{total}</b>",
        "quiz_expired": "⌛ This quiz is already done or has expired.",
        # WOW: picker prompts
        "provider_pick": "⚡ <b>Pick an AI provider:</b>\n\nCurrent marked with ✅",
        "key_pick_provider": "🔑 <b>Which provider is the key for?</b>\n\nPick one — I'll then ask for the key itself.",
        "key_send_for": "🔑 Send the API key for <b>{provider}</b>.\n\n<i>The message with the key will be deleted automatically.</i>",
        "persona_pick": "🎭 <b>Pick a persona:</b>\n\nCurrent marked with ✅",
        "persona_set_short": "✅ Persona: <b>{name}</b>",
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
        "welcome": ("🤖 <b>Benvenuto in AI DISCO BOT v2.1!</b>\n\n"
                     "Assistente AI con <b>risposte in streaming</b> come ChatGPT,\n"
                     "dentro Telegram.\n\n"
                     "<b>Come iniziare:</b>\n"
                     "1️⃣ ⚙️ Impostazioni → ⚡ Provider\n"
                     "2️⃣ 🔑 Chiave API (scegli provider → invia chiave)\n"
                     "3️⃣ Scrivi — ricordo il contesto\n\n"
                     "<b>Da provare:</b>\n"
                     "🎙 Messaggio vocale → trascrivo e rispondo\n"
                     "🎭 /persona → 8 personaggi AI\n"
                     "🎰 /slots /basket /football → mini-giochi\n"
                     "🔮 /today → oroscopo AI del giorno\n"
                     "🧠 /quiz [tema] → quiz con bottoni\n\n"
                     "💎 <b>VIP:</b> generazione immagini, analisi foto/doc, promemoria.\n\n"
                     "📜 /changelog — novità\n👇 <i>Menu sotto:</i>"),
        "help": "📚 <b>Guida comandi:</b>\n\nSeleziona una sezione:",
        "lang_changed": "🇮🇹 Lingua cambiata in Italiano.",
        "btn_ai": "💬 Chat AI", "btn_mem": "🧠 Memoria", "btn_notes": "📝 Note", "btn_vip": "💎 VIP",
        "btn_settings": "⚙️ Impostazioni", "btn_games": "🎮 Giochi", "btn_tools": "🛠 Strumenti", "btn_lang": "🌐 Lingua",
        "ik_provider": "⚡ Provider", "ik_model": "🧠 Modello", "ik_keys": "🔑 Chiave API",
        "ik_persona": "🎭 Persona",
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
        "key_saved_dm": "🔐 Chiave per <b>{provider}</b> salvata e messaggio del gruppo eliminato. Pronto!",
        "key_saved_no_dm": "🔐 Chiave salvata, messaggio eliminato. (Apri il bot in privato per ricevere conferme lì.)",
        # v2.1.x additions
        "reminders_hint": "Annulla: /unremind [#] o /unremind all",
        "unremind_usage": "Uso: /unremind [numero] o /unremind all",
        "unremind_ok": "✅ Promemoria #{num} annullato.",
        "unremind_bad_num": "❌ Inserisci un numero da 1 a {max}.",
        "unremind_all": "🗑 Promemoria annullati: {count}",
        "cancel_done": "✅ Azione corrente annullata.",
        "cancel_nothing": "ℹ️ Nessuna azione in corso.",
        "leaderboard_empty": "📭 Nessuno in classifica.",
        "leaderboard_title": "🏆 <b>Top utenti:</b>\n",
        "reset_warn": ("⚠️ <b>Reset dati</b>\n\nVerranno <b>permanentemente</b> eliminati:\n"
                       "• Tutte note, compiti e memoria\n"
                       "• Cronologia chat e impostazioni AI\n"
                       "• Tutti i promemoria\n\n"
                       "Prima ti invio un export JSON.\n\n"
                       "Conferma: <code>/reset confirm</code>"),
        "reset_done": "🗑 Tutti i tuoi dati sono stati eliminati. Per ricominciare — /start",
        # v2.2.0: action buttons under AI reply
        "btn_regen": "🔄 Rigenera",
        "btn_save_note": "💾 Salva come nota",
        "regen_no_turn": "Niente da rigenerare — fai prima una domanda.",
        "regen_loading": "🔄 Rigenero...",
        "saved_as_note": "💾 Salvato come nota #{num}",
        # v2.2.0: share / referrals
        "share_text": ("👋 <b>Condividi AI DISCO BOT con gli amici!</b>\n\n"
                       "Assistente AI con risposte streaming stile ChatGPT, 10+ modelli, "
                       "voce, mini-giochi — dentro Telegram.\n\n"
                       "🔗 Il tuo link di invito:\n{link}\n\n"
                       "<i>Inoltralo agli amici — referral attivi sbloccano bonus.</i>"),
        "share_stats": "📊 Invitati finora: <b>{count}</b>",
        "ref_stats": "🤝 <b>I tuoi inviti:</b> {count}\n\nLink: /share",
        "ref_inviter_notify": "🎉 <b>{name}</b> si è unito tramite il tuo link!\nReferral totali: <b>{total}</b>",
        # v2.2.2: onboarding wizard
        "onb_step2_text": ("✅ Lingua: <b>Italiano</b>\n\n"
                            "🔑 <b>Passo 2/3: Ottieni una chiave API gratuita</b>\n\n"
                            "Lavoro con il sistema <b>BYOK</b> — usi la tua chiave "
                            "di un provider AI. Significa:\n"
                            "• Le richieste vanno <b>direttamente</b> all'AI, non passano da me\n"
                            "• Nessuno vede i tuoi dati tranne te\n"
                            "• Sui piani gratuiti — <b>$0/mese</b>\n\n"
                            "<b>Opzioni gratuite più veloci:</b>\n"
                            "• ⚡ <b>Groq</b> — davvero veloce, Llama 3.3 70B\n"
                            "• ✨ <b>Gemini</b> — di Google, 60 req/min\n"
                            "• 🌐 <b>OpenRouter</b> — catalogo modelli, alcuni gratis\n\n"
                            "Tocca <b>🌐</b> per aprire la pagina di registrazione, "
                            "poi <b>Usa</b> quando hai la chiave:"),
        "onb_use_btn": "Usa ✅",
        "onb_have_key": "🔑 Ho già una chiave",
        "onb_skip": "⏭ Salta",
        "onb_step3_text": ("🔑 <b>Passo 3/3: Invia la chiave per {provider}</b>\n\n"
                            "Copia la chiave dalla pagina del provider e inviala qui "
                            "come messaggio singolo.\n\n"
                            "<i>Il messaggio con la chiave verrà eliminato automaticamente.</i>"),
        "onb_back_btn": "🔙 Torna ai provider",
        "onb_skipped": ("👌 OK, lo configurerai più tardi.\n\n"
                         "Quando sei pronto — /onboard o ⚙️ Impostazioni → 🔑 Chiave API"),
        "onb_done": ("🎉 <b>Tutto pronto! Sei a posto.</b>\n\n"
                      "Ora puoi:\n"
                      "💬 Scrivere messaggi — ricordo il contesto\n"
                      "🎙 Inviare un vocale — lo trascrivo e rispondo\n"
                      "🎭 /persona — cambia personaggio AI\n"
                      "🔮 /today — oroscopo AI del giorno\n"
                      "🧠 /quiz [tema] — genera un quiz\n"
                      "🎰 /slots /basket /football — mini-giochi\n"
                      "💬 <code>@AI_DISCO_BOT [domanda]</code> — chiedi in qualsiasi chat\n\n"
                      "/help — lista completa dei comandi"),
        # v2.3.0: inline mode
        "inline_setup_btn": "🔑 Apri il bot e imposta la chiave — è gratis",
        "inline_hint_title": "💬 Scrivi una domanda dopo @AI_DISCO_BOT",
        "inline_hint_desc": "Esempio: @AI_DISCO_BOT come funzionano i dizionari in Python",
        "inline_hint_msg": "💡 Uso: @AI_DISCO_BOT [domanda]\n\nScrivi una domanda — l'AI risponde inline.",
        "inline_ask_title": "🤖 Chiedi all'AI: «{q}»",
        "inline_ask_desc": "Invia un placeholder. Tocca «Genera» in chat — l'AI risponderà.",
        "inline_tap_to_generate": "Tocca il bottone per la risposta AI...",
        "inline_generate_btn": "✨ Genera",
        "inline_working": "🤖 Genero...",
        "inline_expired": "⌛ Richiesta scaduta. Riapri inline: @AI_DISCO_BOT [domanda]",
        "inline_not_author": "🔐 Solo chi ha posto la domanda può generare (usa la sua chiave).",
        "from_inline_intro": "👋 Ciao! Per usare <code>@AI_DISCO_BOT</code> in qualsiasi chat, devi prima configurare la tua chiave AI:",
        "model_set": "🧠 Modello: <b>{model}</b>", "model_usage": "Uso: /setmodel [modello]\nAttuale: {current}",
        "mem_saved": "✅ Salvato: {key} = {value}", "mem_usage": "Uso: /memorysave [chiave] [valore]",
        "mem_value": "🧠 {key}: {value}", "mem_not_found": "❌ Chiave '{key}' non trovata.",
        "mem_empty": "📭 Memoria vuota.", "mem_title": "🧠 <b>Memoria:</b>\n\n",
        "mem_deleted": "🗑 '{key}' eliminato.", "mem_del_usage": "Uso: /memorydel [chiave]",
        "note_saved": "✅ Nota #{num} salvata!", "note_usage": "Uso: /note [testo]",
        "notes_empty": "📭 Nessuna nota.", "notes_title": "📝 <b>Note ({count}):</b>\n\n",
        "note_deleted": "✅ Nota #{num} eliminata.", "note_del_usage": "Uso: /delnote [numero]",
        "note_not_found": "❌ Nota non trovata.",
        "notes_full": "❌ Limite note: {max}. Elimina vecchie: /delnote [#]",
        "tasks_full": "❌ Limite compiti: {max}. Pulisci: /todo del [#]",
        "mem_full": "❌ Limite memoria: {max}. Elimina vecchi: /memorydel [chiave]",
        # WOW: voice
        "voice_needs_openai": "🎙 Per trascrivere i vocali, aggiungi una chiave OpenAI:\n<code>/setkey openai sk-...</code>",
        "voice_transcribing": "🎙 Trascrivo la voce...",
        "voice_too_big": "❌ Vocale troppo grande (>20 MB).",
        "voice_empty": "🤔 Non sono riuscito a capire il vocale.",
        "voice_got": "🎙 <i>«{text}»</i>",
        # WOW: persona
        "persona_status": "🎭 <b>Persona attuale:</b> <code>{current}</code>\n\nDisponibili: {list}\n\nCambia: <code>/persona [nome]</code> o <code>/persona off</code>",
        "persona_set": "🎭 Persona impostata: <b>{name}</b>",
        "persona_off": "🎭 Persona reset.",
        "persona_unknown": "❌ Persona sconosciuta.\nDisponibili: {list}",
        # WOW: mini-games
        "game_win": "🎉 <b>{label}</b>\nVittorie: <b>{wins}</b> / {plays}",
        "game_lose": "🎲 Più fortuna la prossima volta.\nVittorie: {wins} / {plays}",
        # WOW: today
        "today_loading": "🔮 Leggo i segnali cosmici...",
        "today_text": "🔮 <b>Oggi — {date}</b>\n\n{body}",
        # WOW: quiz
        "quiz_default_topic": "cultura generale",
        "quiz_loading": "🧠 Preparo una domanda su «{topic}»...",
        "quiz_error": "❌ Impossibile generare il quiz: {err}",
        "quiz_question": "🧠 <b>Quiz: {topic}</b>\n\n{q}",
        "quiz_correct": "✅ <b>Esatto!</b> Risposta <b>{chosen}</b> — {text}",
        "quiz_wrong": "❌ Sbagliato. Hai scelto <b>{chosen}</b> ({chosen_text}).\nCorretta: <b>{correct}</b> — {correct_text}",
        "quiz_score": "Punteggio: <b>{correct}/{total}</b>",
        "quiz_expired": "⌛ Quiz già completato o scaduto.",
        # WOW: picker prompts
        "provider_pick": "⚡ <b>Scegli un provider AI:</b>\n\nAttuale segnato con ✅",
        "key_pick_provider": "🔑 <b>Per quale provider è la chiave?</b>\n\nScegli — poi ti chiederò la chiave.",
        "key_send_for": "🔑 Invia la chiave API per <b>{provider}</b>.\n\n<i>Il messaggio con la chiave verrà eliminato automaticamente.</i>",
        "persona_pick": "🎭 <b>Scegli una persona:</b>\n\nAttuale segnata con ✅",
        "persona_set_short": "✅ Persona: <b>{name}</b>",
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
