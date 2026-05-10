translations = {
    "ru": {
        "welcome": "🤖 <b>Добро пожаловать в AI DISCO BOT!</b>\n\nЯ — многофункциональный ИИ-ассистент.\nВ этой версии внедрена система <b>BYOK (Bring Your Own Key)</b>, что дает вам свободу выбора из 10+ провайдеров (Gemini, OpenAI, Anthropic и др.).\n\n<b>С чего начать:</b>\n1. Перейдите в настройки: <code>/setprovider</code>\n2. Установите ваш ключ: <code>/setkey [провайдер] [ключ]</code>\n3. Просто общайтесь или отправляйте файлы/фото!\n\n👇 <i>Воспользуйтесь меню ниже для управления:</i>",
        "btn_ai": "💬 AI Чат", "btn_mem": "🧠 Память", "btn_notes": "📝 Заметки", "btn_vip": "💎 VIP Меню",
        "btn_settings": "⚙️ Настройки AI", "btn_admin": "👑 Админ", "btn_lang": "🌐 Язык",
        "help": "📚 <b>Справка по командам:</b>\n\nВыберите нужный раздел в меню ниже:",
        "lang_changed": "🇷🇺 Язык изменен на Русский.",
        "ik_provider": "⚡ Выбрать провайдера", "ik_model": "🧠 Выбрать модель", "ik_keys": "🔑 Настроить ключи",
        "ik_reminders": "⏰ Мои напоминания", "ik_generate": "🖼️ Генерация картинок", "ik_guardian": "🛡️ AI Guardian",
        "ik_back": "🔙 Назад",
        "vip_menu": "💎 VIP Меню:", "settings_menu": "⚙️ Настройки AI:",
        "profile_title": "👤 <b>Ваш профиль (Уровень {level})</b>\n\n✨ Опыт: {xp} / {next_level_xp} XP\n📊 Прогресс: {progress_bar} {progress}%\n\n💎 VIP Статус: {vip_status}\n💬 Отправлено сообщений: {msgs}\n⚡ BYOK Провайдер: {provider}\n🧠 Модель: {model}",
        "status_yes": "👑 Да", "status_no": "❌ Нет"
    },
    "en": {
        "welcome": "🤖 <b>Welcome to AI DISCO BOT!</b>\n\nI am a multi-functional AI assistant.\nThis version features a <b>BYOK (Bring Your Own Key)</b> system, giving you the freedom to choose from 10+ providers.\n\n<b>How to start:</b>\n1. Go to settings: <code>/setprovider</code>\n2. Set your key: <code>/setkey [provider] [key]</code>\n3. Just chat or send files/photos!\n\n👇 <i>Use the menu below to manage:</i>",
        "btn_ai": "💬 AI Chat", "btn_mem": "🧠 Memory", "btn_notes": "📝 Notes", "btn_vip": "💎 VIP Menu",
        "btn_settings": "⚙️ AI Settings", "btn_admin": "👑 Admin", "btn_lang": "🌐 Language",
        "help": "📚 <b>Command Reference:</b>\n\nSelect a section from the menu below:",
        "lang_changed": "🇬🇧 Language changed to English.",
        "ik_provider": "⚡ Select Provider", "ik_model": "🧠 Select Model", "ik_keys": "🔑 Configure Keys",
        "ik_reminders": "⏰ My Reminders", "ik_generate": "🖼️ Generate Image", "ik_guardian": "🛡️ AI Guardian",
        "ik_back": "🔙 Back",
        "vip_menu": "💎 VIP Menu:", "settings_menu": "⚙️ AI Settings:",
        "profile_title": "👤 <b>Your Profile (Level {level})</b>\n\n✨ XP: {xp} / {next_level_xp}\n📊 Progress: {progress_bar} {progress}%\n\n💎 VIP Status: {vip_status}\n💬 Messages sent: {msgs}\n⚡ BYOK Provider: {provider}\n🧠 Model: {model}",
        "status_yes": "👑 Yes", "status_no": "❌ No"
    },
    "it": {
        "welcome": "🤖 <b>Benvenuto in AI DISCO BOT!</b>\n\nSono un assistente AI multifunzionale.\nQuesta versione include il sistema <b>BYOK (Bring Your Own Key)</b>, che ti dà la libertà di scegliere tra oltre 10 provider.\n\n<b>Come iniziare:</b>\n1. Vai alle impostazioni: <code>/setprovider</code>\n2. Imposta la tua chiave: <code>/setkey [provider] [chiave]</code>\n3. Chatta o invia file/foto!\n\n👇 <i>Usa il menu sottostante:</i>",
        "btn_ai": "💬 Chat AI", "btn_mem": "🧠 Memoria", "btn_notes": "📝 Note", "btn_vip": "💎 Menu VIP",
        "btn_settings": "⚙️ Impostazioni AI", "btn_admin": "👑 Admin", "btn_lang": "🌐 Lingua",
        "help": "📚 <b>Guida ai comandi:</b>\n\nSeleziona una sezione nel menu sottostante:",
        "lang_changed": "🇮🇹 Lingua cambiata in Italiano.",
        "ik_provider": "⚡ Seleziona Provider", "ik_model": "🧠 Seleziona Modello", "ik_keys": "🔑 Configura Chiavi",
        "ik_reminders": "⏰ Miei Promemoria", "ik_generate": "🖼️ Genera Immagine", "ik_guardian": "🛡️ AI Guardian",
        "ik_back": "🔙 Indietro",
        "vip_menu": "💎 Menu VIP:", "settings_menu": "⚙️ Impostazioni AI:",
        "profile_title": "👤 <b>Il tuo profilo (Livello {level})</b>\n\n✨ XP: {xp} / {next_level_xp}\n📊 Progresso: {progress_bar} {progress}%\n\n💎 Stato VIP: {vip_status}\n💬 Messaggi inviati: {msgs}\n⚡ Provider BYOK: {provider}\n🧠 Modello: {model}",
        "status_yes": "👑 Sì", "status_no": "❌ No"
    }
}

def get_text(user_lang: str, key: str) -> str:
    lang = user_lang if user_lang in translations else "ru"
    return translations[lang].get(key, translations["ru"].get(key, key))
