from telegram import Update
from telegram.ext import ContextTypes
import random
import aiohttp

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice(emoji="🎲")

async def coinflip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["Орёл 🦅", "Решка 🪙"])
    await update.message.reply_text(f"Вы подбросили монетку...\n\nВыпало: <b>{result}</b>", parse_mode="HTML")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /random [от] [до]\nПример: /random 1 100")
        return
    try:
        min_val = int(context.args[0])
        max_val = int(context.args[1])
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        result = random.randint(min_val, max_val)
        await update.message.reply_text(f"🎲 Случайное число от {min_val} до {max_val}:\n\n<b>{result}</b>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, укажите числа.")

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Почему программисты не любят природу? Потому что там слишком много багов.",
        "Заходит тестировщик в бар. Забегает в бар. Пролезает в бар. Танцуя, проникает в бар. Крадется в бар. И заказывает: кружку пива, 2 кружки пива, 0 кружек пива, 999999999 кружек пива, ящерицу в стакане, -1 кружку пива.",
        "Оптимист видит стакан наполовину полным, пессимист — наполовину пустым, а программист — что стакан в два раза больше, чем нужно."
    ]
    await update.message.reply_text(f"😄 {random.choice(jokes)}")
