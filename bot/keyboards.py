from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.i18n import get_text

def get_main_keyboard(lang="ru", user_id=None):
    from bot.config import CREATOR_ID
    keyboard = [
        [KeyboardButton(get_text(lang, "btn_ai")), KeyboardButton(get_text(lang, "btn_mem"))],
        [KeyboardButton(get_text(lang, "btn_notes")), KeyboardButton(get_text(lang, "btn_vip"))],
        [KeyboardButton(get_text(lang, "btn_settings")), KeyboardButton(get_text(lang, "btn_games"))],
        [KeyboardButton(get_text(lang, "btn_tools")), KeyboardButton(get_text(lang, "btn_lang"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_settings_keyboard(lang="ru"):
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "ik_provider"), callback_data="ai_provider"),
         InlineKeyboardButton(get_text(lang, "ik_model"), callback_data="ai_model")],
        [InlineKeyboardButton(get_text(lang, "ik_keys"), callback_data="ai_keys"),
         InlineKeyboardButton(get_text(lang, "ik_clear"), callback_data="ai_clear")],
        [InlineKeyboardButton(get_text(lang, "ik_profile"), callback_data="show_profile"),
         InlineKeyboardButton(get_text(lang, "ik_disco"), callback_data="toggle_disco")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_vip_keyboard(lang="ru"):
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "ik_reminders"), callback_data="vip_reminders"),
         InlineKeyboardButton(get_text(lang, "ik_generate"), callback_data="vip_generate")],
        [InlineKeyboardButton(get_text(lang, "ik_guardian"), callback_data="vip_guardian")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_games_keyboard(lang="ru"):
    keyboard = [
        [InlineKeyboardButton("🎲 Dice", callback_data="game_dice"),
         InlineKeyboardButton("🪙 Coinflip", callback_data="game_coinflip")],
        [InlineKeyboardButton("😄 Joke", callback_data="game_joke"),
         InlineKeyboardButton("🎁 Daily", callback_data="game_daily")],
        [InlineKeyboardButton("🔥 Roast", callback_data="game_roast")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_tools_keyboard(lang="ru"):
    keyboard = [
        [InlineKeyboardButton("⏰ Time", callback_data="tool_time"),
         InlineKeyboardButton("🌤 Weather", callback_data="tool_weather")],
        [InlineKeyboardButton("🧮 Calc", callback_data="tool_calc"),
         InlineKeyboardButton("🔑 Password", callback_data="tool_password")],
        [InlineKeyboardButton("🌍 Translate", callback_data="tool_translate")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_help_keyboard(lang="ru", submenu=None, user_id=None):
    if submenu:
        return InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="help_back")]])
    from bot.config import CREATOR_ID
    labels = {
        "ru": {"base": "🏠 Базовые", "ai": "💬 AI & Память", "notes": "📝 Заметки", "vip": "💎 VIP", "groups": "👥 Группы", "games": "🎮 Игры", "creator": "👑 Создатель"},
        "en": {"base": "🏠 Basic", "ai": "💬 AI & Memory", "notes": "📝 Notes", "vip": "💎 VIP", "groups": "👥 Groups", "games": "🎮 Games", "creator": "👑 Creator"},
        "it": {"base": "🏠 Base", "ai": "💬 AI & Memoria", "notes": "📝 Note", "vip": "💎 VIP", "groups": "👥 Gruppi", "games": "🎮 Giochi", "creator": "👑 Creatore"}
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
         InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it")]
    ]
    return InlineKeyboardMarkup(keyboard)
