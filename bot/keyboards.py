from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.i18n import get_text

def get_main_keyboard(lang="ru"):
    keyboard = [
        [KeyboardButton(get_text(lang, "btn_ai")), KeyboardButton(get_text(lang, "btn_mem"))],
        [KeyboardButton(get_text(lang, "btn_notes")), KeyboardButton(get_text(lang, "btn_vip"))],
        [KeyboardButton(get_text(lang, "btn_settings")), KeyboardButton(get_text(lang, "btn_admin"))],
        [KeyboardButton(get_text(lang, "btn_lang"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_settings_keyboard(lang="ru"):
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "ik_provider"), callback_data="ai_provider")],
        [InlineKeyboardButton(get_text(lang, "ik_model"), callback_data="ai_model")],
        [InlineKeyboardButton(get_text(lang, "ik_keys"), callback_data="ai_keys")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_vip_keyboard(lang="ru"):
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "ik_reminders"), callback_data="vip_reminders")],
        [InlineKeyboardButton(get_text(lang, "ik_generate"), callback_data="vip_generate")],
        [InlineKeyboardButton(get_text(lang, "ik_guardian"), callback_data="vip_guardian")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_help_keyboard(lang="ru", submenu=None):
    if submenu:
        return InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="help_back")]])
        
    keyboard = [
        [
            InlineKeyboardButton("🏠 Базовые", callback_data="help_base"),
            InlineKeyboardButton("💬 AI & Память", callback_data="help_ai")
        ],
        [
            InlineKeyboardButton("📝 Заметки", callback_data="help_notes"),
            InlineKeyboardButton("💎 VIP", callback_data="help_vip")
        ],
        [
            InlineKeyboardButton("👥 Группы", callback_data="help_groups"),
            InlineKeyboardButton("👑 Создатель", callback_data="help_creator")
        ],
        [InlineKeyboardButton("🎮 Игры & Утилиты", callback_data="help_games")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_lang_keyboard():
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it")]
    ]
    return InlineKeyboardMarkup(keyboard)
