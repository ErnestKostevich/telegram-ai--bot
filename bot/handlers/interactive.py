from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import get_settings_keyboard, get_vip_keyboard

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "ai_provider":
        await query.edit_message_text(
            "⚡ <b>Выбор провайдера</b>\n\n"
            "Доступные: gemini, openai, anthropic, groq, openrouter, deepseek, mistral, together, xai, cohere\n\n"
            "Используйте команду: <code>/setprovider [название]</code>",
            parse_mode="HTML"
        )
    elif data == "ai_keys":
        await query.edit_message_text(
            "🔑 <b>Настройка ключей</b>\n\n"
            "Установите ключ для выбранного провайдера.\n"
            "Используйте: <code>/setkey [провайдер] [ваш_ключ]</code>",
            parse_mode="HTML"
        )
    elif data == "vip_reminders":
        await query.edit_message_text("Для установки напоминания используйте:\n<code>/remind [минуты] [текст]</code>\nСписок: <code>/reminders</code>", parse_mode="HTML")
    elif data == "vip_generate":
        await query.edit_message_text("Скоро: Генерация изображений через BYOK!", parse_mode="HTML")
        
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
            text = "🎮 <b>Игры:</b>\n/dice, /coinflip, /random, /joke"
            
        await query.edit_message_text(text, parse_mode="HTML")

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
        await update.message.reply_text("🌐 Для смены языка отправьте: /lang [ru|en|it]\n🌐 To change language send: /lang [ru|en|it]")
    else:
        # Fallback to AI answer if it's a private chat and not a command
        if update.effective_chat.type == 'private' and not text.startswith('/'):
            from bot.ai import ai_handler
            from bot.storage import storage
            user_id = update.effective_user.id
            user = storage.get_user(user_id)
            
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
