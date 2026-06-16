from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.i18n import get_text


def get_main_keyboard(lang="en", user_id=None):
    keyboard = [
        [KeyboardButton(get_text(lang, "btn_ai")), KeyboardButton(get_text(lang, "btn_mem"))],
        [KeyboardButton(get_text(lang, "btn_notes")), KeyboardButton(get_text(lang, "btn_vip"))],
        [KeyboardButton(get_text(lang, "btn_settings")), KeyboardButton(get_text(lang, "btn_games"))],
        [KeyboardButton(get_text(lang, "btn_tools")), KeyboardButton(get_text(lang, "btn_lang"))],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_settings_keyboard(lang="en", user=None):
    """Settings keyboard. If `user` is passed, button labels show current values
    (provider/model/persona) so users instantly see what's selected."""
    from bot.ai import DEFAULT_MODELS

    provider_label = get_text(lang, "ik_provider")
    model_label = get_text(lang, "ik_model")
    persona_label = get_text(lang, "ik_persona")

    if user is not None:
        provider = user.get("ai_provider", "gemini")
        model = user.get("ai_model") or DEFAULT_MODELS.get(provider, "default")
        # Trim model to fit nicely
        short_model = model if len(model) <= 20 else model[:17] + "…"
        persona = user.get("persona", "default")
        provider_label = f"⚡ {provider}"
        model_label = f"🧠 {short_model}"
        persona_label = f"🎭 {persona}"

    keyboard = [
        [InlineKeyboardButton(provider_label, callback_data="ai_provider"),
         InlineKeyboardButton(model_label, callback_data="ai_model")],
        [InlineKeyboardButton(get_text(lang, "ik_keys"), callback_data="ai_keys"),
         InlineKeyboardButton(persona_label, callback_data="ai_persona")],
        [InlineKeyboardButton(get_text(lang, "ik_clear"), callback_data="ai_clear"),
         InlineKeyboardButton(get_text(lang, "ik_disco"), callback_data="toggle_disco")],
        [InlineKeyboardButton(get_text(lang, "ik_profile"), callback_data="show_profile")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_provider_picker_keyboard(lang="en", current=None, action_prefix="setprov"):
    """Grid of provider buttons. action_prefix controls what the callback does:
      - 'setprov' → sets the user's provider (used by Settings → Provider)
      - 'keyfor'  → starts the 2-step setkey flow (used by Settings → API Key)
    """
    from bot.ai import PROVIDERS
    kb = []
    row = []
    for p in PROVIDERS:
        label = f"✅ {p}" if p == current else p.capitalize()
        row.append(InlineKeyboardButton(label, callback_data=f"{action_prefix}_{p}"))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_settings")])
    return InlineKeyboardMarkup(kb)


def get_persona_picker_keyboard(lang="en", current="default"):
    from bot.handlers.wow import PERSONAS
    icons = {
        "default": "💬", "philosopher": "🧘", "comedian": "🎭", "teacher": "📚",
        "coach": "💪", "sarcastic": "😏", "kid": "🧒", "pirate": "🏴‍☠️",
    }
    kb = []
    row = []
    for name in PERSONAS.keys():
        icon = icons.get(name, "•")
        label = f"✅ {icon} {name}" if name == current else f"{icon} {name}"
        row.append(InlineKeyboardButton(label, callback_data=f"setpersona_{name}"))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_settings")])
    return InlineKeyboardMarkup(kb)


def get_vip_keyboard(lang="en"):
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "ik_reminders"), callback_data="vip_reminders"),
         InlineKeyboardButton(get_text(lang, "ik_generate"), callback_data="vip_generate")],
        [InlineKeyboardButton(get_text(lang, "ik_guardian"), callback_data="vip_guardian")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_games_keyboard(lang="en"):
    """Games + WOW shortcuts on a single screen."""
    keyboard = [
        [InlineKeyboardButton("🎰 Slots", callback_data="game_slots"),
         InlineKeyboardButton("🏀 Basket", callback_data="game_basket")],
        [InlineKeyboardButton("⚽ Football", callback_data="game_football"),
         InlineKeyboardButton("🎯 Dart", callback_data="game_dart")],
        [InlineKeyboardButton("🎳 Bowl", callback_data="game_bowl"),
         InlineKeyboardButton("🎲 Dice", callback_data="game_dice")],
        [InlineKeyboardButton("🪙 Coinflip", callback_data="game_coinflip"),
         InlineKeyboardButton("😄 Joke", callback_data="game_joke")],
        [InlineKeyboardButton("🔮 Today", callback_data="game_today"),
         InlineKeyboardButton("🧠 Quiz", callback_data="game_quiz")],
        [InlineKeyboardButton("🎁 Daily", callback_data="game_daily"),
         InlineKeyboardButton("🔥 Roast", callback_data="game_roast")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_tools_keyboard(lang="en"):
    keyboard = [
        [InlineKeyboardButton("⏰ Time", callback_data="tool_time"),
         InlineKeyboardButton("🌤 Weather", callback_data="tool_weather")],
        [InlineKeyboardButton("🧮 Calc", callback_data="tool_calc"),
         InlineKeyboardButton("🔑 Password", callback_data="tool_password")],
        [InlineKeyboardButton("🌍 Translate", callback_data="tool_translate")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_help_keyboard(lang="en", submenu=None, user_id=None):
    if submenu:
        return InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="help_back")]])
    from bot.config import CREATOR_ID
    labels = {
        "ru": {"base": "🏠 Базовые", "ai": "💬 AI & Память", "notes": "📝 Заметки", "vip": "💎 VIP", "groups": "👥 Группы", "games": "🎮 Игры", "creator": "👑 Создатель"},
        "en": {"base": "🏠 Basic", "ai": "💬 AI & Memory", "notes": "📝 Notes", "vip": "💎 VIP", "groups": "👥 Groups", "games": "🎮 Games", "creator": "👑 Creator"},
        "it": {"base": "🏠 Base", "ai": "💬 AI & Memoria", "notes": "📝 Note", "vip": "💎 VIP", "groups": "👥 Gruppi", "games": "🎮 Giochi", "creator": "👑 Creatore"},
    }
    lb = labels.get(lang, labels["en"])
    keyboard = [
        [InlineKeyboardButton(lb["base"], callback_data="help_base"),
         InlineKeyboardButton(lb["ai"], callback_data="help_ai")],
        [InlineKeyboardButton(lb["notes"], callback_data="help_notes"),
         InlineKeyboardButton(lb["vip"], callback_data="help_vip")],
        [InlineKeyboardButton(lb["groups"], callback_data="help_groups"),
         InlineKeyboardButton(lb["games"], callback_data="help_games")],
    ]
    if user_id == CREATOR_ID:
        keyboard.append([InlineKeyboardButton(lb["creator"], callback_data="help_creator")])
    return InlineKeyboardMarkup(keyboard)


def get_lang_keyboard():
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
         InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it")],
    ]
    return InlineKeyboardMarkup(keyboard)
