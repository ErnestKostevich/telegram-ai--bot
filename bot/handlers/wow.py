"""Wow-factor commands: personas, dice mini-games, /today, /quiz."""
import asyncio
import datetime
import html
import json
import random
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler
from bot.i18n import t


# ============== PERSONAS ==============

PERSONAS = {
    "default": "",
    "philosopher": "Respond as a thoughtful philosopher. Quote thinkers occasionally. Be deep, slow, considered. Use metaphors.",
    "comedian": "Respond as a stand-up comedian. Witty, punchy, never offensive. Drop a one-liner where it fits.",
    "teacher": "Respond as a patient teacher. Explain step by step, with examples. Check understanding at the end.",
    "coach": "Respond as a high-energy motivational coach. Direct, encouraging, action-oriented. Use 💪 sparingly.",
    "sarcastic": "Respond with light, harmless sarcasm. Witty deadpan tone. Still actually answer the question.",
    "kid": "Respond like you're talking to a curious 8-year-old. Simple words, friendly, use analogies kids get.",
    "pirate": "Respond as a friendly pirate. Use 'arrr', 'matey', nautical terms. Stay actually helpful.",
}


async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        # No args → show interactive picker
        from bot.keyboards import get_persona_picker_keyboard
        current = user.get("persona", "default")
        await update.message.reply_text(
            t(lang, "persona_pick"),
            parse_mode="HTML",
            reply_markup=get_persona_picker_keyboard(lang, current=current),
        )
        return
    name = context.args[0].lower()
    if name in ("off", "none", "reset"):
        user["persona"] = "default"
        await storage.save()
        await update.message.reply_text(t(lang, "persona_off"))
        return
    if name not in PERSONAS:
        await update.message.reply_text(
            t(lang, "persona_unknown", list=", ".join(PERSONAS.keys()))
        )
        return
    user["persona"] = name
    await storage.save()
    await update.message.reply_text(t(lang, "persona_set", name=name), parse_mode="HTML")


def get_persona_addon(user: dict) -> str:
    """Return the persona-specific instruction snippet for the system prompt."""
    return PERSONAS.get(user.get("persona", "default"), "")


# ============== DICE MINI-GAMES ==============

_GAME_DEFS = {
    "slots":    ("🎰", "slots",    {64: "JACKPOT! 🎰", 1: "—", 22: "🍒🍒🍒", 43: "🍋🍋🍋"}),
    "basket":   ("🏀", "basket",   {4: "🎯 SCORE!", 5: "🎯 SCORE!"}),
    "football": ("⚽", "football", {3: "⚽ GOAL!", 4: "⚽ GOAL!", 5: "⚽ GOAL!"}),
    "dart":     ("🎯", "dart",     {6: "🎯 BULLSEYE!"}),
    "bowl":     ("🎳", "bowl",     {6: "🎳 STRIKE!"}),
}


async def _play_dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_key: str):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    emoji, _, wins = _GAME_DEFS[game_key]

    sent = await update.message.reply_dice(emoji=emoji)
    value = sent.dice.value

    # Track per-game stats
    games = user.setdefault("games", {})
    g = games.setdefault(game_key, {"plays": 0, "wins": 0})
    g["plays"] += 1

    if value in wins:
        g["wins"] += 1
        await storage.save()
        await asyncio.sleep(3.5)  # let the dice animation finish
        await update.message.reply_text(
            t(lang, "game_win", label=wins[value], wins=g["wins"], plays=g["plays"]),
            parse_mode="HTML",
        )
    else:
        await storage.save()
        await asyncio.sleep(3.5)
        await update.message.reply_text(
            t(lang, "game_lose", wins=g["wins"], plays=g["plays"]),
            parse_mode="HTML",
        )


async def slots_command(update, context):    await _play_dice_game(update, context, "slots")
async def basket_command(update, context):   await _play_dice_game(update, context, "basket")
async def football_command(update, context): await _play_dice_game(update, context, "football")
async def dart_command(update, context):     await _play_dice_game(update, context, "dart")
async def bowl_command(update, context):     await _play_dice_game(update, context, "bowl")


