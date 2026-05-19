from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t
import datetime, pytz, random, string, aiohttp
from urllib.parse import quote


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "time_usage"))
        return
    city = " ".join(context.args)
    needle = city.lower().replace(" ", "_")
    tz_name = None
    # Prefer exact end-match (e.g. Europe/Rome) over substring
    for tz in pytz.all_timezones:
        if tz.lower().endswith("/" + needle):
            tz_name = tz
            break
    if not tz_name:
        for tz in pytz.all_timezones:
            if needle in tz.lower():
                tz_name = tz
                break
    if tz_name:
        now = datetime.datetime.now(pytz.timezone(tz_name))
        await update.message.reply_text(
            f"⏰ <b>{city}</b>\n\n🕐 {now.strftime('%H:%M:%S')}\n📅 {now.strftime('%Y-%m-%d')}\n🌍 {tz_name}",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(t(lang, "time_not_found"))


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "weather_usage"))
        return
    city = " ".join(context.args)
    headers = {"User-Agent": "ai-disco-bot"}
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as session:
            url = f"https://wttr.in/{quote(city)}?format=%t|%f|%C|%h|%w&lang={lang}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = (await resp.text()).strip()
                    parts = data.split("|")
                    if len(parts) == 5 and "Unknown" not in data:
                        temp, feels, desc, hum, wind = parts
                        await update.message.reply_text(
                            f"🌍 <b>{city}</b>\n\n🌡 {temp}\n🤔 {feels}\n☁️ {desc}\n💧 {hum}\n💨 {wind}",
                            parse_mode="HTML",
                        )
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
    if len(expr) > 200:
        await update.message.reply_text(t(lang, "calc_error"))
        return
    allowed = "0123456789+-*/(). %"
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
    length = 16
    if context.args:
        try:
            length = int(context.args[0])
            if length < 8 or length > 64:
                await update.message.reply_text(t(lang, "pwd_error"))
                return
        except ValueError:
            await update.message.reply_text(t(lang, "pwd_error"))
            return
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(t(lang, "pwd_result", pwd=pwd), parse_mode="HTML")
