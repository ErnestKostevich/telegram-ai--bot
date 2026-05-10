from telegram import Update
from telegram.ext import ContextTypes
import datetime
import pytz
import random
import string
import aiohttp

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /time [город]\nПример: /time Moscow")
        return
        
    city = " ".join(context.args)
    # Simple mockup for timezone search. In real app, we'd use geopy or a timezone library properly.
    # For this rewrite, we'll try to find a matching timezone.
    tz_name = None
    for tz in pytz.all_timezones:
        if city.lower() in tz.lower():
            tz_name = tz
            break
            
    if tz_name:
        timezone = pytz.timezone(tz_name)
        now = datetime.datetime.now(timezone)
        await update.message.reply_text(f"⏰ <b>{city}</b>\n\n🕐 Время: {now.strftime('%H:%M:%S')}\n📅 Дата: {now.strftime('%Y-%m-%d')}\n🌍 Пояс: {tz_name}", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Часовой пояс для '{city}' не найден.")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /weather [город]")
        return
        
    city = " ".join(context.args)
    # For now, without OPENWEATHER_API_KEY, we'll provide a mock or simple response, 
    # since we moved away from hardcoded keys. Or we can use a free public API with no key.
    try:
        async with aiohttp.ClientSession() as session:
            # wttr.in is a free public weather API
            url = f"https://wttr.in/{city}?format=%t|%f|%C|%h|%w"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.text()
                    parts = data.strip().split('|')
                    if len(parts) == 5:
                        temp, feels, desc, hum, wind = parts
                        await update.message.reply_text(
                            f"🌍 <b>Погода в {city}:</b>\n\n"
                            f"🌡 Температура: {temp}\n"
                            f"🤔 Ощущается как: {feels}\n"
                            f"☁️ {desc}\n"
                            f"💧 Влажность: {hum}\n"
                            f"💨 Ветер: {wind}",
                            parse_mode="HTML"
                        )
                        return
    except Exception:
        pass
        
    await update.message.reply_text("❌ Ошибка получения погоды. Попробуйте другой город.")

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /calc [выражение]")
        return
        
    expr = "".join(context.args)
    allowed = "0123456789+-*/(). "
    if not all(c in allowed for c in expr):
        await update.message.reply_text("❌ Разрешены только числа и базовые операторы (+ - * /).")
        return
        
    try:
        # safe eval with no builtins
        result = eval(expr, {"__builtins__": {}})
        await update.message.reply_text(f"🧮 <b>Результат:</b>\n\n{expr} = <b>{result}</b>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ Ошибка вычисления.")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    length = 12
    if context.args:
        try:
            length = int(context.args[0])
            if length < 8 or length > 50:
                await update.message.reply_text("❌ Длина пароля должна быть от 8 до 50.")
                return
        except ValueError:
            await update.message.reply_text("❌ Укажите число.")
            return
            
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(f"🔑 <b>Ваш пароль:</b>\n\n<code>{pwd}</code>", parse_mode="HTML")
