from telegram import Update
from telegram.ext import ContextTypes
import base64, aiohttp
from bot.ai import ai_handler
from bot.storage import storage
from bot.i18n import t

async def media_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not user.get("vip"):
        await update.message.reply_text(t(lang, "gen_vip_only"))
        return
    msg = await update.message.reply_text("🔍 ...")
    try:
        if update.message.photo:
            await msg.edit_text("📸 Vision API — coming in v2.0!")
        elif update.message.document:
            await msg.edit_text("📎 Document analysis — coming in v2.0!")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not user.get("vip"):
        await update.message.reply_text(t(lang, "gen_vip_only"))
        return
    if not context.args:
        await update.message.reply_text(t(lang, "gen_usage"))
        return
    prompt = " ".join(context.args)
    provider = user.get("ai_provider", "openai")
    keys = user.get("api_keys", {})
    key = keys.get(provider) or keys.get("openai")
    if not key:
        await update.message.reply_text(t(lang, "ai_no_key", provider=provider))
        return
    msg = await update.message.reply_text(t(lang, "gen_drawing"))
    try:
        if provider == "together" and keys.get("together"):
            url = "https://api.together.xyz/v1/images/generations"
            headers = {"Authorization": f"Bearer {keys['together']}", "Content-Type": "application/json"}
            payload = {"model": "stabilityai/stable-diffusion-xl-base-1.0", "prompt": prompt, "n": 1, "steps": 20}
        else:
            use_key = keys.get("openai") or key
            url = "https://api.openai.com/v1/images/generations"
            headers = {"Authorization": f"Bearer {use_key}", "Content-Type": "application/json"}
            payload = {"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    await msg.edit_text(f"❌ {err_msg}")
                    return
                if "data" in data and len(data["data"]) > 0:
                    image_url = data["data"][0].get("url") or data["data"][0].get("b64_json")
                    if image_url and image_url.startswith("http"):
                        await update.message.reply_photo(photo=image_url, caption=f"🎨 {prompt}")
                        await msg.delete()
                    else:
                        await msg.edit_text("❌ No image URL returned.")
                else:
                    await msg.edit_text("❌ No image returned.")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")