# ============== /today AI fortune ==============

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    today = datetime.date.today().isoformat()
    cached = user.get("today_cache")
    if cached and cached.get("date") == today:
        await update.message.reply_text(cached["text"], parse_mode="HTML")
        return

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    placeholder = await update.message.reply_text(t(lang, "today_loading"))

    lang_names = {"ru": "Russian", "en": "English", "it": "Italian"}
    prompt = (
        f"Generate a creative, encouraging 'fortune of the day' for today. "
        f"Include: one upbeat insight (1 sentence), one tiny actionable challenge (1 sentence), "
        f"and a lucky 'vibe number' between 1 and 99. Use {lang_names.get(lang, 'English')}. "
        f"Keep total length under 350 characters. Make it different from generic horoscopes — "
        f"be specific and curious, with a hint of playful wit. Date seed: {today}-{uid}."
    )
    try:
        response = await ai_handler.generate_response(
            uid, prompt,
            system_prompt="You write fun, encouraging daily fortunes. Never repeat phrasing.",
            use_history=False,
        )
        if response.startswith("❌"):
            await placeholder.edit_text(response, parse_mode="HTML")
            return
        safe = html.escape(response.strip())
        text = t(lang, "today_text", body=safe, date=today)
        user["today_cache"] = {"date": today, "text": text}
        await storage.save()
        await placeholder.edit_text(text, parse_mode="HTML")
    except Exception as e:
        await placeholder.edit_text(f"❌ {e}")


# ============== /quiz AI quiz with inline buttons ==============

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    topic = " ".join(context.args).strip() or t(lang, "quiz_default_topic")
    lang_names = {"ru": "Russian", "en": "English", "it": "Italian"}

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    placeholder = await update.message.reply_text(t(lang, "quiz_loading", topic=topic))

    prompt = (
        f"Generate ONE multiple-choice trivia question about: {topic}. "
        f"Return STRICT JSON only, no markdown, with this shape:\n"
        f'{{"question": "...", "options": ["A", "B", "C", "D"], "correct": 0, "explanation": "..."}}\n'
        f"correct is the 0-based index of the right option. "
        f"Question and answers in {lang_names.get(lang, 'English')}. "
        f"Keep question under 200 chars, each option under 80 chars, explanation under 150 chars."
    )
    try:
        raw = await ai_handler.generate_response(
            uid, prompt,
            system_prompt="You output ONLY valid JSON, no markdown fences, no commentary.",
            use_history=False,
        )
        if raw.startswith("❌"):
            await placeholder.edit_text(raw, parse_mode="HTML")
            return
        # Strip possible markdown fences
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(cleaned)
        question = str(data["question"])[:300]
        options = [str(o)[:90] for o in data["options"]][:4]
        correct = int(data["correct"])
        explanation = str(data.get("explanation", ""))[:200]
        if len(options) < 2 or not (0 <= correct < len(options)):
            raise ValueError("invalid quiz shape")
    except Exception as e:
        await placeholder.edit_text(t(lang, "quiz_error", err=str(e)[:100]))
        return

    # Stash the answer key
    quizzes = user.setdefault("active_quizzes", {})
    qid = f"q{int(time.time()*1000)}"
    quizzes[qid] = {"correct": correct, "options": options, "explanation": explanation, "topic": topic, "ts": time.time()}
    # Keep only the most recent few to avoid bloat
    if len(quizzes) > 10:
        oldest = sorted(quizzes.items(), key=lambda kv: kv[1]["ts"])[:-10]
        for k, _ in oldest:
            quizzes.pop(k, None)
    await storage.save()

    keyboard = [
        [InlineKeyboardButton(f"{chr(65 + i)}. {opt}"[:64], callback_data=f"quizans_{qid}_{i}")]
        for i, opt in enumerate(options)
    ]
    await placeholder.edit_text(
        t(lang, "quiz_question", topic=html.escape(topic), q=html.escape(question)),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    try:
        _, qid, chosen_str = query.data.split("_", 2)
        chosen = int(chosen_str)
    except (ValueError, IndexError):
        return

    quizzes = user.get("active_quizzes", {}) or {}
    q = quizzes.get(qid)
    if not q:
        try:
            await query.edit_message_text(t(lang, "quiz_expired"))
        except Exception:
            pass
        return

    correct = q["correct"]
    options = q["options"]
    explanation = q["explanation"]

    stats = user.setdefault("quiz_stats", {"correct": 0, "total": 0})
    stats["total"] = stats.get("total", 0) + 1
    if chosen == correct:
        stats["correct"] = stats.get("correct", 0) + 1
        verdict = t(lang, "quiz_correct", chosen=chr(65 + chosen), text=html.escape(options[chosen]))
    else:
        verdict = t(lang, "quiz_wrong",
                    chosen=chr(65 + chosen), chosen_text=html.escape(options[chosen]),
                    correct=chr(65 + correct), correct_text=html.escape(options[correct]))

    body = verdict
    if explanation:
        body += f"\n\n<i>💡 {html.escape(explanation)}</i>"
    body += f"\n\n📊 {t(lang, 'quiz_score', correct=stats['correct'], total=stats['total'])}"

    quizzes.pop(qid, None)
    await storage.save()
    try:
        await query.edit_message_text(body, parse_mode="HTML")
    except Exception:
        pass
