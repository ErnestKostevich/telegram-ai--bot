from telegram import Update
from telegram.ext import ContextTypes
import base64, html, io, aiohttp
from bot.ai import ai_handler, VISION_PROVIDERS
from bot.storage import storage
from bot.i18n import t
from bot.handlers.vip_creator import check_vip


# TTS voice characters supported by OpenAI's tts-1
TTS_VOICES = ("alloy", "echo", "fable", "onyx", "nova", "shimmer")
TTS_MAX_CHARS = 4000  # OpenAI hard limit is 4096


async def tts_speak(api_key: str, text: str, voice: str = "alloy") -> bytes:
    """Synthesize speech via OpenAI TTS. Returns OGG/opus bytes Telegram accepts."""
    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "tts-1",
        "voice": voice if voice in TTS_VOICES else "alloy",
        "input": text[:TTS_MAX_CHARS],
        "response_format": "opus",  # Telegram's native voice format
    }
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"TTS HTTP {resp.status}: {body[:300]}")
            return await resp.read()


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/voice on|off|<voice_name> — toggle TTS voice replies."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    if not context.args:
        cur = user.get("voice_reply", False)
        v = user.get("voice_name", "alloy")
        await update.message.reply_text(
            t(lang, "voice_status",
              status="ON ✅" if cur else "OFF ❌",
              voice=v,
              voices=", ".join(TTS_VOICES)),
            parse_mode="HTML",
        )
        return

    arg = context.args[0].lower()
    if arg in ("on", "вкл"):
        if not user.get("api_keys", {}).get("openai"):
            await update.message.reply_text(t(lang, "tts_needs_openai"), parse_mode="HTML")
            return
        user["voice_reply"] = True
        await storage.save()
        await update.message.reply_text(t(lang, "voice_on"))
    elif arg in ("off", "выкл"):
        user["voice_reply"] = False
        await storage.save()
        await update.message.reply_text(t(lang, "voice_off"))
    elif arg in TTS_VOICES:
        user["voice_name"] = arg
        await storage.save()
        await update.message.reply_text(t(lang, "voice_picked", voice=arg))
    else:
        await update.message.reply_text(t(lang, "voice_bad_arg", voices=", ".join(TTS_VOICES)))


