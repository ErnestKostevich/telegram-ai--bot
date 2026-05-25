"""Proactive memory: bot occasionally proposes memory entries to save.

After every N user/assistant turns, we ask the AI to look at the recent
chat history and suggest 1-3 stable facts worth remembering long-term
(name, profession, preferences, ongoing projects — NOT one-off
questions). The user sees inline buttons to save each suggestion or
skip the whole batch.

This is what makes the bot feel like it actually knows you, vs ChatGPT
that forgets after every conversation.
"""
import json
import re
import secrets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler
from bot.i18n import t


# Trigger after this many message-pairs since the last suggestion
SUGGEST_AFTER_TURNS = 6
# Max memory entries to suggest at once
MAX_SUGGESTIONS = 3


async def maybe_suggest_memory(context, chat_id: int, user: dict):
    """Decide whether to run a memory suggestion now, and run it if so.

    Cheap-fail design: any error or insufficient data → silently skip.
    Never blocks or delays the AI reply (caller awaits this as fire-and-forget)."""
    try:
        if not user.get("api_keys"):
            return
        history = user.get("chat_history") or []
        turn_pairs = len(history) // 2
        if turn_pairs < SUGGEST_AFTER_TURNS:
            return
        last_suggested = int(user.get("memory_last_suggested_at_pairs", 0))
        if turn_pairs - last_suggested < SUGGEST_AFTER_TURNS:
            return

        # Build a flat transcript of the recent history
        recent = history[-SUGGEST_AFTER_TURNS * 2 :]
        transcript = "\n".join(
            f"{('User' if m['role'] == 'user' else 'AI')}: {m['content'][:400]}"
            for m in recent
        )

        existing_keys = list((user.get("memory") or {}).keys())
        existing_block = (
            f"Already saved memory keys (do NOT suggest these again): "
            f"{', '.join(existing_keys)}\n\n" if existing_keys else ""
        )

        lang = user.get("language", "ru")
        lang_names = {"ru": "Russian", "en": "English", "it": "Italian"}
        prompt = (
            f"{existing_block}"
            f"Recent conversation:\n{transcript}\n\n"
            f"Identify up to {MAX_SUGGESTIONS} STABLE, long-term facts about the user worth "
            f"remembering across future conversations (name, profession, location, "
            f"preferences, ongoing projects, allergies, etc.). DO NOT include one-off "
            f"questions or short-lived context.\n\n"
            f"If nothing worth remembering, return an empty list.\n\n"
            f"Reply with STRICT JSON only, no markdown:\n"
            f'{{"suggestions": [{{"key": "short_snake_key", "value": "short value, <100 chars"}}, ...]}}\n\n'
            f"Use {lang_names.get(lang, 'English')} for values. Keys MUST be english snake_case."
        )

        user_id = user["id"]
        raw = await ai_handler.generate_response(
            user_id, prompt,
            system_prompt="You output ONLY valid JSON, no markdown fences, no commentary.",
            use_history=False,
        )
        if raw.startswith("❌"):
            return

        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
            raw_suggestions = data.get("suggestions") or []
        except (json.JSONDecodeError, KeyError, TypeError):
            return

        # Mark check-point even if AI returned nothing — we don't want to nag
        user["memory_last_suggested_at_pairs"] = turn_pairs

        if not raw_suggestions:
            await storage.save()
            return

        # Sanitize and filter
        suggestions = []
        for s in raw_suggestions[:MAX_SUGGESTIONS]:
            if not isinstance(s, dict):
                continue
            k = str(s.get("key", "")).strip()[:50]
            v = str(s.get("value", "")).strip()[:200]
            if not k or not v:
                continue
            if k in (user.get("memory") or {}):
                continue
            # snake_case key safety
            k = re.sub(r"[^a-z0-9_]", "_", k.lower())[:50] or f"fact_{len(suggestions) + 1}"
            suggestions.append({"key": k, "value": v})

        if not suggestions:
            await storage.save()
            return

        # Store as pending suggestion batch keyed by short_id for callbacks
        batch_id = secrets.token_urlsafe(4)
        pending = user.setdefault("memory_pending", {})
        pending[batch_id] = suggestions
        # Keep only the 3 most recent batches
        if len(pending) > 3:
            for k in list(pending.keys())[:-3]:
                pending.pop(k, None)
        await storage.save()

        # Render the suggestion message with inline buttons
        lines = [t(lang, "mem_suggest_header")]
        for i, s in enumerate(suggestions):
            lines.append(f"<b>{s['key']}</b>: {_escape(s['value'])}")
        text = "\n".join(lines)
        kb_rows = []
        for i, s in enumerate(suggestions):
            kb_rows.append([
                InlineKeyboardButton(t(lang, "mem_suggest_save", key=s['key'][:30]),
                                     callback_data=f"msave_{batch_id}_{i}")
            ])
        kb_rows.append([
            InlineKeyboardButton(t(lang, "mem_suggest_save_all"),
                                  callback_data=f"msaveall_{batch_id}"),
            InlineKeyboardButton(t(lang, "mem_suggest_skip"),
                                  callback_data=f"mskip_{batch_id}"),
        ])
        try:
            await context.bot.send_message(
                chat_id, text, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb_rows),
            )
        except Exception:
            pass
    except Exception:
        # Proactive memory must NEVER break the bot
        return


