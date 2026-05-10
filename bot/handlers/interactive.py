from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.keyboards import get_settings_keyboard, get_vip_keyboard, get_lang_keyboard, get_main_keyboard, get_help_keyboard
from bot.storage import storage
from bot.i18n import get_text

def _get_lang(update):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    return user.get("language", "ru")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    lang = user.get("language", "ru")
    
    # --- Provider selection ---
    if data == "ai_provider":
        user["state"] = "awaiting_setprovider"
        await storage.save()
        
        from bot.ai import PROVIDERS
        keyboard = []
        row = []
        for p in PROVIDERS:
            row.append(InlineKeyboardButton(p.capitalize(), callback_data=f"setprov_{p}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        await query.edit_message_text(
            "⚡ <b>Выбор провайдера</b>\n\nВыберите провайдера из списка:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data.startswith("setprov_"):
        provider = data.split("_", 1)[1]
        from bot.ai import PROVIDERS
        if provider in PROVIDERS:
            user["ai_provider"] = provider
            user["state"] = None
            await storage.save()
            await query.edit_message_text(
                f"✅ Провайдер установлен: <b>{provider}</b>\n\nТеперь установите ключ: <code>/setkey {provider} [ваш_ключ]</code>",
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text(f"❌ Неизвестный провайдер: {provider}")
    
    # --- Model selection ---
    elif data == "ai_model":
        user["state"] = "awaiting_setmodel"
        await storage.save()
        await query.edit_message_text(
            "🧠 <b>Выбор модели</b>\n\n"
            "Отправьте мне название модели в чат\n"
            "(например: <code>gpt-4o</code>, <code>claude-3-5-sonnet-20240620</code>)",
            parse_mode="HTML"
        )
    
    # --- Key configuration ---
    elif data == "ai_keys":
        user["state"] = "awaiting_setkey"
        await storage.save()
        await query.edit_message_text(
            "🔑 <b>Настройка ключей</b>\n\n"
            "Отправьте мне ключ в формате:\n<code>провайдер ваш_ключ</code>\n\n"
            "Например: <code>gemini AIzaSyA...</code>",
            parse_mode="HTML"
        )
    
    # --- VIP ---
    elif data == "vip_reminders":
        await query.edit_message_text(
            "⏰ <b>Напоминания</b>\n\n"
            "Установить: <code>/remind [минуты] [текст]</code>\n"
            "Список: <code>/reminders</code>",
            parse_mode="HTML"
        )
    elif data == "vip_generate":
        user["state"] = "awaiting_generate_prompt"
        await storage.save()
        await query.edit_message_text(
            "🖼️ <b>Генерация изображений</b>\n\n"
            "Отправьте мне описание того, что вы хотите нарисовать!",
            parse_mode="HTML"
        )
    elif data == "vip_guardian":
        await query.edit_message_text(
            "🛡️ <b>AI Guardian</b>\n\n"
            "Защита от спама и токсичности.\n"
            "Включить в группе: <code>/guardian on</code>",
            parse_mode="HTML"
        )
    
    # --- Language ---
    elif data.startswith("lang_"):
        new_lang = data.split("_")[1]
        user["language"] = new_lang
        await storage.save()
        
        text = get_text(new_lang, "lang_changed")
        await query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=get_main_keyboard(new_lang)
        )
    
    # --- Help: Back button (MUST be before help_ prefix!) ---
    elif data == "help_back":
        text = get_text(lang, "help")
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_help_keyboard(lang))
    
    # --- Help: Section details ---
    elif data.startswith("help_"):
        section = data.split("_")[1]
        sections = {
            "base":    "🏠 <b>Базовые:</b>\n/start — запуск бота\n/help — список команд\n/info — информация о боте\n/status — статус системы\n/profile — ваш профиль\n/lang — смена языка",
            "ai":      "💬 <b>AI & Память:</b>\n/ai [вопрос] — задать вопрос\n/setprovider — выбор провайдера\n/setkey — установить API ключ\n/setmodel — выбор модели\n/memorysave [ключ] [значение]\n/memoryget [ключ]\n/memorylist\n/memorydel [ключ]",
            "notes":   "📝 <b>Заметки & Задачи:</b>\n/note [текст] — создать заметку\n/notes — все заметки\n/delnote [номер] — удалить\n/todo [текст] — добавить задачу\n/todo — список задач\n/todo done [номер]\n/todo del [номер]",
            "vip":     "💎 <b>VIP:</b>\n/vip — статус VIP\n/remind [мин] [текст] — напоминание\n/reminders — список\n/generate [описание] — генерация картинок\n/disco on/off — AI Disco Mode",
            "groups":  "👥 <b>Группы:</b>\n/grouphelp — справка\n/ban — бан\n/warn — предупреждение\n/mute — мут\n/kick — кик\n/purge — очистка\n/ask [вопрос] — AI в группе\n/rules — правила\n/setrules — установить правила\n/guardian on/off — защита\n/groupstats — статистика",
            "creator": "👑 <b>Создатель:</b>\n/grant_vip [user_id] [дни] — выдать VIP\n/broadcast [текст] — рассылка\n/stats — полная статистика",
            "games":   "🎮 <b>Игры:</b>\n/dice — кубик\n/coinflip — монетка\n/random [мин] [макс]\n/joke — шутка\n/daily — награда\n/roast — прожарка\n/rep — репутация\n\n🛠 <b>Утилиты:</b>\n/time — время\n/weather [город]\n/calc [выражение]\n/password [длина]\n/translate [текст]"
        }
        text = sections.get(section, f"ℹ️ Раздел: {section}")
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_help_keyboard(lang, submenu=True))