async def maybe_speak_response(context, chat_id: int, user: dict, text: str):
    """If user has voice_reply enabled and we're in private chat, synthesize and send."""
    if not user.get("voice_reply"):
        return
    api_key = user.get("api_keys", {}).get("openai")
    if not api_key:
        return  # disabled silently if key was removed since toggle
    # Telegram voice messages max ~50MB but TTS is bounded anyway
    if not text or len(text.strip()) < 2 or text.startswith("❌"):
        return
    try:
        audio = await tts_speak(api_key, text, voice=user.get("voice_name", "alloy"))
        bio = io.BytesIO(audio)
        bio.name = "voice.ogg"
        await context.bot.send_voice(chat_id=chat_id, voice=bio)
    except Exception:
        # Voice is a nice-to-have; never fail the whole reply if TTS hiccups
        pass


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Image-to-image edit. Usage:
      - Send a photo with caption: /edit <prompt>
      - Reply to a photo with: /edit <prompt>"""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    from bot.handlers.payments import tier_active, consume_image_credit

    if not tier_active(user, "pro"):
        await update.message.reply_text(t(lang, "edit_pro_only"), parse_mode="HTML")
        return

    # Find the photo to edit: either the message itself or its reply target
    msg = update.message
    photo_msg = None
    if msg.photo:
        photo_msg = msg
    elif msg.reply_to_message and msg.reply_to_message.photo:
        photo_msg = msg.reply_to_message
    else:
        await msg.reply_text(t(lang, "edit_usage"), parse_mode="HTML")
        return

    prompt = " ".join(context.args).strip()
    if not prompt:
        # Try caption-without-command
        cap = (msg.caption or "").strip()
        if cap.lower().startswith("/edit"):
            prompt = cap[5:].strip()
    if not prompt:
        await msg.reply_text(t(lang, "edit_usage"), parse_mode="HTML")
        return

    openai_key = user.get("api_keys", {}).get("openai")
    if not openai_key:
        await msg.reply_text(t(lang, "edit_needs_openai"), parse_mode="HTML")
        return

    if not consume_image_credit(user):
        await msg.reply_text(t(lang, "gen_no_credits"), parse_mode="HTML")
        return
    await storage.save()

    placeholder = await msg.reply_text(t(lang, "edit_working"))

    try:
        # Download the source photo
        photo = photo_msg.photo[-1]
        tg_file = await context.bot.get_file(photo.file_id)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(tg_file.file_path) as r:
                img_bytes = await r.read()

        # OpenAI image edit API (gpt-image-1)
        url = "https://api.openai.com/v1/images/edits"
        form = aiohttp.FormData()
        form.add_field("model", "gpt-image-1")
        form.add_field("prompt", prompt[:1000])
        form.add_field("size", "1024x1024")
        form.add_field("image", img_bytes, filename="src.png", content_type="image/png")
        headers = {"Authorization": f"Bearer {openai_key}"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
            async with s.post(url, headers=headers, data=form) as resp:
                data = await resp.json()
                if resp.status != 200 or "data" not in data:
                    err = data.get("error", {}).get("message") or f"HTTP {resp.status}"
                    raise RuntimeError(err)
                b64 = data["data"][0].get("b64_json")
                if not b64:
                    # Some responses give url instead
                    img_url = data["data"][0].get("url")
                    if not img_url:
                        raise RuntimeError("no image data returned")
                    async with aiohttp.ClientSession(timeout=timeout) as s2:
                        async with s2.get(img_url) as r2:
                            out_bytes = await r2.read()
                else:
                    out_bytes = base64.b64decode(b64)

        await msg.reply_photo(photo=out_bytes,
                               caption=f"🎨 <i>{html.escape(prompt[:200])}</i>",
                               parse_mode="HTML")
        try:
            await placeholder.delete()
        except Exception:
            pass
    except Exception as e:
        try:
            await placeholder.edit_text(t(lang, "edit_error", err=html.escape(str(e))[:200]),
                                          parse_mode="HTML")
        except Exception:
            pass


async def _transcribe_voice_openai(api_key: str, ogg_bytes: bytes) -> str:
    """Transcribe a Telegram voice (.ogg/opus) via OpenAI Whisper."""
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    form = aiohttp.FormData()
    form.add_field("file", ogg_bytes, filename="voice.ogg", content_type="audio/ogg")
    form.add_field("model", "whisper-1")
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, data=form) as resp:
            data = await resp.json()
            if "error" in data:
                raise Exception(data["error"].get("message", str(data["error"])))
            return data.get("text", "").strip()


async def voice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Voice/audio → Whisper transcription → AI response."""
    msg = update.message
    if not msg or update.effective_chat.type != "private":
        return
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    api_key = user.get("api_keys", {}).get("openai")
    if not api_key:
        await msg.reply_text(t(lang, "voice_needs_openai"), parse_mode="HTML")
        return

    voice = msg.voice or msg.audio
    if not voice:
        return
    if voice.file_size and voice.file_size > 20_000_000:
        await msg.reply_text(t(lang, "voice_too_big"))
        return

    status = await msg.reply_text(t(lang, "voice_transcribing"))
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(tg_file.file_path) as r:
                raw = await r.read()
        text = await _transcribe_voice_openai(api_key, raw)
        if not text:
            await status.edit_text(t(lang, "voice_empty"))
            return
        await status.edit_text(t(lang, "voice_got", text=text[:300]))

        # Now send through the regular AI pipeline (streaming!)
        from bot.handlers.ai_memory import _build_system_prompt, _stream_to_message
        user["stats"]["msgs"] = user["stats"].get("msgs", 0) + 1
        await _stream_to_message(update, context, text, _build_system_prompt(user), lang)
        await storage.save()
    except Exception as e:
        try:
            await status.edit_text(f"❌ {e}")
        except Exception:
            pass


async def _download_photo_b64(context, file_id: str) -> tuple[str, str]:
    """Download Telegram photo and return (base64, mime)."""
    tg_file = await context.bot.get_file(file_id)
    file_url = tg_file.file_path
    # 30s timeout: a slow CDN must not be able to hang the handler forever
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(file_url) as resp:
            content = await resp.read()
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
            # If file_size is None (rare) we still refuse oversized uploads at read-time
            if doc.file_size and doc.file_size > 200_000:
                await update.message.reply_text(t(lang, "doc_too_big"))
                return
            msg = await update.message.reply_text(t(lang, "doc_reading"))
            try:
                tg_file = await context.bot.get_file(doc.file_id)
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(tg_file.file_path) as r:
                        raw = await r.read()
                # Defensive cap if file_size was missing
                if len(raw) > 200_000:
                    await msg.edit_text(t(lang, "doc_too_big"))
                    return
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
    # Pro tier required for image generation
    from bot.handlers.payments import tier_active, consume_image_credit
    if not tier_active(user, "pro"):
        await update.message.reply_text(t(lang, "gen_pro_only"), parse_mode="HTML")
        return
    if not context.args:
        await update.message.reply_text(t(lang, "gen_usage"))
        return
    # Try to spend a credit before calling the paid endpoint
    if not consume_image_credit(user):
        await update.message.reply_text(t(lang, "gen_no_credits"), parse_mode="HTML")
        return
    from bot.storage import storage as _st
    await _st.save()
    prompt = " ".join(context.args)
    keys = user.get("api_keys", {})
    provider = user.get("ai_provider", "openai")
    msg = await update.message.reply_text(
        t(lang, "gen_drawing") + f"\n<i>💎 {user.get('image_credits', 0)} credits left</i>",
        parse_mode="HTML",
    )
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
