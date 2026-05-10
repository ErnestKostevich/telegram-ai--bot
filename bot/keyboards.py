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

def get_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("Выбрать провайдера", callback_data="ai_provider")],
        [InlineKeyboardButton("Настроить ключи", callback_data="ai_keys")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_vip_keyboard():
    keyboard = [
        [InlineKeyboardButton("⏰ Мои напоминания", callback_data="vip_reminders")],
        [InlineKeyboardButton("🖼️ Генерация картинок", callback_data="vip_generate")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_help_keyboard():
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
        [InlineKeyboardButton("🎮 Игры & Развлечения", callback_data="help_games")]
    ]
    return InlineKeyboardMarkup(keyboard)
