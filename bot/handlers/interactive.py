from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import get_settings_keyboard, get_vip_keyboard, get_lang_keyboard, get_main_keyboard, get_help_keyboard
from bot.storage import storage

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "ai_provider":
        user_id = update.effective_user.id
        user = storage.get_user(user_id)
        user["state"] = "awaiting_setprovider"
        await storage.save()
        
        # Add inline keyboard for providers
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
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
            "⚡ <b>Выбор провайдера</b>\n\nВыберите провайдера из списка ниже или отправьте его название в чат:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "vip_reminders":
        await query.edit_message_text("Для установки напоминания используйте:\n<code>/remind [минуты] [текст]</code>\nСписок: <code>/reminders</code>", parse_mode="HTML")
    elif data == "vip_generate":
        user_id = update.effective_user.id
        user = storage.get_user(user_id)
        user["state"] = "awaiting_generate_prompt"
        await storage.save()
        await query.edit_message_text("🖼️ <b>Генерация изображений</b>\n\nОтправьте мне описание того, что вы хотите нарисовать!", parse_mode="HTML")
        
    elif data.startswith("setprov_"):
        provider = data.split("_")[1]
        user_id = update.effective_user.id
        user = storage.get_user(user_id)
        
        context.args = [provider]
        from bot.handlers.ai_memory import setprovider_command
        await setprovider_command(update, context)
        
        # Also clean up the message
        await query.message.delete()
        
    elif data.startswith("lang_"):
        lang = data.split("_")[1]
        user_id = update.effective_user.id
        user = storage.get_user(user_id)
        user["language"] = lang
        await storage.save()
        
        from bot.i18n import get_text
        text = get_text(lang, "lang_changed")
        
        # We delete the inline keyboard message and send a new one with the updated reply_markup (main keyboard)
        await query.message.delete()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=get_main_keyboard(lang))
        
    # Help sections
    elif data.startswith("help_"):
        section = data.split("_")[1]
        text = ""
        if section == "base":
            text = "🏠 <b>Базовые:</b>\n/start, /help, /info, /status"
        elif section == "ai":
            text = "💬 <b>AI & Память:</b>\n/setprovider, /setkey, /ai, /memorysave, /memoryget, /memorylist, /memorydel"
        elif section == "notes":
            text = "📝 <b>Заметки:</b>\n/note, /notes, /delnote"
        elif section == "vip":
            text = "💎 <b>VIP:</b>\n/vip, /remind, /reminders"
        elif section == "groups":
            text = "👥 <b>Группы:</b>\n/grouphelp, /ban, /ask, /rules, /setrules"
        elif section == "creator":
            text = "👑 <b>Создатель:</b>\n/grant_vip, /broadcast, /stats"
        elif section == "games":
            text = "🎮 <b>Игры:</b>\n/dice, /coinflip, /random, /joke\n🛠 <b>Утилиты:</b>\n/time, /weather, /calc, /password"
            
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_help_keyboard(submenu=True))
        
    elif data == "help_back":
        from bot.i18n import get_text
        user_id = update.effective_user.id
        user = storage.get_user(user_id)
        user_lang = user.get("language", "ru")
        text = get_text(user_lang, "help")
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_help_keyboard())
        
    elif data == "ai_model":
        user_id = update.effective_user.id
        user = storage.get_user(user_id)
        user["state"] = "awaiting_setmodel"
        await storage.save()
        await query.edit_message_text(
            "🧠 <b>Выбор модели</b>\n\n"
            "Отправьте мне название модели в чат (например, gpt-4o, claude-3-5-sonnet-20240620).\n\n"
            "Или используйте команду: <code>/setmodel [название]</code>",
            parse_mode="HTML"
        )
    elif data == "ai_keys":
        user_id = update.effective_user.id
        user = storage.get_user(user_id)
        user["state"] = "awaiting_setkey"
        await storage.save()
        await query.edit_message_text(
            "🔑 <b>Настройка ключей</b>\n\n"
            "Отправьте мне ключ в формате: <b>[провайдер] [ключ]</b>\n"
            "Например: <code>gemini AIzaSyA...</code>",
            parse_mode="HTML"
        )
    elif data == "vip_guardian":
        await query.edit_message_text("🛡️ <b>AI Guardian</b>\n\nЗащита от спама и токсичности. Включить в группе: <code>/guardian on</code>", parse_mode="HTML")

