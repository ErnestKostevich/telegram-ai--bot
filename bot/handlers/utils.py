from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t
import datetime, pytz, random, string, aiohttp

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "time_usage"))
        return
    city = " ".join(context.args)
    tz_name = None
    for tz in pytz.all_timezones:
        if city.lower() in tz.lower():
            tz_name = tz
            break
    if tz_name:
        now = datetime.datetime.now(pytz.timezone(tz_name))
        await update.message.reply_text(f"⏰ <b>{city}</b>\n\n🕐 {now.strftime('%H:%M:%S')}\n📅 {now.strftime('%Y-%m-%d')}\n🌍 {tz_name}", parse_mode="HTML")
    else:
        await update.message.reply_text(t(lang, "time_not_found"))

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "weather_usage"))
        return
    city = " ".join(context.args)
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?format=%t|%f|%C|%h|%w"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.text()
                    parts = data.strip().split('|')
                    if len(parts) == 5:
                        temp, feels, desc, hum, wind = parts
                        await update.message.reply_text(f"🌍 <b>{city}</b>\n\n🌡 {temp}\n🤔 {feels}\n☁️ {desc}\n💧 {hum}\n💨 {wind}", parse_mode="HTML")
                        return
    except Exception:
        pass
    await update.message.reply_text(t(lang, "weather_error"))

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "calc_usage"))
        return
    expr = "".join(context.args)
    allowed = "0123456789+-*/(). "
    if not all(c in allowed for c in expr):
        await update.message.reply_text(t(lang, "calc_error"))
        return
    try:
        result = eval(expr, {"__builtins__": {}})
        await update.message.reply_text(t(lang, "calc_result", expr=expr, result=result), parse_mode="HTML")
    except Exception:
        await update.message.reply_text(t(lang, "calc_error"))

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    length = 12
    if context.args:
        try:
            length = int(context.args[0])
            if length < 8 or length > 50:
                await update.message.reply_text(t(lang, "pwd_error"))
                return
        except ValueError:
            await update.message.reply_text(t(lang, "pwd_error"))
            return
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(t(lang, "pwd_result", pwd=pwd), parse_mode="HTML")
