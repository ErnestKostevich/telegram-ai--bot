from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage

async def grouphelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
👥 <b>Команды для групп:</b>

🛡️ <b>Модерация (требуются права админа):</b>
/warn [reply] — предупреждение
/unwarn [reply] — снять предупреждение
/mute [reply] [минуты] — мут
/unmute [reply] — снять мут
/ban [reply] — бан
/unban [user_id] — разбан
/kick [reply] — кик
/purge [кол-во] — удалить сообщения
/antilink [on/off] — запрет ссылок
/antispam [on/off] — антиспам

🤖 <b>AI для групп:</b>
/ask [вопрос] — AI отвечает в группе
/summary — краткая сводка последних сообщений
/translate [язык] [текст] — перевод

📢 <b>Админ:</b>
/setrules [текст] — установить правила
/rules — показать правила
/welcome [on/off] — включить/выключить приветствие
/goodbye [on/off] — сообщения при выходе

📊 <b>Статистика:</b>
/groupstats — статистика группы
"""
    await update.message.reply_text(help_text, parse_mode="HTML")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Basic ban implementation requiring a reply
    chat = update.effective_chat
    if chat.type == 'private':
        await update.message.reply_text("Эта команда работает только в группах.")
        return
        
    user = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    if user.status not in ['administrator', 'creator']:
        await update.message.reply_text("❌ Нужны права администратора.")
        return
        
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение пользователя, которого нужно забанить.")
        return
        
    target_user = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat.id, target_user.id)
        await update.message.reply_text(f"🚫 Пользователь {target_user.first_name} был забанен.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Like AI, but for groups
    chat = update.effective_chat
    if chat.type == 'private':
        await update.message.reply_text("Для приватных чатов используйте /ai")
        return
        
    from bot.ai import ai_handler
    
    # We use the group owner's key or the requester's key? Requester's key.
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        await update.message.reply_text("❓ Задайте вопрос: /ask [текст]")
        return
        
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("⏳ AI думает...")
    
    response = await ai_handler.generate_response(user_id, prompt)
    
    if len(response) > 4000:
        await msg.edit_text("Ответ слишком длинный. Пожалуйста, конкретизируйте запрос.")
    else:
        await msg.edit_text(response)

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.effective_chat.type == 'private':
        return
        
    group = storage.get_group(chat_id)
    rules = group.get("rules", "")
    
    if rules:
        await update.message.reply_text(f"📜 <b>Правила группы:</b>\n\n{rules}", parse_mode="HTML")
    else:
        await update.message.reply_text("📜 Правила не установлены.")

async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == 'private':
        return
        
    user = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    if user.status not in ['administrator', 'creator']:
        await update.message.reply_text("❌ Нужны права администратора.")
        return
        
    if not context.args:
        await update.message.reply_text("Использование: /setrules [текст правил]")
        return
        
    rules = " ".join(context.args)
    group = storage.get_group(chat.id)
    group["rules"] = rules
    await storage.save()
    
    await update.message.reply_text("✅ Правила успешно установлены!")

async def guardian_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if update.effective_chat.type == "private":
        await update.message.reply_text("Эта команда работает только в группах.")
        return
        
    group = storage.get_group(chat_id)
    if not context.args:
        status = "включен" if group.get("guardian", False) else "выключен"
        await update.message.reply_text(f"🛡️ AI Guardian сейчас {status}.\nИспользование: /guardian [on|off]")
        return
        
    action = context.args[0].lower()
    if action == "on":
        group["guardian"] = True
        await update.message.reply_text("🛡️ AI Guardian успешно ВКЛЮЧЕН! Теперь бот будет следить за порядком и фильтровать спам/токсичность.")
    elif action == "off":
        group["guardian"] = False
        await update.message.reply_text("🛡️ AI Guardian ВЫКЛЮЧЕН.")
        
    await storage.save()
