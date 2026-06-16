from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t
import random

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice(emoji="🎲")

async def coinflip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "en")
    result = t(lang, "coinflip_h") if random.randint(0,1) else t(lang, "coinflip_t")
    await update.message.reply_text(t(lang, "coinflip_text", result=result), parse_mode="HTML")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "en")
    if len(context.args) < 2:
        await update.message.reply_text(t(lang, "random_usage"))
        return
    try:
        mn, mx = int(context.args[0]), int(context.args[1])
        if mn > mx: mn, mx = mx, mn
        result = random.randint(mn, mx)
        await update.message.reply_text(t(lang, "random_text", min=mn, max=mx, result=result), parse_mode="HTML")
    except ValueError:
        await update.message.reply_text(t(lang, "random_usage"))

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "en")
    jokes = {
        "ru": [
            "Почему программисты не любят природу? Слишком много багов. 🐛",
            "Оптимист: стакан наполовину полон. Пессимист: наполовину пуст. Программист: стакан в два раза больше, чем нужно. 🥛",
            "— Алло, это служба поддержки? — Да. — У меня не работает интернет. — А как вы нам звоните? — По телефону! 📞",
        ],
        "en": [
            "Why do programmers prefer dark mode? Because light attracts bugs. 🐛",
            "There are 10 types of people: those who understand binary and those who don't. 💻",
            "A SQL query walks into a bar, sees two tables and asks: 'Can I join you?' 🍺",
        ],
        "it": [
            "Perché i programmatori preferiscono il buio? Perché la luce attira i bug. 🐛",
            "Ci sono 10 tipi di persone: chi capisce il binario e chi no. 💻",
            "Un programmatore va al supermercato. La moglie dice: 'Compra il pane, e se ci sono le uova, prendine 6'. Torna con 6 pani. 🍞",
        ]
    }
    await update.message.reply_text(f"😄 {random.choice(jokes.get(lang, jokes['en']))}")
