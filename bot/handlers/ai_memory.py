import asyncio
import html
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler, PROVIDERS, STREAMING_PROVIDERS
from bot.i18n import t


def _action_buttons(lang: str) -> InlineKeyboardMarkup:
    """Inline keyboard attached under a finished AI response."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "btn_regen"), callback_data="ai_regen"),
        InlineKeyboardButton(t(lang, "btn_save_note"), callback_data="ai_save_note"),
    ]])

# Per-user cap on long-term memory entries to keep system-prompt size sane
MAX_MEMORY_ENTRIES = 50
MAX_MEMORY_KEY_LEN = 100
MAX_MEMORY_VALUE_LEN = 1000
# Cap memory entries injected into AI system prompts
MEMORY_SYSTEM_PROMPT_CAP = 30

# Streaming: re-edit Telegram message at most every N seconds.
# Telegram allows ~30 edits/min per chat → 2s is the safe floor; 1.5s gives
# us margin while still feeling live.
STREAM_EDIT_INTERVAL = 1.5
# Stop streaming-edit if accumulated text exceeds this; switch to send_new_chunks
STREAM_MAX_EDIT_LEN = 3800


async def _typing(context, chat_id):
    """Fire-and-forget typing indicator; failure is silent (user may have blocked the bot)."""
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass


async def _stream_to_message(update, context, prompt, system_prompt, lang):
    """Run a streaming AI response and update the Telegram message live.
    Returns the final accumulated text. Also stores last_ai_turn on the user
    and attaches action buttons (regenerate / save as note)."""
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    user = storage.get_user(uid)
    provider = user.get("ai_provider", "gemini")
    is_private = update.effective_chat.type == "private"

    await _typing(context, chat_id)
    placeholder = await update.message.reply_text(t(lang, "ai_thinking"))

    # If the provider can't stream, do the old single-shot path
    if provider not in STREAMING_PROVIDERS:
        response = await ai_handler.generate_response(uid, prompt, system_prompt=system_prompt)
        if response.startswith("❌"):
            await placeholder.edit_text(response, parse_mode="HTML")
        elif len(response) > 3800:
            await placeholder.delete()
            await _send_long(update.message, response)
        else:
            kb = _action_buttons(lang) if is_private else None
            await placeholder.edit_text(response, disable_web_page_preview=True, reply_markup=kb)
            user["last_ai_turn"] = {"prompt": prompt[:2000], "response": response[:3800],
                                     "system_prompt": (system_prompt or "")[:1500]}
            await storage.save()
        return response

    acc = ""
    last_edit = 0.0
    last_text = ""
    error_text = None

    try:
        async for chunk in ai_handler.stream_response(uid, prompt, system_prompt=system_prompt):
            if chunk.startswith("❌"):
                error_text = chunk
                break
            acc += chunk
            now = time.monotonic()
            if now - last_edit < STREAM_EDIT_INTERVAL:
                continue
            if len(acc) > STREAM_MAX_EDIT_LEN:
                # Too long to keep editing — finalize current placeholder and break to chunked send
                break
            preview = (acc + " ▌").strip()
            if preview == last_text or not preview:
                continue
            try:
                await placeholder.edit_text(preview, disable_web_page_preview=True)
                last_text = preview
                last_edit = now
                # Refresh typing indicator periodically
                await _typing(context, chat_id)
            except BadRequest:
                # Telegram says "message not modified" or rate-limit; ignore and continue
                continue
            except Exception:
                continue
    except Exception as e:
        error_text = f"❌ {e}"

    final = error_text or acc.strip()
    if not final:
        final = "…"

    try:
        if len(final) <= 3800:
            kb = _action_buttons(lang) if (is_private and not error_text) else None
            # Always do a final edit (without cursor, with buttons if applicable)
            try:
                await placeholder.edit_text(
                    final,
                    parse_mode="HTML" if error_text else None,
                    disable_web_page_preview=True,
                    reply_markup=kb,
                )
            except BadRequest:
                pass
        else:
            try:
                await placeholder.delete()
            except Exception:
                pass
            await _send_long(update.message, final)
    except Exception:
        pass

    if not error_text:
        ai_handler.push_history(uid, prompt, acc)
        # Award weekly XP for a successful AI turn (small reward, builds streak feel)
        try:
            from bot.handlers.base import award_weekly_xp
            award_weekly_xp(user, 5)
        except Exception:
            pass
        # Stash the turn so action buttons can act on it.
        if is_private:
            user["last_ai_turn"] = {"prompt": prompt[:2000], "response": acc[:3800],
                                     "system_prompt": (system_prompt or "")[:1500]}
            try:
                await storage.save()
            except Exception:
                pass
            # Voice reply if user enabled it
            try:
                from bot.handlers.media import maybe_speak_response
                await maybe_speak_response(context, chat_id, user, acc)
            except Exception:
                pass
            # Proactive memory: occasionally offer to save stable facts
            try:
                from bot.handlers.proactive import maybe_suggest_memory
                # Fire-and-forget — never blocks the reply
                asyncio.create_task(maybe_suggest_memory(context, chat_id, user))
            except Exception:
                pass
    return final


def _build_system_prompt(user: dict, base: str = "", group: dict | None = None) -> str:
    lang = user.get("language", "ru")
    lang_names = {"ru": "Russian", "en": "English", "it": "Italian"}
    sp = base or "You are AI DISCO BOT — a helpful, friendly AI assistant inside Telegram. "
    sp += f"Respond in {lang_names.get(lang, 'English')} unless asked otherwise. "
    sp += "Be concise and clear. Use simple line breaks instead of complex markdown. "
    if user.get("disco_mode"):
        sp += "Style: playful, witty, use emojis and humor moderately. "
    # Persona overlay
    try:
        from bot.handlers.wow import get_persona_addon
        persona = get_persona_addon(user)
        if persona:
            sp += persona + " "
    except Exception:
        pass
    memory = user.get("memory") or {}
    if memory:
        sp += "User's saved memory:\n"
        for k, v in list(memory.items())[:MEMORY_SYSTEM_PROMPT_CAP]:
            sp += f"- {k}: {v}\n"
    # Group shared memory (only present when called from group context)
    if group:
        try:
            from bot.handlers.groups import _build_group_memory_block
            gmem = _build_group_memory_block(group)
            if gmem:
                sp += gmem
        except Exception:
            pass
    return sp


async def _send_long(message, text: str):
    text = (text or "").strip() or "…"
    # Telegram max ~4096; chunk by 3800 to be safe
    if len(text) <= 3800:
        await message.reply_text(text, disable_web_page_preview=True)
        return
    for i in range(0, len(text), 3800):
        await message.reply_text(text[i:i+3800], disable_web_page_preview=True)


async def setprovider_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        # No args → show inline picker buttons (huge UX improvement vs. plain text)
        from bot.keyboards import get_provider_picker_keyboard
        await update.message.reply_text(
            t(lang, "provider_pick"),
            parse_mode="HTML",
            reply_markup=get_provider_picker_keyboard(lang, current=user.get("ai_provider", "gemini"), action_prefix="setprov"),
        )
        return
    provider = context.args[0].lower()
    if provider not in PROVIDERS:
        await update.message.reply_text(t(lang, "provider_unknown", list=', '.join(PROVIDERS)))
        return
    user["ai_provider"] = provider
    await storage.save()
    await update.message.reply_text(t(lang, "provider_set", provider=provider), parse_mode="HTML")


async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    # SECURITY: in groups we MUST scrub the message first. If we successfully
    # delete it the key is safe to save and we confirm via DM. If we couldn't
    # delete (bot isn't admin) we refuse and tell the user to use a private chat.
    if update.effective_chat.type != "private":
        deleted_ok = False
        try:
            await update.message.delete()
            deleted_ok = True
        except Exception:
            pass

        if deleted_ok and len(context.args) >= 2:
            provider = context.args[0].lower()
            key = context.args[1]
            if provider in PROVIDERS:
                user["api_keys"][provider] = key
                await storage.save()
                # The original message is gone — try to DM the user privately
                try:
                    await context.bot.send_message(
                        uid,
                        t(lang, "key_saved_dm", provider=provider),
                        parse_mode="HTML",
                    )
                    return
                except Exception:
                    # User hasn't started a private chat with the bot yet.
                    # Post a generic confirmation in the group (no key contents).
                    try:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=t(lang, "key_saved_no_dm", provider=provider),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    return

        # Either delete failed (key still visible) or args were missing.
        # Refuse loudly via a normal send_message — reply_text would target
        # the now-deleted message.
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t(lang, "key_group_refuse"),
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(uid, t(lang, "key_group_dm_hint"), parse_mode="HTML")
        except Exception:
            pass
        return

    if len(context.args) < 2:
        # No args → start the 2-step button flow
        from bot.keyboards import get_provider_picker_keyboard
        await update.message.reply_text(
            t(lang, "key_pick_provider"),
            parse_mode="HTML",
            reply_markup=get_provider_picker_keyboard(lang, action_prefix="keyfor"),
        )
        return
    provider = context.args[0].lower()
    key = context.args[1]
    if provider not in PROVIDERS:
        await update.message.reply_text(t(lang, "provider_unknown", list=', '.join(PROVIDERS)))
        return
    user["api_keys"][provider] = key
    await storage.save()
    try:
        await update.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t(lang, "key_saved", provider=provider),
        parse_mode="HTML",
    )


async def setmodel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        # No args → show model picker buttons for current provider
        from bot.ai import PROVIDER_MODELS, DEFAULT_MODELS
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        provider = user.get("ai_provider", "gemini")
        models = PROVIDER_MODELS.get(provider, [])
        current = user.get("ai_model") or DEFAULT_MODELS.get(provider, "default")
        if not models:
            await update.message.reply_text(
                t(lang, "model_usage", current=current),
                parse_mode="HTML",
            )
            return
        kb = []
        for m in models:
            label = f"✅ {m}" if m == current else m
            display = label if len(label) <= 40 else label[:37] + "…"
            kb.append([InlineKeyboardButton(display, callback_data=f"setmodel_{m}")])
        kb.append([InlineKeyboardButton(t(lang, "ik_back"), callback_data="back_settings")])
        await update.message.reply_text(
            f"🧠 <b>Model</b> ({provider})\n\n<i>Current: {current}</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return
    model = " ".join(context.args)
    user["ai_model"] = model
    await storage.save()
    await update.message.reply_text(t(lang, "model_set", model=model), parse_mode="HTML")


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    user["stats"]["commands"] = user["stats"].get("commands", 0) + 1
    user["stats"]["msgs"] = user["stats"].get("msgs", 0) + 1
    if not context.args:
        await update.message.reply_text(t(lang, "ai_no_query"))
        return
    prompt = " ".join(context.args)
    await _stream_to_message(update, context, prompt, _build_system_prompt(user), lang)
    await storage.save()


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    had = len(user.get("chat_history", []))
    ai_handler.clear_history(uid)
    await storage.save()
    await update.message.reply_text(t(lang, "ai_cleared", count=had // 2))


async def memorysave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if len(context.args) < 2:
        await update.message.reply_text(t(lang, "mem_usage"))
        return
    key = context.args[0][:MAX_MEMORY_KEY_LEN]
    value = " ".join(context.args[1:])[:MAX_MEMORY_VALUE_LEN]
    memory = user.setdefault("memory", {})
    # If adding a new key would exceed cap, refuse
    if key not in memory and len(memory) >= MAX_MEMORY_ENTRIES:
        await update.message.reply_text(t(lang, "mem_full", max=MAX_MEMORY_ENTRIES))
        return
    memory[key] = value
    await storage.save()
    await update.message.reply_text(t(lang, "mem_saved", key=html.escape(key), value=html.escape(value)))


async def memoryget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "mem_usage"))
        return
    key = context.args[0]
    value = user["memory"].get(key)
    if value:
        await update.message.reply_text(t(lang, "mem_value", key=html.escape(key), value=html.escape(value)))
    else:
        await update.message.reply_text(t(lang, "mem_not_found", key=html.escape(key)))


async def memorylist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not user["memory"]:
        await update.message.reply_text(t(lang, "mem_empty"))
        return
    text = t(lang, "mem_title")
    # Escape so any < or & in keys/values doesn't crash HTML parser
    for k, v in user["memory"].items():
        text += f"• <b>{html.escape(k)}</b>: {html.escape(v)}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def memorydel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "mem_del_usage"))
        return
    key = context.args[0]
    if key in user["memory"]:
        del user["memory"][key]
        await storage.save()
        await update.message.reply_text(t(lang, "mem_deleted", key=html.escape(key)))
    else:
        await update.message.reply_text(t(lang, "mem_not_found", key=html.escape(key)))
