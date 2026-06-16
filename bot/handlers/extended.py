import datetime
import random
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler
from bot.i18n import t


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "en")

    today = datetime.date.today().isoformat()
    last = user.get("daily_last")
    if last == today:
        msgs = {
            "ru": "🎁 Вы уже забрали награду сегодня! Возвращайтесь завтра.",
            "en": "🎁 You already claimed today's reward! Come back tomorrow.",
            "it": "🎁 Hai già preso il premio oggi! Torna domani.",
        }
        await update.message.reply_text(msgs.get(lang, msgs["en"]))
        return

    streak = user.get("daily_streak", 0)
    # Streak is preserved only if last claim was yesterday
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    streak = streak + 1 if last == yesterday else 1
    bonus_xp = 50 + (streak - 1) * 10  # +10 per consecutive day
    bonus_xp = min(bonus_xp, 200)

    user["daily_last"] = today
    user["daily_streak"] = streak
    user["stats"]["commands"] = user["stats"].get("commands", 0) + bonus_xp // 10
    await storage.save()

    texts = {
        "ru": f"🎁 <b>Награда дня:</b> +{bonus_xp} XP\n🔥 Серия: <b>{streak}</b> дн.",
        "en": f"🎁 <b>Daily reward:</b> +{bonus_xp} XP\n🔥 Streak: <b>{streak}</b> days",
        "it": f"🎁 <b>Premio giornaliero:</b> +{bonus_xp} XP\n🔥 Serie: <b>{streak}</b> giorni",
    }
    await update.message.reply_text(texts.get(lang, texts["en"]), parse_mode="HTML")


async def rep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "en")
    if not update.message.reply_to_message:
        texts = {"ru": "❌ Ответьте на сообщение пользователя.", "en": "❌ Reply to a user's message.", "it": "❌ Rispondi al messaggio di un utente."}
        await update.message.reply_text(texts.get(lang, texts["en"]))
        return
    target_user = update.message.reply_to_message.from_user
    if target_user.is_bot or target_user.id == update.effective_user.id:
        msgs = {"ru": "❌ Нельзя поднять репутацию себе или боту.", "en": "❌ Cannot give rep to yourself or a bot.", "it": "❌ Non puoi dare rep a te stesso o a un bot."}
        await update.message.reply_text(msgs.get(lang, msgs["en"]))
        return
    target = storage.get_user(target_user.id)
    target["reputation"] = target.get("reputation", 0) + 1
    await storage.save()
    texts = {
        "ru": f"📈 Репутация <b>{target_user.first_name}</b>: <b>{target['reputation']}</b>",
        "en": f"📈 <b>{target_user.first_name}</b>'s rep: <b>{target['reputation']}</b>",
        "it": f"📈 Rep di <b>{target_user.first_name}</b>: <b>{target['reputation']}</b>",
    }
    await update.message.reply_text(texts.get(lang, texts["en"]), parse_mode="HTML")


async def roast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "en")
    if not update.message.reply_to_message:
        texts = {"ru": "❌ Ответьте на сообщение.", "en": "❌ Reply to a message.", "it": "❌ Rispondi a un messaggio."}
        await update.message.reply_text(texts.get(lang, texts["en"]))
        return
    target = update.message.reply_to_message.from_user.first_name
    try:
        response = await ai_handler.generate_response(
            uid,
            f"Give a witty, friendly, totally harmless roast of someone named {target}. 1-2 short sentences, light humor, no offensive content. Reply in the user's language.",
            system_prompt="You generate light, friendly comedy roasts. Never offensive, never personal attacks.",
            use_history=False,
        )
        if response.startswith("❌"):
            raise RuntimeError(response)
        await update.message.reply_text(f"🔥 {response}")
    except Exception:
        fallbacks = {
            "ru": [
                f"{target}, твой код как абстрактное искусство — никто не понимает, но все притворяются. 🎨",
                f"{target}, ты как Wi-Fi в кафе — все хотят тебя, но никто не помнит пароль. 📶",
            ],
            "en": [
                f"{target}, your code is like abstract art — no one gets it, but everyone pretends. 🎨",
                f"{target}, you're like café Wi-Fi — everyone wants you, no one remembers the password. 📶",
            ],
            "it": [
                f"{target}, il tuo codice è come l'arte astratta — nessuno lo capisce, ma tutti fingono. 🎨",
                f"{target}, sei come il Wi-Fi del bar — tutti ti vogliono, nessuno ricorda la password. 📶",
            ],
        }
        await update.message.reply_text(random.choice(fallbacks.get(lang, fallbacks["en"])))