async def keyboard_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # We must match against any language string for these buttons
    from bot.i18n import translations
    
    btn_ai_vals = [t["btn_ai"] for t in translations.values()]
    btn_mem_vals = [t["btn_mem"] for t in translations.values()]
    btn_notes_vals = [t["btn_notes"] for t in translations.values()]
    btn_vip_vals = [t["btn_vip"] for t in translations.values()]
    btn_settings_vals = [t["btn_settings"] for t in translations.values()]
    btn_admin_vals = [t["btn_admin"] for t in translations.values()]
    btn_lang_vals = [t["btn_lang"] for t in translations.values()]
    
    if text in btn_ai_vals:
        await update.message.reply_text("Отправьте ваш запрос с помощью команды /ai [вопрос] или просто напишите мне, если я добавлен в группу с нужными правами.")
    elif text in btn_mem_vals:
        from bot.handlers.ai_memory import memorylist_command
        await memorylist_command(update, context)
    elif text in btn_notes_vals:
        from bot.handlers.notes import notes_command
        await notes_command(update, context)
    elif text in btn_vip_vals:
        await update.message.reply_text("💎 VIP Меню:", reply_markup=get_vip_keyboard())
    elif text in btn_settings_vals:
        await update.message.reply_text("⚙️ Настройки AI:", reply_markup=get_settings_keyboard())
    elif text in btn_admin_vals:
        from bot.handlers.vip_creator import stats_command
        await stats_command(update, context)
    elif text in btn_lang_vals:
        await update.message.reply_text("🌐 Выберите язык / Choose language / Scegli la lingua:", reply_markup=get_lang_keyboard())
    else:
        # Fallback to AI answer if it's a private chat and not a command
        if update.effective_chat.type == 'private' and not text.startswith('/'):
            user_id = update.effective_user.id
            user = storage.get_user(user_id)
            
            # Check conversation states
            state = user.get("state")
            if state == "awaiting_generate_prompt":
                # Clear state
                user["state"] = None
                await storage.save()
                
                # Mock context.args and call generate_command
                context.args = text.split()
                from bot.handlers.media import generate_command
                await generate_command(update, context)
                return
            elif state == "awaiting_setprovider":
                user["state"] = None
                await storage.save()
                context.args = [text]
                from bot.handlers.ai_memory import setprovider_command
                await setprovider_command(update, context)
                return
            elif state == "awaiting_setkey":
                user["state"] = None
                await storage.save()
                # Text should be provider and key. But we don't know the provider. 
                # Let's assume they type "/setkey provider key" directly.
                await update.message.reply_text(f"Используйте команду: /setkey [провайдер] {text}")
                return
            elif state == "awaiting_setmodel":
                user["state"] = None
                await storage.save()
                context.args = text.split()
                from bot.handlers.ai_memory import setmodel_command
                await setmodel_command(update, context)
                return
                
            from bot.ai import ai_handler
            
            msg = await update.message.reply_text("⏳ AI думает...")
            system_prompt = "Ты AI ассистент. "
            if user.get("memory"):
                system_prompt += "Память:\n"
                for k, v in user["memory"].items():
                    system_prompt += f"- {k}: {v}\n"
            response = await ai_handler.generate_response(user_id, text, system_prompt=system_prompt)
            
            if len(response) > 4000:
                await msg.edit_text("Ответ слишком длинный.")
            else:
                await msg.edit_text(response)
