from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler, PROVIDERS

async def setprovider_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        await update.message.reply_text(f"Использование: /setprovider [провайдер]\nДоступные: {', '.join(PROVIDERS)}")
        return
        
    provider = context.args[0].lower()
    if provider not in PROVIDERS:
        await update.message.reply_text(f"❌ Неизвестный провайдер. Доступные: {', '.join(PROVIDERS)}")
        return
        
    user["ai_provider"] = provider
    await storage.save()
    await update.message.reply_text(f"✅ Провайдер установлен: {provider}. Убедитесь, что у вас задан ключ: /setkey {provider} [ключ]")

async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /setkey [провайдер] [ключ]")
        return
        
    provider = context.args[0].lower()
    key = context.args[1]
    
    if provider not in PROVIDERS:
        await update.message.reply_text(f"❌ Неизвестный провайдер. Доступные: {', '.join(PROVIDERS)}")
        return
        
    user["api_keys"][provider] = key
    await storage.save()
    
    # Скрываем ключ в чате, если возможно (сообщение лучше удалить)
    try:
        await update.message.delete()
        await update.message.reply_text(f"✅ Ключ для {provider} успешно сохранен. Ваше сообщение с ключом удалено для безопасности.")
    except Exception:
        await update.message.reply_text(f"✅ Ключ для {provider} успешно сохранен. Внимание: удаляйте свои ключи из чата для безопасности!")

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    user["stats"]["msgs"] += 1
    
    if not context.args:
        await update.message.reply_text("❓ Задайте вопрос: /ai [текст]")
        return
        
    prompt = " ".join(context.args)
    
    msg = await update.message.reply_text("⏳ Генерирую ответ...")
    
    # Добавляем контекст из памяти
    system_prompt = "Ты AI ассистент. "
    if user.get("memory"):
        system_prompt += "У тебя есть доступ к памяти пользователя:\n"
        for k, v in user["memory"].items():
            system_prompt += f"- {k}: {v}\n"
            
    response = await ai_handler.generate_response(user_id, prompt, system_prompt=system_prompt)
    
    # Защита от длинных сообщений
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
        await msg.delete()
    else:
        await msg.edit_text(response)
        
    await storage.save()

async def memorysave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /memorysave [ключ] [значение]")
        return
        
    key = context.args[0]
    value = " ".join(context.args[1:])
    
    user["memory"][key] = value
    await storage.save()
    await update.message.reply_text(f"✅ В память сохранено: {key} = {value}")

async def memoryget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        await update.message.reply_text("Использование: /memoryget [ключ]")
        return
        
    key = context.args[0]
    value = user["memory"].get(key)
    
    if value:
        await update.message.reply_text(f"🧠 Память ({key}):\n{value}")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти.")

async def memorylist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not user["memory"]:
        await update.message.reply_text("📭 Ваша память пуста.")
        return
        
    text = "🧠 <b>Ваша память:</b>\n\n"
    for k, v in user["memory"].items():
        text += f"• <b>{k}</b>: {v}\n"
        
    await update.message.reply_text(text, parse_mode="HTML")

async def memorydel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        await update.message.reply_text("Использование: /memorydel [ключ]")
        return
        
    key = context.args[0]
    
    if key in user["memory"]:
        del user["memory"][key]
        await storage.save()
        await update.message.reply_text(f"🗑 Ключ '{key}' удален из памяти.")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден.")
