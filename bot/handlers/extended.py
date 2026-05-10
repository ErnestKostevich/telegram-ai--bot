from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler
from bot.i18n import t
import random

async def generic_mock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    cmd = update.message.text.split()[0]
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    texts = {
        "ru": f"✨ <b>{cmd}</b> — эта функция скоро будет доступна! 🚀",
        "en": f"✨ <b>{cmd}</b> — this feature is coming soon! 🚀",
        "it": f"✨ <b>{cmd}</b> — questa funzione sarà presto disponibile! 🚀",
    }
    await update.message.reply_text(texts.get(lang, texts["en"]), parse_mode="HTML")

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    user["stats"]["commands"] = user["stats"].get("commands", 0) + 50
    await storage.save()
    texts = {"ru": "🎁 <b>Ежедневная награда!</b>\n+500 XP!", "en": "🎁 <b>Daily Reward!</b>\n+500 XP!", "it": "🎁 <b>Premio giornaliero!</b>\n+500 XP!"}
    await update.message.reply_text(texts.get(lang, texts["en"]), parse_mode="HTML")

async def rep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        texts = {"ru": "❌ Ответьте на сообщение.", "en": "❌ Reply to a message.", "it": "❌ Rispondi a un messaggio."}
        await update.message.reply_text(texts.get(lang, texts["en"]))
        return
    name = update.message.reply_to_message.from_user.first_name
    texts = {"ru": f"📈 Репутация <b>{name}</b> +1!", "en": f"📈 <b>{name}</b>'s rep +1!", "it": f"📈 Rep di <b>{name}</b> +1!"}
    await update.message.reply_text(texts.get(lang, texts["en"]), parse_mode="HTML")

async def roast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not update.message.reply_to_message:
        texts = {"ru": "❌ Ответьте на сообщение.", "en": "❌ Reply to a message.", "it": "❌ Rispondi a un messaggio."}
        await update.message.reply_text(texts.get(lang, texts["en"]))
        return
    target = update.message.reply_to_message.from_user.first_name
    # Use AI for roast if key is available
    try:
        response = await ai_handler.generate_response(uid, f"Give a funny, friendly roast of someone named {target}. Keep it light, no offensive content. 1-2 sentences max.", system_prompt="You generate friendly comedy roasts. Keep it fun and non-toxic.")
        await update.message.reply_text(f"🔥 {response}")
    except Exception:
        roasts = {"ru": [f"{target}, твой код — произведение искусства... абстрактного! 🎨"], "en": [f"{target}, your code is art... abstract art! 🎨"], "it": [f"{target}, il tuo codice è arte... astratta! 🎨"]}
        await update.message.reply_text(random.choice(roasts.get(lang, roasts["en"])))
