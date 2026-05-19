from telegram import Update
from telegram.ext import ContextTypes
import base64, aiohttp
from bot.ai import ai_handler, VISION_PROVIDERS
from bot.storage import storage
from bot.i18n import t
from bot.handlers.vip_creator import check_vip


async def _download_photo_b64(context, file_id: str) -> tuple[str, str]:
    """Download Telegram photo and return (base64, mime)."""
    tg_file = await context.bot.get_file(file_id)
    file_url = tg_file.file_path
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            content = await resp.read()
    # Telegram delivers photos as JPEG
    return base64.b64encode(content).decode("utf-8"), "image/jpeg"


async def media_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    # Only handle private chats here; groups would be too noisy
    if update.effective_chat.type != "private":
        return

    if not check_vip(user):
        await update.message.reply_text(t(lang, "gen_vip_only"))
        return

    if update.message.document:
        # Try text extraction
        doc = update.message.document
        if doc.mime_type and (doc.mime_type.startswith("text/") or doc.mime_type in ("application/json", "application/xml")):
            if doc.file_size and doc.file_size > 200_000:
                await update.message.reply_text(t(lang, "doc_too_big"))
                return
            msg = await update.message.reply_text(t(lang, "doc_reading"))
            try:
                tg_file = await context.bot.get_file(doc.file_id)
                async with aiohttp.ClientSession() as s:
                    async with s.get(tg_file.file_path) as r:
                        raw = await r.read()
                text = raw.decode("utf-8", errors="replace")[:12000]
                caption = (update.message.caption or t(lang, "doc_default_prompt")).strip()
                from bot.handlers.ai_memory import _build_system_prompt, _send_long
                response = await ai_handler.generate_response(
                    uid,
                    f"{caption}\n\n--- File content ---\n{text}",
                    system_prompt=_build_system_prompt(user),
                    use_history=False,
                )
                if response.startswith("❌"):
                    await msg.edit_text(response, parse_mode="HTML")
                else:
                    await msg.delete()
                    await _send_long(update.message, response)
            except Exception as e:
                await msg.edit_text(f"❌ {e}")
            return
        else:
            await update.message.reply_text(t(lang, "doc_unsupported"))
            return

    if update.message.photo:
        provider = user.get("ai_provider", "gemini")
        if provider not in VISION_PROVIDERS:
            await update.message.reply_text(t(lang, "vision_unsupported", provider=provider))
            return

        msg = await update.message.reply_text(t(lang, "vision_analyzing"))
        try:
            # Pick the largest photo size
            photo = update.message.photo[-1]
            b64, mime = await _download_photo_b64(context, photo.file_id)
            caption = (update.message.caption or t(lang, "vision_default_prompt")).strip()
            from bot.handlers.ai_memory import _build_system_prompt, _send_long
            response = await ai_handler.generate_response(
                uid,
                caption,
                system_prompt=_build_system_prompt(user),
                use_history=False,
                image_b64=b64,
                image_mime=mime,
            )
            if response.startswith("❌"):
                await msg.edit_text(response, parse_mode="HTML")
            else:
                await msg.delete()
                await _send_long(update.message, response)
        except Exception as e:
            await msg.edit_text(f"❌ {e}")


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not check_vip(user):
        await update.message.reply_text(t(lang, "gen_vip_only"))
        return
    if not context.args:
        await update.message.reply_text(t(lang, "gen_usage"))
        return
    prompt = " ".join(context.args)
    keys = user.get("api_keys", {})
    provider = user.get("ai_provider", "openai")
    msg = await update.message.reply_text(t(lang, "gen_drawing"))
    try:
        if provider == "together" and keys.get("together"):
            url = "https://api.together.xyz/v1/images/generations"
            headers = {"Authorization": f"Bearer {keys['together']}", "Content-Type": "application/json"}
            payload = {"model": "black-forest-labs/FLUX.1-schnell-Free", "prompt": prompt, "n": 1, "steps": 4}
        else:
            use_key = keys.get("openai")
            if not use_key:
                await msg.edit_text(t(lang, "gen_needs_openai"), parse_mode="HTML")
                return
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
                    image_url = data["data"][0].get("url")
                    if image_url and image_url.startswith("http"):
                        await update.message.reply_photo(photo=image_url, caption=f"🎨 {prompt}")
                        await msg.delete()
                    elif data["data"][0].get("b64_json"):
                        img_bytes = base64.b64decode(data["data"][0]["b64_json"])
                        await update.message.reply_photo(photo=img_bytes, caption=f"🎨 {prompt}")
                        await msg.delete()
                    else:
                        await msg.edit_text("❌ No image URL returned.")
                else:
                    await msg.edit_text("❌ No image returned.")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")