def _escape(s: str) -> str:
    import html
    return html.escape(s)


async def memory_suggest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle msave_<batch>_<idx>, msaveall_<batch>, mskip_<batch>."""
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    data = query.data or ""

    pending = user.get("memory_pending") or {}

    if data.startswith("msave_"):
        try:
            _, batch_id, idx_str = data.split("_", 2)
            idx = int(idx_str)
        except (ValueError, IndexError):
            return
        batch = pending.get(batch_id)
        if not batch or idx >= len(batch):
            try:
                await query.edit_message_text(t(lang, "mem_suggest_stale"))
            except Exception:
                pass
            return
        s = batch[idx]
        memory = user.setdefault("memory", {})
        memory[s["key"]] = s["value"]
        # Mark this slot as saved
        batch[idx]["_saved"] = True
        await storage.save()
        new_text = _render_batch(batch, lang)
        try:
            await query.edit_message_text(new_text, parse_mode="HTML",
                                           reply_markup=_render_batch_kb(batch, batch_id, lang))
        except Exception:
            pass
        return

    if data.startswith("msaveall_"):
        batch_id = data.split("_", 1)[1]
        batch = pending.get(batch_id)
        if not batch:
            return
        memory = user.setdefault("memory", {})
        saved = 0
        for s in batch:
            if s.get("_saved"):
                continue
            memory[s["key"]] = s["value"]
            s["_saved"] = True
            saved += 1
        pending.pop(batch_id, None)
        await storage.save()
        try:
            await query.edit_message_text(
                t(lang, "mem_suggest_saved_all", count=saved),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    if data.startswith("mskip_"):
        batch_id = data.split("_", 1)[1]
        pending.pop(batch_id, None)
        await storage.save()
        try:
            await query.edit_message_text(t(lang, "mem_suggest_skipped"))
        except Exception:
            pass
        return


def _render_batch(batch, lang):
    """Re-render a suggestion batch showing which entries are saved."""
    lines = [t(lang, "mem_suggest_header")]
    for s in batch:
        check = "✅ " if s.get("_saved") else ""
        lines.append(f"{check}<b>{s['key']}</b>: {_escape(s['value'])}")
    return "\n".join(lines)


def _render_batch_kb(batch, batch_id, lang):
    """Re-render keyboard hiding already-saved items."""
    kb_rows = []
    has_unsaved = False
    for i, s in enumerate(batch):
        if s.get("_saved"):
            continue
        has_unsaved = True
        kb_rows.append([
            InlineKeyboardButton(t(lang, "mem_suggest_save", key=s['key'][:30]),
                                 callback_data=f"msave_{batch_id}_{i}")
        ])
    if has_unsaved:
        kb_rows.append([
            InlineKeyboardButton(t(lang, "mem_suggest_save_all"),
                                  callback_data=f"msaveall_{batch_id}"),
            InlineKeyboardButton(t(lang, "mem_suggest_skip"),
                                  callback_data=f"mskip_{batch_id}"),
        ])
    return InlineKeyboardMarkup(kb_rows)