async def keyboard_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    from bot.i18n import translations
    
    btn_ai_vals = [t["btn_ai"] for t in translations.values()]
    btn_mem_vals = [t["btn_mem"] for t in translations.values()]
    btn_notes_vals = [t["btn_notes"] for t in translations.values()]
    btn_vip_vals = [t["btn_vip"] for t in translations.values()]
    btn_settings_vals = [t["btn_settings"] for t in translations.values()]
    btn_admin_vals = [t["btn_admin"] for t in translations.values()]
    btn_lang_vals = [t["btn_lang"] for t in translations.values()]
    
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    lang = user.get("language", "ru")
    
    if text in btn_ai_vals:
        await update.message.reply_text("Отправьте ваш запрос с помощью команды /ai [вопрос] или просто напишите мне в личные сообщения.")
    elif text in btn_mem_vals:
        from bot.handlers.ai_memory import memorylist_command
        await memorylist_command(update, context)
    elif text in btn_notes_vals:
        from bot.handlers.notes import notes_command
        await notes_command(update, context)
    elif text in btn_vip_vals:
        await update.message.reply_text(get_text(lang, "vip_menu"), reply_markup=get_vip_keyboard(lang))
    elif text in btn_settings_vals:
        await update.message.reply_text(get_text(lang, "settings_menu"), reply_markup=get_settings_keyboard(lang))
    elif text in btn_admin_vals:
        from bot.handlers.vip_creator import stats_command
        await stats_command(update, context)
    elif text in btn_lang_vals:
        await update.message.reply_text("🌐 Выберите язык / Choose language / Scegli la lingua:", reply_markup=get_lang_keyboard())
    else:
        # Fallback — check conversation state or AI chat
        if update.effective_chat.type == 'private' and not text.startswith('/'):
            state = user.get("state")
            
            if state == "awaiting_generate_prompt":
                user["state"] = None
                await storage.save()
                context.args = text.split()
                from bot.handlers.media import generate_command
                await generate_command(update, context)
                return
                
            elif state == "awaiting_setprovider":
                user["state"] = None
                provider = text.strip().lower()
                from bot.ai import PROVIDERS
                if provider in PROVIDERS:
                    user["ai_provider"] = provider
                    await storage.save()
                    await update.message.reply_text(f"✅ Провайдер установлен: <b>{provider}</b>\nТеперь установите ключ: <code>/setkey {provider} [ваш_ключ]</code>", parse_mode="HTML")
                else:
                    await update.message.reply_text(f"❌ Неизвестный провайдер: {provider}\nДоступные: {', '.join(PROVIDERS)}")
                return
                
            elif state == "awaiting_setkey":
                user["state"] = None
                parts = text.strip().split(maxsplit=1)
                if len(parts) == 2:
                    provider, key = parts[0].lower(), parts[1]
                    from bot.ai import PROVIDERS
                    if provider in PROVIDERS:
                        user["api_keys"][provider] = key
                        await storage.save()
                        try:
                            await update.message.delete()
                        except Exception:
                            pass
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"✅ Ключ для <b>{provider}</b> сохранён! Ваше сообщение с ключом удалено для безопасности.",
                            parse_mode="HTML"
                        )
                    else:
                        await update.message.reply_text(f"❌ Неизвестный провайдер: {provider}")
                else:
                    await update.message.reply_text("❌ Формат: <code>провайдер ключ</code>\nПример: <code>gemini AIzaSyA...</code>", parse_mode="HTML")
                return
                
            elif state == "awaiting_setmodel":
                user["state"] = None
                model = text.strip()
                user["ai_model"] = model
                await storage.save()
                await update.message.reply_text(f"🧠 Модель установлена: <b>{model}</b>", parse_mode="HTML")
                return
            
            # Default: AI chat
            from bot.ai import ai_handler
            
            msg = await update.message.reply_text("⏳ AI думает...")
            system_prompt = "Ты AI ассистент. "
            if user.get("memory"):
                system_prompt += "Память:\n"
                for k, v in user["memory"].items():
                    system_prompt += f"- {k}: {v}\n"
            
            try:
                response = await ai_handler.generate_response(user_id, text, system_prompt=system_prompt)
                if len(response) > 4000:
                    for i in range(0, len(response), 4000):
                        await update.message.reply_text(response[i:i+4000])
                    await msg.delete()
                else:
                    await msg.edit_text(response)
            except Exception as e:
                await msg.edit_text(f"❌ Ошибка AI: {str(e)}")
