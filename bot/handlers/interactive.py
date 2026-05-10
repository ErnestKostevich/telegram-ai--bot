from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.keyboards import (get_settings_keyboard, get_vip_keyboard, get_lang_keyboard,
                           get_main_keyboard, get_help_keyboard, get_games_keyboard, get_tools_keyboard)
from bot.storage import storage
from bot.i18n import get_text, t

def _lang(update):
    return storage.get_user(update.effective_user.id).get("language", "ru")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    # === Provider ===
    if data == "ai_provider":
        user["state"] = "awaiting_setprovider"
        await storage.save()
        from bot.ai import PROVIDERS
        kb = []
        row = []
        for p in PROVIDERS:
            row.append(InlineKeyboardButton(p.capitalize(), callback_data=f"setprov_{p}"))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row: kb.append(row)
        kb.append([InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_settings")])
        await query.edit_message_text("⚡ <b>Provider</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("setprov_"):
        provider = data.split("_", 1)[1]
        from bot.ai import PROVIDERS, DEFAULT_MODELS
        if provider in PROVIDERS:
            user["ai_provider"] = provider
            user["ai_model"] = DEFAULT_MODELS.get(provider, "default")
            user["state"] = None
            await storage.save()
            await query.edit_message_text(t(lang, "provider_set", provider=provider), parse_mode="HTML")

    elif data == "ai_model":
        from bot.ai import PROVIDER_MODELS, DEFAULT_MODELS
        provider = user.get("ai_provider", "gemini")
        models = PROVIDER_MODELS.get(provider, [])
        current = user.get("ai_model", DEFAULT_MODELS.get(provider, "default"))
        kb = []
        for m in models:
            label = f"{'✅ ' if m == current else ''}{m}"
            # Truncate long model names for button display
            display = label if len(label) <= 40 else label[:37] + "..."
            kb.append([InlineKeyboardButton(display, callback_data=f"setmodel_{m}")])
        kb.append([InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_settings")])
        await query.edit_message_text(
            f"🧠 <b>Model</b> ({provider})\n\n<i>Current: {current}</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data.startswith("setmodel_"):
        model = data[len("setmodel_"):]
        user["ai_model"] = model
        await storage.save()
        # Re-show model list with updated checkmark
        from bot.ai import PROVIDER_MODELS, DEFAULT_MODELS
        provider = user.get("ai_provider", "gemini")
        models = PROVIDER_MODELS.get(provider, [])
        kb = []
        for m in models:
            label = f"{'✅ ' if m == model else ''}{m}"
            display = label if len(label) <= 40 else label[:37] + "..."
            kb.append([InlineKeyboardButton(display, callback_data=f"setmodel_{m}")])
        kb.append([InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_settings")])
        await query.edit_message_text(
            f"🧠 <b>Model</b> ({provider})\n\n✅ <b>{model}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data == "ai_keys":
        user["state"] = "awaiting_setkey"
        await storage.save()
        await query.edit_message_text("🔑 <b>API Key</b>\n\nSend: <code>provider key</code>\nExample: <code>gemini AIza...</code>", parse_mode="HTML")

    elif data == "back_settings":
        await query.edit_message_text(get_text(lang, "settings_menu"), parse_mode="HTML", reply_markup=get_settings_keyboard(lang))

    # === Profile & Disco (inline) ===
    elif data == "show_profile":
        xp = user.get("stats", {}).get("commands", 0) * 10
        level = xp // 100 + 1
        next_xp = level * 100
        progress = xp % 100
        vip = t(lang, "status_yes") if user.get("vip") else t(lang, "status_no")
        text = t(lang, "profile_title", level=level, xp=xp, next_level_xp=next_xp,
                 progress_bar='▓'*(progress//10)+'░'*(10-progress//10), progress=progress,
                 vip_status=vip, msgs=user.get('stats',{}).get('msgs',0),
                 provider=user.get('ai_provider','gemini'), model=user.get('ai_model','default'))
        await query.edit_message_text(text, parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_settings")]]))

    elif data == "toggle_disco":
        user["disco_mode"] = not user.get("disco_mode", False)
        await storage.save()
        msg = t(lang, "disco_on") if user["disco_mode"] else t(lang, "disco_off")
        await query.edit_message_text(msg, parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_settings")]]))

    # === VIP ===
    elif data == "vip_reminders":
        await query.edit_message_text(t(lang, "remind_usage"), parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_vip")]]))
    elif data == "vip_generate":
        user["state"] = "awaiting_generate_prompt"
        await storage.save()
        await query.edit_message_text(t(lang, "gen_describe"), parse_mode="HTML")
    elif data == "vip_guardian":
        await query.edit_message_text("🛡️ <b>AI Guardian</b>\n\n<code>/guardian on</code> / <code>/guardian off</code>", parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "ik_back"), callback_data="back_vip")]]))
    elif data == "back_vip":
        await query.edit_message_text(get_text(lang, "vip_menu"), parse_mode="HTML", reply_markup=get_vip_keyboard(lang))

    # === Language ===
    elif data.startswith("lang_"):
        new_lang = data.split("_")[1]
        user["language"] = new_lang
        await storage.save()
        await query.message.delete()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(new_lang, "lang_changed"), reply_markup=get_main_keyboard(new_lang))

    # === Help ===
    elif data == "help_back":
        await query.edit_message_text(get_text(lang, "help"), parse_mode="HTML", reply_markup=get_help_keyboard(lang, user_id=uid))

    elif data.startswith("help_"):
        section = data.split("_")[1]
        sections = {
            "ru": {
                "base": "🏠 <b>Базовые команды</b>\n\n/start — запуск бота\n/help — справка\n/info — о боте\n/status — статус системы\n/profile — ваш профиль и XP\n/lang — смена языка\n/disco on|off — режим вечеринки 🪩",
                "ai": "💬 <b>AI & Память</b>\n\n🤖 <b>Общение:</b>\n/ai [вопрос] — спросить AI\n\n⚙️ <b>Настройка BYOK:</b>\n/setprovider — выбрать провайдера\n/setkey [пров] [ключ] — API ключ\n/setmodel [модель] — выбрать модель\n\n🧠 <b>Память:</b>\n/memorysave [ключ] [значение]\n/memoryget [ключ]\n/memorylist — все записи\n/memorydel [ключ]",
                "notes": "📝 <b>Заметки & Задачи</b>\n\n📌 <b>Заметки:</b>\n/note [текст] — создать\n/notes — показать все\n/delnote [#] — удалить\n\n📋 <b>Задачи:</b>\n/todo [текст] — добавить\n/todo — список\n/todo done [#] — завершить\n/todo del [#] — удалить",
                "vip": "💎 <b>VIP функции</b>\n\n/vip — статус\n/remind [мин] [текст] — напоминание\n/reminders — список\n/generate [описание] — 🖼 генерация картинок\n/daily — ежедневная награда",
                "groups": "👥 <b>Группы</b>\n\n🛡 <b>Модерация:</b>\n/warn /mute /ban /kick\n/guardian on|off — AI защита\n\n🤖 <b>AI в группах:</b>\n/ask [вопрос]\n/summary — сводка чата\n/translate [язык] [текст]\n@бот [вопрос] — по упоминанию\n\n📢 <b>Управление:</b>\n/rules • /setrules • /groupstats",
                "games": "🎮 <b>Игры & Утилиты</b>\n\n🎲 /dice — кубик\n🪙 /coinflip — монетка\n🔢 /random [от] [до]\n😄 /joke — шутка\n🎁 /daily — награда\n🔥 /roast — прожарка\n\n🛠 <b>Утилиты:</b>\n⏰ /time [город]\n🌤 /weather [город]\n🧮 /calc [выражение]\n🔑 /password [длина]\n🌍 /translate [язык] [текст]",
                "creator": "👑 <b>Команды создателя</b>\n\n/grant_vip [@user] [week|month|year|forever]\n/grant_vip [@user] remove — забрать\n/users — список пользователей\n/broadcast [текст] — рассылка\n/stats — статистика бота"
            },
            "en": {
                "base": "🏠 <b>Basic Commands</b>\n\n/start — launch bot\n/help — reference\n/info — about bot\n/status — system status\n/profile — your profile & XP\n/lang — change language\n/disco on|off — party mode 🪩",
                "ai": "💬 <b>AI & Memory</b>\n\n🤖 <b>Chat:</b>\n/ai [question] — ask AI\n\n⚙️ <b>BYOK Setup:</b>\n/setprovider — pick provider\n/setkey [prov] [key] — API key\n/setmodel [model] — pick model\n\n🧠 <b>Memory:</b>\n/memorysave [key] [value]\n/memoryget [key]\n/memorylist — all entries\n/memorydel [key]",
                "notes": "📝 <b>Notes & Tasks</b>\n\n📌 <b>Notes:</b>\n/note [text] — create\n/notes — show all\n/delnote [#] — delete\n\n📋 <b>Tasks:</b>\n/todo [text] — add\n/todo — list\n/todo done [#] — complete\n/todo del [#] — delete",
                "vip": "💎 <b>VIP Features</b>\n\n/vip — status\n/remind [min] [text] — reminder\n/reminders — list\n/generate [prompt] — 🖼 image generation\n/daily — daily reward",
                "groups": "👥 <b>Groups</b>\n\n🛡 <b>Moderation:</b>\n/warn /mute /ban /kick\n/guardian on|off — AI protection\n\n🤖 <b>Group AI:</b>\n/ask [question]\n/summary — chat summary\n/translate [lang] [text]\n@bot [question] — by mention\n\n📢 <b>Management:</b>\n/rules • /setrules • /groupstats",
                "games": "🎮 <b>Games & Tools</b>\n\n🎲 /dice — dice roll\n🪙 /coinflip — coin flip\n🔢 /random [min] [max]\n😄 /joke — joke\n🎁 /daily — reward\n🔥 /roast — roast\n\n🛠 <b>Tools:</b>\n⏰ /time [city]\n🌤 /weather [city]\n🧮 /calc [expression]\n🔑 /password [length]\n🌍 /translate [lang] [text]",
                "creator": "👑 <b>Creator Commands</b>\n\n/grant_vip [@user] [week|month|year|forever]\n/grant_vip [@user] remove — revoke\n/users — user list\n/broadcast [text] — mass send\n/stats — bot statistics"
            },
            "it": {
                "base": "🏠 <b>Comandi Base</b>\n\n/start — avvia bot\n/help — guida\n/info — info bot\n/status — stato sistema\n/profile — profilo e XP\n/lang — cambia lingua\n/disco on|off — modalità festa 🪩",
                "ai": "💬 <b>AI & Memoria</b>\n\n🤖 <b>Chat:</b>\n/ai [domanda] — chiedi all'AI\n\n⚙️ <b>Setup BYOK:</b>\n/setprovider — scegli provider\n/setkey [prov] [chiave] — chiave API\n/setmodel [modello] — scegli modello\n\n🧠 <b>Memoria:</b>\n/memorysave [chiave] [valore]\n/memoryget [chiave]\n/memorylist — tutte le voci\n/memorydel [chiave]",
                "notes": "📝 <b>Note & Compiti</b>\n\n📌 <b>Note:</b>\n/note [testo] — crea\n/notes — mostra\n/delnote [#] — elimina\n\n📋 <b>Compiti:</b>\n/todo [testo] — aggiungi\n/todo — lista\n/todo done [#] — completa\n/todo del [#] — elimina",
                "vip": "💎 <b>Funzioni VIP</b>\n\n/vip — stato\n/remind [min] [testo] — promemoria\n/reminders — lista\n/generate [desc] — 🖼 genera immagine\n/daily — premio giornaliero",
                "groups": "👥 <b>Gruppi</b>\n\n🛡 <b>Moderazione:</b>\n/warn /mute /ban /kick\n/guardian on|off — protezione AI\n\n🤖 <b>AI nel Gruppo:</b>\n/ask [domanda]\n/summary — riassunto chat\n/translate [lingua] [testo]\n@bot [domanda] — per menzione\n\n📢 <b>Gestione:</b>\n/rules • /setrules • /groupstats",
                "games": "🎮 <b>Giochi & Strumenti</b>\n\n🎲 /dice — dado\n🪙 /coinflip — moneta\n🔢 /random [min] [max]\n😄 /joke — barzelletta\n🎁 /daily — premio\n🔥 /roast — roast\n\n🛠 <b>Strumenti:</b>\n⏰ /time [città]\n🌤 /weather [città]\n🧮 /calc [espressione]\n🔑 /password [lunghezza]\n🌍 /translate [lingua] [testo]",
                "creator": "👑 <b>Comandi Creatore</b>\n\n/grant_vip [@user] [week|month|year|forever]\n/grant_vip [@user] remove — revocare\n/users — lista utenti\n/broadcast [testo] — invio massivo\n/stats — statistiche bot"
            }
        }
        lang_sections = sections.get(lang, sections["en"])
        text = lang_sections.get(section, f"ℹ️ {section}")
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_help_keyboard(lang, submenu=True, user_id=uid))

    # === Games buttons ===
    elif data == "game_dice":
        await query.message.reply_dice(emoji="🎲")
        await query.message.delete()
    elif data == "game_coinflip":
        result = get_text(lang, "coinflip_h") if __import__('random').randint(0,1) else get_text(lang, "coinflip_t")
        await query.edit_message_text(t(lang, "coinflip_text", result=result), parse_mode="HTML")
    elif data == "game_joke":
        import random
        jokes = {
            "ru": ["Почему программисты не любят природу? Слишком много багов. 🐛", "Оптимист: стакан наполовину полон. Программист: стакан в два раза больше, чем нужно. 🥛"],
            "en": ["Why do programmers prefer dark mode? Light attracts bugs. 🐛", "There are 10 types of people: those who understand binary and those who don't. 💻"],
            "it": ["Perché i programmatori preferiscono il buio? La luce attira i bug. 🐛", "Ci sono 10 tipi di persone: chi capisce il binario e chi no. 💻"],
        }
        await query.edit_message_text(f"😄 {random.choice(jokes.get(lang, jokes['en']))}")
    elif data == "game_daily":
        user["stats"]["commands"] = user["stats"].get("commands", 0) + 50
        await storage.save()
        await query.edit_message_text("🎁 <b>+500 XP!</b>", parse_mode="HTML")
    elif data == "game_roast":
        import random
        roasts = {"ru": ["Твой код как чувство юмора — полон багов! 🔥"], "en": ["Your code is like your humor — full of bugs! 🔥"], "it": ["Il tuo codice è come il tuo umorismo — pieno di bug! 🔥"]}
        await query.edit_message_text(f"🔥 {random.choice(roasts.get(lang, roasts['en']))}")

    # === Tool buttons ===
    elif data == "tool_time":
        user["state"] = "awaiting_time_city"
        await storage.save()
        await query.edit_message_text(t(lang, "time_usage"))
    elif data == "tool_weather":
        user["state"] = "awaiting_weather_city"
        await storage.save()
        await query.edit_message_text(t(lang, "weather_usage"))
    elif data == "tool_calc":
        user["state"] = "awaiting_calc"
        await storage.save()
        await query.edit_message_text(t(lang, "calc_usage"))
    elif data == "tool_password":
        import random, string
        pwd = "".join(random.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(16))
        await query.edit_message_text(t(lang, "pwd_result", pwd=pwd), parse_mode="HTML")
    elif data == "tool_translate":
        user["state"] = "awaiting_translate"
        await storage.save()
        await query.edit_message_text(t(lang, "translate_usage"))


async def keyboard_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    uid = update.effective_user.id
    user = storage.get_user(uid)
    # Save username for creator lookup
    if update.effective_user.username:
        user["username"] = update.effective_user.username
    lang = user.get("language", "ru")
    is_private = update.effective_chat.type == 'private'
    is_group = update.effective_chat.type in ['group', 'supergroup']

    # --- In GROUPS: only respond to @mentions or replies to the bot ---
    if is_group:
        bot_username = (await context.bot.get_me()).username
        is_mention = f"@{bot_username}" in text
        is_reply_to_bot = (
            update.message.reply_to_message and
            update.message.reply_to_message.from_user and
            update.message.reply_to_message.from_user.id == context.bot.id
        )

        if is_mention or is_reply_to_bot:
            # Strip the @mention from the query
            query = text.replace(f"@{bot_username}", "").strip()
            if not query:
                return

            from bot.ai import ai_handler
            msg = await update.message.reply_text(t(lang, "ai_thinking"))
            system = "You are an AI assistant in a group chat. Be concise and helpful. "
            if user.get("disco_mode"):
                system = "You are a fun creative AI in a group chat. Use emojis and humor. Be concise. "
            try:
                response = await ai_handler.generate_response(uid, query, system_prompt=system)
                if len(response) > 4000:
                    for i in range(0, len(response), 4000):
                        await update.message.reply_text(response[i:i+4000])
                    await msg.delete()
                else:
                    await msg.edit_text(response)
            except Exception as e:
                await msg.edit_text(f"❌ {e}")
        # In groups, ignore everything else (don't match keyboard buttons)
        return

    # --- PRIVATE chat: handle keyboard buttons ---
    from bot.i18n import translations
    all_btns = {}
    for key_prefix in ["btn_ai", "btn_mem", "btn_notes", "btn_vip", "btn_settings", "btn_games", "btn_tools", "btn_lang"]:
        all_btns[key_prefix] = [tr[key_prefix] for tr in translations.values() if key_prefix in tr]

    if text in all_btns.get("btn_ai", []):
        await update.message.reply_text(t(lang, "ai_no_query"))
    elif text in all_btns.get("btn_mem", []):
        from bot.handlers.ai_memory import memorylist_command
        await memorylist_command(update, context)
    elif text in all_btns.get("btn_notes", []):
        from bot.handlers.notes import notes_command
        await notes_command(update, context)
    elif text in all_btns.get("btn_vip", []):
        await update.message.reply_text(get_text(lang, "vip_menu"), parse_mode="HTML", reply_markup=get_vip_keyboard(lang))
    elif text in all_btns.get("btn_settings", []):
        await update.message.reply_text(get_text(lang, "settings_menu"), parse_mode="HTML", reply_markup=get_settings_keyboard(lang))
    elif text in all_btns.get("btn_games", []):
        await update.message.reply_text(get_text(lang, "games_menu"), parse_mode="HTML", reply_markup=get_games_keyboard(lang))
    elif text in all_btns.get("btn_tools", []):
        await update.message.reply_text(get_text(lang, "tools_menu"), parse_mode="HTML", reply_markup=get_tools_keyboard(lang))
    elif text in all_btns.get("btn_lang", []):
        await update.message.reply_text("🌐", reply_markup=get_lang_keyboard())
    else:
        # Private chat: handle states or fallback to AI
        if not text.startswith('/'):
            state = user.get("state")

            if state == "awaiting_generate_prompt":
                user["state"] = None
                await storage.save()
                context.args = text.split()
                from bot.handlers.media import generate_command
                await generate_command(update, context)
                return
            elif state == "awaiting_setprovider":
                user["state"] = None
                p = text.strip().lower()
                from bot.ai import PROVIDERS
                if p in PROVIDERS:
                    user["ai_provider"] = p
                    await storage.save()
                    await update.message.reply_text(t(lang, "provider_set", provider=p), parse_mode="HTML")
                else:
                    await update.message.reply_text(t(lang, "provider_unknown", list=', '.join(PROVIDERS)))
                return
            elif state == "awaiting_setkey":
                user["state"] = None
                parts = text.strip().split(maxsplit=1)
                if len(parts) == 2:
                    prov, key = parts[0].lower(), parts[1]
                    from bot.ai import PROVIDERS
                    if prov in PROVIDERS:
                        user["api_keys"][prov] = key
                        await storage.save()
                        try: await update.message.delete()
                        except: pass
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=t(lang, "key_saved", provider=prov), parse_mode="HTML")
                    else:
                        await update.message.reply_text(t(lang, "provider_unknown", list=', '.join(PROVIDERS)))
                else:
                    await update.message.reply_text("❌ Format: <code>provider key</code>", parse_mode="HTML")
                return
            elif state == "awaiting_setmodel":
                user["state"] = None
                user["ai_model"] = text.strip()
                await storage.save()
                await update.message.reply_text(t(lang, "model_set", model=text.strip()), parse_mode="HTML")
                return
            elif state == "awaiting_time_city":
                user["state"] = None
                await storage.save()
                context.args = text.split()
                from bot.handlers.utils import time_command
                await time_command(update, context)
                return
            elif state == "awaiting_weather_city":
                user["state"] = None
                await storage.save()
                context.args = text.split()
                from bot.handlers.utils import weather_command
                await weather_command(update, context)
                return
            elif state == "awaiting_calc":
                user["state"] = None
                await storage.save()
                context.args = text.split()
                from bot.handlers.utils import calc_command
                await calc_command(update, context)
                return
            elif state == "awaiting_translate":
                user["state"] = None
                await storage.save()
                context.args = text.split()
                from bot.handlers.groups import translate_command
                await translate_command(update, context)
                return

            # Default: AI chat in private
            from bot.ai import ai_handler
            user["stats"]["msgs"] = user["stats"].get("msgs", 0) + 1
            msg = await update.message.reply_text(t(lang, "ai_thinking"))
            system = "You are an AI assistant. "
            if user.get("disco_mode"):
                system = "You are a fun creative AI. Use emojis and humor. "
            if user.get("memory"):
                system += "Memory:\n"
                for k, v in user["memory"].items():
                    system += f"- {k}: {v}\n"
            try:
                response = await ai_handler.generate_response(uid, text, system_prompt=system)
                if len(response) > 4000:
                    for i in range(0, len(response), 4000):
                        await update.message.reply_text(response[i:i+4000])
                    await msg.delete()
                else:
                    await msg.edit_text(response)
            except Exception as e:
                await msg.edit_text(f"❌ {e}")
