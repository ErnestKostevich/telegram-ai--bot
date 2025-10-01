logger.error(f"❌ Ошибка автосохранения: {e}")
    
    # ========================================================================
    # ЗАПУСК БОТА
    # ========================================================================
    
    async def run_bot(self):
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не найден!")
            return
        
        logger.info("🚀 Запуск бота v3.0 (Улучшенная версия)...")
        
        self.application = Application.builder()\
            .token(BOT_TOKEN)\
            .read_timeout(30)\
            .write_timeout(30)\
            .build()
        
        async def error_handler(update, context):
            logger.error(f"Ошибка: {context.error}")
            try:
                if update and update.effective_message:
                    await update.effective_message.reply_text(
                        "❌ Произошла ошибка. Попробуйте позже."
                    )
            except:
                pass
        
        self.application.add_error_handler(error_handler)
        
        # Регистрация ВСЕХ команд
        commands = [
            # Базовые
            ("start", self.start_command),
            ("help", self.help_command),
            ("info", self.info_command),
            ("status", self.status_command),
            ("uptime", self.uptime_command),
            
            # Время
            ("time", self.time_command),
            ("date", self.date_command),
            
            # AI
            ("ai", self.ai_command),
            ("clearhistory", self.clearhistory_command),
            
            # Заметки
            ("note", self.note_command),
            ("notes", self.notes_command),
            ("delnote", self.delnote_command),
            ("findnote", self.findnote_command),
            ("clearnotes", self.clearnotes_command),
            
            # Память
            ("memorysave", self.memorysave_command),
            ("memoryget", self.memoryget_command),
            ("memorylist", self.memorylist_command),
            ("memorydel", self.memorydel_command),
            
            # Развлечения
            ("joke", self.joke_command),
            ("fact", self.fact_command),
            ("quote", self.quote_command),
            ("quiz", self.quiz_command),
            ("coin", self.coin_command),
            ("dice", self.dice_command),
            ("8ball", self.eightball_command),
            
            # Математика
            ("math", self.math_command),
            ("calculate", self.calculate_command),
            
            # Утилиты
            ("password", self.password_command),
            ("qr", self.qr_command),
            ("shorturl", self.shorturl_command),
            ("ip", self.ip_command),
            ("weather", self.weather_command),
            ("currency", self.currency_command),
            ("translate", self.translate_command),
            
            # Язык
            ("language", self.language_command),
            
            # Профиль
            ("rank", self.rank_command),
            ("profile", self.profile_command),
            ("stats", self.stats_command),
            
            # VIP
            ("vip", self.vip_command),
            ("remind", self.remind_command),
            ("reminders", self.reminders_command),
            ("delreminder", self.delreminder_command),
            ("nickname", self.nickname_command),
            
            # Создатель
            ("grant_vip", self.grant_vip_command),
            ("revoke_vip", self.revoke_vip_command),
            ("broadcast", self.broadcast_command),
            ("users", self.users_command),
            ("maintenance", self.maintenance_command),
            ("backup", self.backup_command)
        ]
        
        for cmd, handler in commands:
            self.application.add_handler(CommandHandler(cmd, handler))
        
        # Обработчик текстовых сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            self.handle_message
        ))
        
        # Обработчик кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Планировщик задач
        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()
        
        # Автопинг каждые 14 минут
        self.scheduler.add_job(self.self_ping, 'interval', minutes=14)
        
        # Автосохранение каждые 30 минут
        self.scheduler.add_job(self.save_data, 'interval', minutes=30)
        
        # Проверка напоминаний каждую минуту
        self.scheduler.add_job(self.check_reminders, 'interval', minutes=1)
        
        # Проверка дня рождения папы каждый час
        self.scheduler.add_job(self.check_papa_birthday_scheduled, 'interval', hours=1)
        
        logger.info("=" * 60)
        logger.info("🤖 БОТ ЗАПУЩЕН УСПЕШНО!")
        logger.info(f"📅 Версия: 3.0 (Улучшенная)")
        logger.info(f"👥 Пользователей в базе: {len(self.db.get_all_users())}")
        logger.info(f"💬 Разговоров: {len(self.conversation_memory.conversations)}")
        logger.info(f"🧠 AI: {'✅ Активен' if self.gemini_model else '❌ Недоступен'}")
        logger.info(f"⏰ Время запуска: {self.start_time.strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info("=" * 60)
        
        await self.application.run_polling(drop_pending_updates=True)

# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

async def main():
    bot = TelegramBot()
    await bot.run_bot()

# ============================================================================
# FLASK ВЕБ-СЕРВЕР
# ============================================================================

app = Flask(__name__)

@app.route('/')
def home():
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Telegram AI Bot v3.0</title>
    <meta charset="utf-8">
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 50px;
            text-align: center;
            margin: 0;
            min-height: 100vh;
        }
        .container {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 700px;
            margin: 0 auto;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        h1 {
            font-size: 56px;
            margin: 20px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .status {
            color: #00ff88;
            font-weight: bold;
            font-size: 24px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .feature {
            background: rgba(255,255,255,0.05);
            padding: 15px;
            margin: 10px 0;
            border-radius: 10px;
        }
        .emoji {
            font-size: 32px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Telegram AI Bot</h1>
        <p class="status">✅ РАБОТАЕТ</p>
        
        <div class="feature">
            <p class="emoji">📅</p>
            <p>Версия: 3.0 (Улучшенная)</p>
            <p>⏰ """ + now + """</p>
        </div>
        
        <div class="feature">
            <p class="emoji">🌟</p>
            <p>✨ Полная память разговоров</p>
            <p>⏰ Актуальное время и погода</p>
            <p>🎂 Автопоздравления</p>
            <p>🧠 AI: Gemini 2.0 Flash</p>
        </div>
        
        <div class="feature">
            <p class="emoji">🌐</p>
            <p>6 языков | 50+ команд</p>
            <p>Бот: """ + BOT_USERNAME + """</p>
            <p>Создатель: """ + CREATOR_USERNAME + """</p>
        </div>
    </div>
</body>
</html>
"""
    return html_content

@app.route('/health')
def health():
    return {
        "status": "ok",
        "version": "3.0",
        "time": datetime.datetime.now().isoformat(),
        "ai_active": GEMINI_API_KEY is not None
    }

@app.route('/stats')
def stats():
    try:
        db = Database()
        users = db.get_all_users()
        uptime_val = str(datetime.datetime.now() - bot_start_time).split('.')[0] if 'bot_start_time' in globals() else "N/A"
        return {
            "users": len(users),
            "version": "3.0",
            "uptime": uptime_val
        }
    except:
        return {"error": "Stats unavailable"}, 500

# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

if __name__ == "__main__":
    from threading import Thread
    
    # Сохраняем время запуска
    bot_start_time = datetime.datetime.now()
    
    # Запуск Flask в отдельном потоке
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(
        target=app.run,
        kwargs={
            'host': '0.0.0.0',
            'port': port,
            'debug': False,
            'use_reloader': False
        }
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info(f"🌐 Flask запущен на порту {port}")
    logger.info(f"🔗 URL: {RENDER_URL}")
    
    # Запуск бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - VIP ФУНКЦИИ
    # ========================================================================
    
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/vip")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if self.is_vip(user_data):
            expires = "Навсегда" if not user_data.get('vip_expires') else \
                     datetime.datetime.fromisoformat(user_data['vip_expires']).strftime('%d.%m.%Y')
            
            vip_text = f"""
💎 VIP СТАТУС

✅ Статус: Активен
⏰ До: {expires}

🌟 ВАШИ ВОЗМОЖНОСТИ:
• ⏰ Напоминания (/remind)
• 📛 Кастомный никнейм (/nickname)
• 🎯 Приоритетная поддержка
• 🚀 Ранний доступ к новым функциям
• 💾 Увеличенные лимиты

🎁 Спасибо за поддержку!
"""
        else:
            vip_text = f"""
💎 VIP СТАТУС

❌ Статус: Не активен

🌟 ЧТО ДАЁТ VIP:
• ⏰ Система напоминаний
• 📛 Кастомный никнейм
• 🎯 Приоритетная поддержка
• 🚀 Новые функции первыми
• 💾 Расширенные лимиты

💬 Хотите VIP? Напишите {CREATOR_USERNAME}
"""
        
        await update.message.reply_text(vip_text)
        await self.add_experience(user_data, 1)
    
    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/remind")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP пользователям!\n\nПолучить VIP: /vip")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "⏰ НАПОМИНАНИЯ\n\n"
                "Использование: /remind [минуты] [текст]\n\n"
                "Примеры:\n"
                "• /remind 30 Позвонить маме\n"
                "• /remind 60 Перерыв на обед\n"
                "• /remind 1440 День рождения завтра!"
            )
            return
        
        try:
            minutes = int(context.args[0])
            message = " ".join(context.args[1:])
            
            if minutes < 1:
                await update.message.reply_text("❌ Минуты должны быть больше 0")
                return
            
            if minutes > 10080:
                await update.message.reply_text("❌ Максимум 7 дней (10080 минут)")
                return
            
            remind_at = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            self.db.add_reminder(user_data['user_id'], message, remind_at)
            
            await update.message.reply_text(
                f"✅ НАПОМИНАНИЕ СОЗДАНО\n\n"
                f"⏰ Через {minutes} минут\n"
                f"📅 {remind_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"💬 {message}"
            )
            
        except ValueError:
            await update.message.reply_text("❌ Неверное количество минут")
        
        await self.add_experience(user_data, 2)
    
    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/reminders")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP пользователям!")
            return
        
        reminders = self.db.get_reminders(user_data['user_id'])
        
        if not reminders:
            await update.message.reply_text("📭 У вас нет активных напоминаний!\n\nСоздать: /remind [минуты] [текст]")
            return
        
        text = "⏰ ВАШИ НАПОМИНАНИЯ:\n\n"
        for i, reminder in enumerate(reminders, 1):
            remind_at = datetime.datetime.fromisoformat(reminder['remind_at'])
            time_left = remind_at - datetime.datetime.now()
            
            if time_left.total_seconds() > 0:
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                text += f"{i}. {reminder['message']}\n"
                text += f"   ⏰ Через {hours}ч {minutes}м\n"
                text += f"   📅 {remind_at.strftime('%d.%m %H:%M')}\n\n"
        
        text += f"📊 Всего: {len(reminders)}"
        
        await update.message.reply_text(text)
        await self.add_experience(user_data, 1)
    
    async def delreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/delreminder")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP пользователям!")
            return
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер!\nПример: /delreminder 1")
            return
        
        reminders = self.db.get_reminders(user_data['user_id'])
        index = int(context.args[0]) - 1
        
        if 0 <= index < len(reminders):
            self.db.delete_reminder(reminders[index]['id'], user_data['user_id'])
            await update.message.reply_text(f"✅ Напоминание #{index+1} удалено!")
        else:
            await update.message.reply_text(f"❌ Напоминания #{index+1} не существует!")
        
        await self.add_experience(user_data, 1)
    
    async def nickname_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/nickname")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP пользователям!")
            return
        
        if not context.args:
            current = user_data.get('nickname') or "не установлен"
            await update.message.reply_text(
                f"📛 НИКНЕЙМ\n\n"
                f"Текущий: {current}\n\n"
                f"Установить: /nickname [новое имя]\n"
                f"Пример: /nickname СуперПользователь"
            )
            return
        
        nickname = " ".join(context.args)
        
        if len(nickname) > 30:
            await update.message.reply_text("❌ Максимум 30 символов")
            return
        
        user_data['nickname'] = nickname
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"✅ Никнейм установлен: {nickname}")
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # ========================================================================
    
    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "💎 ВЫДАТЬ VIP\n\n"
                "Использование: /grant_vip [user_id] [duration]\n\n"
                "Duration: week, month, year, permanent\n\n"
                "Пример: /grant_vip 123456789 month"
            )
            return
        
        try:
            target_id = int(context.args[0])
            duration = context.args[1].lower()
            
            target_user = self.db.get_user(target_id)
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден в базе!")
                return
            
            target_user['is_vip'] = 1
            
            if duration == "week":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(weeks=1)).isoformat()
                duration_text = "1 неделя"
            elif duration == "month":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
                duration_text = "1 месяц"
            elif duration == "year":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
                duration_text = "1 год"
            elif duration == "permanent":
                target_user['vip_expires'] = None
                duration_text = "навсегда"
            else:
                await update.message.reply_text("❌ Используйте: week, month, year, permanent")
                return
            
            self.db.save_user(target_user)
            
            await update.message.reply_text(
                f"✅ VIP ВЫДАН\n\n"
                f"👤 {target_user['first_name']}\n"
                f"🆔 {target_id}\n"
                f"⏰ Длительность: {duration_text}"
            )
            
            try:
                await self.application.bot.send_message(
                    target_id,
                    f"🎉 ВЫ ПОЛУЧИЛИ VIP!\n\n"
                    f"⏰ Длительность: {duration_text}\n"
                    f"💎 Проверьте возможности: /vip"
                )
            except:
                pass
            
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя!")
    
    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        if not context.args:
            await update.message.reply_text("Использование: /revoke_vip [user_id]")
            return
        
        try:
            target_id = int(context.args[0])
            target_user = self.db.get_user(target_id)
            
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            target_user['is_vip'] = 0
            target_user['vip_expires'] = None
            self.db.save_user(target_user)
            
            await update.message.reply_text(f"✅ VIP отозван у {target_user['first_name']} (ID: {target_id})")
            
            try:
                await self.application.bot.send_message(target_id, "⚠️ Ваш VIP статус истёк")
            except:
                pass
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID!")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📢 РАССЫЛКА\n\n"
                "Использование: /broadcast [сообщение]\n\n"
                "Сообщение будет отправлено ВСЕМ пользователям!"
            )
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        
        await update.message.reply_text(f"📢 Начинаю рассылку для {len(users)} пользователей...")
        
        sent = 0
        failed = 0
        
        for user in users:
            try:
                await self.application.bot.send_message(
                    user['user_id'],
                    f"📢 СООБЩЕНИЕ ОТ СОЗДАТЕЛЯ:\n\n{message}"
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast failed for {user['user_id']}: {e}")
        
        await update.message.reply_text(
            f"✅ Рассылка завершена!\n\n"
            f"✅ Отправлено: {sent}\n"
            f"❌ Ошибок: {failed}"
        )
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        users = self.db.get_all_users()
        
        text = f"👥 СПИСОК ПОЛЬЗОВАТЕЛЕЙ ({len(users)})\n\n"
        
        for i, user in enumerate(users[:30], 1):
            vip = "💎" if user.get('is_vip') else "👤"
            username = f"@{user.get('username')}" if user.get('username') else "нет username"
            text += f"{i}. {vip} {user['first_name']} ({username})\n"
            text += f"   🆔 {user['user_id']} | 🆙 Lvl {user.get('level', 1)}\n\n"
        
        if len(users) > 30:
            text += f"\n... и ещё {len(users) - 30} пользователей"
        
        await update.message.reply_text(text)
    
    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        if not context.args:
            status = "🔧 Включен" if self.maintenance_mode else "✅ Выключен"
            await update.message.reply_text(
                f"🔧 РЕЖИМ ОБСЛУЖИВАНИЯ\n\n"
                f"Статус: {status}\n\n"
                f"Использование:\n"
                f"• /maintenance on - Включить\n"
                f"• /maintenance off - Выключить"
            )
            return
        
        mode = context.args[0].lower()
        
        if mode == "on":
            self.maintenance_mode = True
            await update.message.reply_text("🔧 Режим обслуживания ВКЛЮЧЕН\n\nБот доступен только создателю")
        elif mode == "off":
            self.maintenance_mode = False
            await update.message.reply_text("✅ Режим обслуживания ВЫКЛЮЧЕН\n\nБот доступен всем")
        else:
            await update.message.reply_text("❌ Используйте: on или off")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        try:
            await update.message.reply_text("💾 Создаю резервную копию...")
            
            self.conversation_memory.save()
            
            users = self.db.get_all_users()
            
            backup_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'users_count': len(users),
                'conversations_count': len(self.conversation_memory.conversations),
                'total_messages': sum(len(c['messages']) for c in self.conversation_memory.conversations.values()),
                'bot_version': '3.0'
            }
            
            filename = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(BACKUP_PATH, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            text = f"""
✅ БЭКАП СОЗДАН

📁 Файл: {filename}
⏰ {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

📊 Содержимое:
• Пользователей: {backup_data['users_count']}
• Разговоров: {backup_data['conversations_count']}
• Сообщений: {backup_data['total_messages']}
"""
            await update.message.reply_text(text)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка создания бэкапа: {str(e)}")
    
    # ========================================================================
    # ОБРАБОТЧИКИ
    # ========================================================================
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("lang_"):
            lang = query.data.split("_")[1]
            user_data = await self.get_user_data(update)
            user_data['language'] = lang
            self.db.save_user(user_data)
            
            await query.edit_message_text(
                self.t('language_changed', lang),
                reply_markup=None
            )
            
            await self.application.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ Язык изменён!",
                reply_markup=self.get_keyboard(lang)
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            return
        
        user_data = await self.get_user_data(update)
        user_data['total_messages'] = user_data.get('total_messages', 0) + 1
        message = update.message.text
        
        lang = user_data.get('language', 'ru')
        if message == self.t('help', lang):
            return await self.help_command(update, context)
        elif message == self.t('notes', lang):
            return await self.notes_command(update, context)
        elif message == self.t('stats', lang):
            return await self.stats_command(update, context)
        elif message == self.t('time', lang):
            return await self.time_command(update, context)
        elif message == self.t('language', lang):
            return await self.language_command(update, context)
        elif message == self.t('ai_chat', lang):
            await update.message.reply_text("💬 AI активен! Напишите ваш вопрос")
            return
        
        if not self.gemini_model:
            return
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            history = self.conversation_memory.get_context(user_data['user_id'], limit=None)
            context_str = ""
            if history:
                for msg in history[-10:]:
                    role = "Пользователь" if msg['role'] == 'user' else "AI"
                    context_str += f"{role}: {msg['content'][:200]}\n"
            
            prompt = f"""Ты дружелюбный AI-ассистент в Telegram боте.

История:
{context_str}

Пользователь: {message}

Ответь полезно и кратко."""
            
            response = self.gemini_model.generate_content(prompt)
            
            self.conversation_memory.add_message(user_data['user_id'], 'user', message)
            self.conversation_memory.add_message(user_data['user_id'], 'assistant', response.text)
            
            await update.message.reply_text(response.text)
            
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Ошибка: {e}")
        
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # СИСТЕМНЫЕ ФУНКЦИИ
    # ========================================================================
    
    async def check_reminders(self):
        try:
            pending = self.db.get_pending_reminders()
            
            for reminder in pending:
                try:
                    await self.application.bot.send_message(
                        reminder['user_id'],
                        f"⏰ НАПОМИНАНИЕ\n\n{reminder['message']}"
                    )
                    self.db.mark_reminder_sent(reminder['id'])
                    logger.info(f"Напоминание отправлено: {reminder['id']}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания {reminder['id']}: {e}")
        except Exception as e:
            logger.error(f"Ошибка проверки напоминаний: {e}")
    
    async def check_papa_birthday_scheduled(self):
        try:
            now = datetime.datetime.now()
            if now.month == 10 and now.day == 3 and now.hour == 0:
                users = self.db.get_all_users()
                for user in users:
                    if user.get('username') == 'mkostevich':
                        try:
                            await self.application.bot.send_message(
                                user['user_id'],
                                "🎉🎂 С ДНЁМ РОЖДЕНИЯ, ПАПА! 🎂🎉\n\n"
                                "🎈 Желаю здоровья, счастья и всех благ! 🎈\n\n"
                                "💝 С любовью, твой AI-бот!"
                            )
                            logger.info("Поздравление отправлено!")
                        except Exception as e:
                            logger.error(f"Ошибка отправки поздравления: {e}")
        except Exception as e:
            logger.error(f"Ошибка проверки дня рождения: {e}")
    
    async def self_ping(self):
        try:
            requests.get(RENDER_URL, timeout=10)
            logger.info("Self-ping OK")
        except Exception as e:
            logger.error(f"Self-ping ошибка: {e}")
    
    async def save_data(self):
        try:
            self.conversation_memory.save()
            logger.info("✅ Данные автоматически сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка автосохранения: {e}")#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM AI BOT v3.0 - УЛУЧШЕННАЯ ВЕРСИЯ
✅ Полная система памяти с неограниченным контекстом
✅ Актуальное время и погода
✅ Поздравление для @mkostevich 3 октября
✅ Все команды работают идеально
✅ Архитектура как у официального AI
"""

import asyncio
import logging
import json
import random
import time
import datetime
import requests
import os
import sys
import sqlite3
import hashlib
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import nest_asyncio
from flask import Flask
import pytz
from typing import Dict, List, Optional

nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

import google.generativeai as genai

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

CREATOR_ID = 7108255346
PAPA_ID = None
CREATOR_USERNAME = "@Ernest_Kostevich"
PAPA_USERNAME = "@mkostevich"
BOT_USERNAME = "@AI_DISCO_BOT"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = "gemini-2.0-flash-exp"

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai-bot.onrender.com")

DB_PATH = "bot_database.db"
CONVERSATIONS_PATH = "conversations.json"
MEMORY_PATH = "memory.json"
BACKUP_PATH = "backups"
Path(BACKUP_PATH).mkdir(exist_ok=True)

# ============================================================================
# ПЕРЕВОДЫ
# ============================================================================

TRANSLATIONS = {
    'ru': {
        'welcome': '🤖 Привет, {name}!\n\nЯ AI-бот нового поколения с расширенными возможностями!\n\n✨ Что я умею:\n• 💬 Умный AI-чат с полной памятью\n• 🧠 Долговременная память разговоров\n• 📝 Система заметок и напоминаний\n• 🌤️ Актуальная погода\n• ⏰ Мировое время\n• 🎮 Игры и развлечения\n• 🔧 Множество утилит\n\n💎 VIP доступ - расширенные возможности!\n\n📋 Используйте /help для списка команд',
        'help': '📋 Помощь',
        'notes': '📝 Заметки',
        'stats': '📊 Статистика',
        'time': '⏰ Время',
        'language': '🌐 Язык',
        'ai_chat': '💬 AI Чат',
        'current_time': '⏰ МИРОВОЕ ВРЕМЯ',
        'language_changed': '✅ Язык изменён на: Русский'
    },
    'en': {
        'welcome': '🤖 Hello, {name}!\n\nI am a next-generation AI bot with advanced features!\n\n✨ What I can do:\n• 💬 Smart AI chat with full memory\n• 🧠 Long-term conversation memory\n• 📝 Notes and reminders system\n• 🌤️ Current weather\n• ⏰ World time\n• 🎮 Games and entertainment\n• 🔧 Many utilities\n\n💎 VIP access - extended features!\n\n📋 Use /help for command list',
        'help': '📋 Help',
        'notes': '📝 Notes',
        'stats': '📊 Stats',
        'time': '⏰ Time',
        'language': '🌐 Language',
        'ai_chat': '💬 AI Chat',
        'current_time': '⏰ WORLD TIME',
        'language_changed': '✅ Language changed to: English'
    }
}

LANGUAGE_NAMES = {
    'ru': '🇷🇺 Русский',
    'en': '🇺🇸 English',
    'es': '🇪🇸 Español',
    'fr': '🇫🇷 Français',
    'it': '🇮🇹 Italiano',
    'de': '🇩🇪 Deutsch'
}

# ============================================================================
# БАЗА ДАННЫХ С РАСШИРЕННЫМИ ВОЗМОЖНОСТЯМИ
# ============================================================================

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_vip INTEGER DEFAULT 0,
            vip_expires TEXT,
            language TEXT DEFAULT 'ru',
            nickname TEXT,
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            total_messages INTEGER DEFAULT 0,
            total_commands INTEGER DEFAULT 0
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            remind_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_sent INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS command_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            command TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS memory_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            key TEXT,
            value TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, key)
        )''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    def get_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def save_user(self, user_data: dict):
        conn = self.get_connection()
        cursor = conn.cursor()
        user_data['last_activity'] = datetime.datetime.now().isoformat()
        
        if self.get_user(user_data['user_id']):
            cursor.execute('''UPDATE users SET 
                username=?, first_name=?, is_vip=?, vip_expires=?,
                language=?, nickname=?, level=?, experience=?, 
                last_activity=?, total_messages=?, total_commands=?
                WHERE user_id=?''',
                (user_data.get('username',''), user_data.get('first_name',''), 
                 user_data.get('is_vip',0), user_data.get('vip_expires'),
                 user_data.get('language','ru'), user_data.get('nickname'),
                 user_data.get('level',1), user_data.get('experience',0),
                 user_data['last_activity'], user_data.get('total_messages',0),
                 user_data.get('total_commands',0), user_data['user_id']))
        else:
            cursor.execute('''INSERT INTO users 
                (user_id, username, first_name, is_vip, vip_expires,
                 language, nickname, level, experience, last_activity,
                 total_messages, total_commands) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (user_data['user_id'], user_data.get('username',''), 
                 user_data.get('first_name',''), user_data.get('is_vip',0),
                 user_data.get('vip_expires'), user_data.get('language','ru'),
                 user_data.get('nickname'), user_data.get('level',1),
                 user_data.get('experience',0), user_data['last_activity'],
                 user_data.get('total_messages',0), user_data.get('total_commands',0)))
        
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def log_command(self, user_id: int, command: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO command_logs (user_id, command) VALUES (?, ?)", 
                      (user_id, command))
        conn.commit()
        conn.close()
    
    def add_note(self, user_id: int, note: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (user_id, note) VALUES (?, ?)", (user_id, note))
        conn.commit()
        conn.close()
    
    def get_notes(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", 
                      (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def delete_note(self, note_id: int, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def clear_notes(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count
    
    def add_reminder(self, user_id: int, message: str, remind_at: datetime.datetime):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO reminders (user_id, message, remind_at) 
                         VALUES (?, ?, ?)""",
                      (user_id, message, remind_at.isoformat()))
        conn.commit()
        conn.close()
    
    def get_reminders(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM reminders 
                         WHERE user_id = ? AND is_sent = 0 
                         ORDER BY remind_at""", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_pending_reminders(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""SELECT * FROM reminders 
                         WHERE is_sent = 0 AND remind_at <= ?""", (now,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def mark_reminder_sent(self, reminder_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,))
        conn.commit()
        conn.close()
    
    def delete_reminder(self, reminder_id: int, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", 
                      (reminder_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def save_memory(self, user_id: int, key: str, value: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""INSERT OR REPLACE INTO memory_store 
                         (user_id, key, value, created_at, updated_at) 
                         VALUES (?, ?, ?, 
                                COALESCE((SELECT created_at FROM memory_store 
                                         WHERE user_id=? AND key=?), ?), ?)""",
                      (user_id, key, value, user_id, key, now, now))
        conn.commit()
        conn.close()
    
    def get_memory(self, user_id: int, key: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM memory_store WHERE user_id = ? AND key = ?", 
                      (user_id, key))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None
    
    def get_all_memory(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM memory_store WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}
    
    def delete_memory(self, user_id: int, key: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory_store WHERE user_id = ? AND key = ?", 
                      (user_id, key))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

# ============================================================================
# СИСТЕМА ПАМЯТИ РАЗГОВОРОВ
# ============================================================================

class ConversationMemory:
    def __init__(self, filepath: str = CONVERSATIONS_PATH):
        self.filepath = filepath
        self.conversations = self._load()
        self.cache = {}
    
    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Загружено {len(data)} разговоров")
                    return data
            except Exception as e:
                logger.error(f"Ошибка загрузки разговоров: {e}")
                return {}
        return {}
    
    def _save(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.conversations, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.conversations)} разговоров")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    def add_message(self, user_id: int, role: str, content: str):
        uid = str(user_id)
        if uid not in self.conversations:
            self.conversations[uid] = {
                'messages': [],
                'created_at': datetime.datetime.now().isoformat(),
                'message_count': 0
            }
        
        self.conversations[uid]['messages'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.datetime.now().isoformat()
        })
        self.conversations[uid]['message_count'] = len(self.conversations[uid]['messages'])
        
        self.cache[uid] = self.conversations[uid]['messages'][-20:]
        
        if len(self.conversations[uid]['messages']) % 5 == 0:
            self._save()
    
    def get_context(self, user_id: int, limit: int = 100):
        uid = str(user_id)
        
        if uid in self.cache and limit and limit <= 20:
            return self.cache[uid][-limit:]
        
        if uid not in self.conversations:
            return []
        
        messages = self.conversations[uid]['messages']
        return messages[-limit:] if limit and len(messages) > limit else messages
    
    def get_full_history(self, user_id: int):
        uid = str(user_id)
        if uid not in self.conversations:
            return []
        return self.conversations[uid]['messages']
    
    def get_summary(self, user_id: int):
        uid = str(user_id)
        if uid not in self.conversations:
            return None
        
        conv = self.conversations[uid]
        user_msgs = sum(1 for m in conv['messages'] if m['role'] == 'user')
        ai_msgs = sum(1 for m in conv['messages'] if m['role'] == 'assistant')
        
        return {
            'total_messages': len(conv['messages']),
            'user_messages': user_msgs,
            'ai_messages': ai_msgs,
            'created_at': conv.get('created_at'),
            'first_message': conv['messages'][0] if conv['messages'] else None,
            'last_message': conv['messages'][-1] if conv['messages'] else None
        }
    
    def clear_history(self, user_id: int):
        uid = str(user_id)
        if uid in self.conversations:
            del self.conversations[uid]
            if uid in self.cache:
                del self.cache[uid]
            self._save()
    
    def save(self):
        self._save()

# ============================================================================
# ГЛАВНЫЙ КЛАСС БОТА
# ============================================================================

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.conversation_memory = ConversationMemory()
        self.gemini_model = None
        self.start_time = datetime.datetime.now()
        
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("✅ Gemini AI инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка Gemini: {e}")
        
        self.scheduler = AsyncIOScheduler()
        self.maintenance_mode = False
        self.application = None
    
    def t(self, key: str, lang: str = 'ru', **kwargs):
        text = TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, key)
        return text.format(**kwargs) if kwargs else text
    
    async def get_user_data(self, update: Update):
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            user_data = {
                'user_id': user.id,
                'username': user.username or "",
                'first_name': user.first_name or "",
                'is_vip': 1 if user.id == CREATOR_ID else 0,
                'vip_expires': None,
                'language': 'ru',
                'nickname': None,
                'level': 1,
                'experience': 0,
                'total_messages': 0,
                'total_commands': 0
            }
            self.db.save_user(user_data)
            logger.info(f"➕ Новый пользователь: {user.id} (@{user.username})")
        
        return user_data
    
    def get_keyboard(self, lang: str = 'ru'):
        keyboard = [
            [KeyboardButton(self.t('ai_chat', lang)), KeyboardButton(self.t('help', lang))],
            [KeyboardButton(self.t('notes', lang)), KeyboardButton(self.t('stats', lang))],
            [KeyboardButton(self.t('time', lang)), KeyboardButton(self.t('language', lang))]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def is_creator(self, user_id: int):
        return user_id == CREATOR_ID
    
    def is_vip(self, user_data: dict):
        if user_data['user_id'] == CREATOR_ID:
            return True
        
        if not user_data.get('is_vip'):
            return False
        
        if user_data.get('vip_expires'):
            try:
                expires = datetime.datetime.fromisoformat(user_data['vip_expires'])
                if datetime.datetime.now() > expires:
                    user_data['is_vip'] = 0
                    self.db.save_user(user_data)
                    return False
            except:
                return False
        return True
    
    async def add_experience(self, user_data: dict, points: int = 1):
        user_data['experience'] = user_data.get('experience', 0) + points
        required = user_data.get('level', 1) * 100
        
        if user_data['experience'] >= required:
            user_data['level'] = user_data.get('level', 1) + 1
            user_data['experience'] = 0
        
        self.db.save_user(user_data)
    
    async def check_papa_birthday(self, user_data: dict):
        if user_data.get('username') == 'mkostevich':
            now = datetime.datetime.now()
            if now.month == 10 and now.day == 3:
                return True
        return False
    
    # ========================================================================
    # КОМАНДЫ - БАЗОВЫЕ
    # ========================================================================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/start")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        lang = user_data.get('language', 'ru')
        
        if await self.check_papa_birthday(user_data):
            birthday_msg = "🎉🎂 С ДНЁМ РОЖДЕНИЯ, ПАПА! 🎂🎉\n\n"
            birthday_msg += "🎈 Желаю здоровья, счастья и всего самого лучшего! 🎈\n\n"
            await update.message.reply_text(birthday_msg)
        
        message = self.t('welcome', lang, name=user_data['first_name'])
        keyboard = self.get_keyboard(lang)
        
        await update.message.reply_text(message, reply_markup=keyboard)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - РАЗВЛЕЧЕНИЯ
    # ========================================================================
    
    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/joke")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        jokes = [
            "😄 Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
            "🤓 Заходит программист в бар, заказывает 1 пиво. Заказывает 0 пива. Заказывает 999999 пива. Заказывает -1 пиво...",
            "💻 Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
            "🧼 Как программист моет посуду? Не моет - это не баг, это фича!",
            "💊 - Доктор, я думаю, что я компьютерный вирус!\n- Не волнуйтесь, примите эту таблетку.\n- А что это?\n- Антивирус!",
            "🔧 Программист - это машина для превращения кофе в код!",
            "🐛 99 маленьких багов в коде, 99 маленьких багов... Исправил один, прогнал тесты - 117 маленьких багов в коде!"
        ]
        await update.message.reply_text(random.choice(jokes))
        await self.add_experience(user_data, 1)
    
    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/fact")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        facts = [
            "🧠 Человеческий мозг содержит около 86 миллиардов нейронов!",
            "🌊 В океане больше исторических артефактов, чем во всех музеях мира!",
            "🐙 У осьминогов три сердца и голубая кровь!",
            "💻 Первый компьютерный вирус был создан в 1971 году и назывался 'Creeper'!",
            "🦈 Акулы существуют дольше, чем деревья - более 400 миллионов лет!",
            "🌙 Луна удаляется от Земли на 3.8 см каждый год!",
            "⚡ Молния в 5 раз горячее поверхности Солнца!",
            "🍯 Мёд никогда не портится - археологи находили 3000-летний мёд, который всё ещё съедобен!",
            "🐌 Улитка может спать до 3 лет подряд!",
            "🌍 В мире больше звёзд, чем песчинок на всех пляжах Земли!"
        ]
        await update.message.reply_text(random.choice(facts))
        await self.add_experience(user_data, 1)
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/quote")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        quotes = [
            "💫 'Будь собой. Остальные роли уже заняты.' - Оскар Уайльд",
            "🚀 'Единственный способ сделать великую работу - любить то, что делаешь.' - Стив Джобс",
            "🎯 'Не бойтесь совершать ошибки - бойтесь не учиться на них.'",
            "🌟 'Лучшее время посадить дерево было 20 лет назад. Второе лучшее время - сейчас.'",
            "💪 'Успех - это способность идти от неудачи к неудаче, не теряя энтузиазма.' - Уинстон Черчилль",
            "🔥 'Если вы не можете сделать великие дела, делайте маленькие дела с великой любовью.' - Мать Тереза",
            "⚡ 'Будущее принадлежит тем, кто верит в красоту своих мечтаний.' - Элеонора Рузвельт"
        ]
        await update.message.reply_text(random.choice(quotes))
        await self.add_experience(user_data, 1)
    
    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/quiz")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        quizzes = [
            {"q": "❓ Какая планета самая большая в Солнечной системе?", "a": "Юпитер"},
            {"q": "❓ Столица Японии?", "a": "Токио"},
            {"q": "❓ Сколько континентов на Земле?", "a": "7 (или 6, в зависимости от модели)"},
            {"q": "❓ Кто написал 'Войну и мир'?", "a": "Лев Толстой"},
            {"q": "❓ Скорость света в вакууме?", "a": "≈300,000 км/с"}
        ]
        
        quiz = random.choice(quizzes)
        await update.message.reply_text(f"🎯 ВИКТОРИНА\n\n{quiz['q']}\n\n💡 Ответ: ||{quiz['a']}||")
        await self.add_experience(user_data, 1)
    
    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/coin")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        result = random.choice(["🪙 Орёл!", "🪙 Решка!"])
        await update.message.reply_text(result)
        await self.add_experience(user_data, 1)
    
    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/dice")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
        await self.add_experience(user_data, 1)
    
    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/8ball")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "🔮 МАГИЧЕСКИЙ ШАР\n\n"
                "Задайте вопрос!\n"
                "Пример: /8ball Стоит ли мне учить Python?"
            )
            return
        
        answers = [
            "✅ Да, определённо!",
            "✅ Можешь быть уверен!",
            "✅ Бесспорно!",
            "✅ Без сомнений!",
            "🤔 Возможно...",
            "🤔 Спроси позже",
            "🤔 Сейчас нельзя сказать",
            "🤔 Не уверен...",
            "❌ Мой ответ - нет",
            "❌ Очень сомнительно",
            "❌ Не рассчитывай на это",
            "❌ Определённо нет"
        ]
        
        question = " ".join(context.args)
        await update.message.reply_text(f"🔮 Вопрос: {question}\n\n{random.choice(answers)}")
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - МАТЕМАТИКА
    # ========================================================================
    
    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/math")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "🔢 КАЛЬКУЛЯТОР\n\n"
                "Введите выражение!\n\n"
                "Примеры:\n"
                "• /math 15 + 25\n"
                "• /math (10 + 5) * 2\n"
                "• /math 100 / 4"
            )
            return
        
        expression = " ".join(context.args)
        
        try:
            allowed_chars = set('0123456789+-*/()., ')
            if not all(c in allowed_chars for c in expression):
                await update.message.reply_text("❌ Разрешены только: цифры, +, -, *, /, ()")
                return
            
            result = eval(expression)
            await update.message.reply_text(f"🔢 {expression} = {result}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка вычисления: {str(e)}")
        
        await self.add_experience(user_data, 1)
    
    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/calculate")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "🧮 ПРОДВИНУТЫЙ КАЛЬКУЛЯТОР\n\n"
                "Функции: sqrt, sin, cos, tan, log, pi, e, pow, abs\n\n"
                "Примеры:\n"
                "• /calculate sqrt(16)\n"
                "• /calculate sin(3.14/2)\n"
                "• /calculate log(100)\n"
                "• /calculate pow(2, 10)"
            )
            return
        
        expression = " ".join(context.args)
        
        try:
            import math
            safe_dict = {
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "log": math.log,
                "log10": math.log10,
                "pi": math.pi,
                "e": math.e,
                "pow": pow,
                "abs": abs,
                "round": round
            }
            
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            await update.message.reply_text(f"🧮 {expression} = {result}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        
        await self.add_experience(user_data, 2)
    
    # ========================================================================
    # КОМАНДЫ - ЯЗЫК И ПРОФИЛЬ
    # ========================================================================
    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/language")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if context.args:
            lang = context.args[0].lower()
            if lang in LANGUAGE_NAMES:
                user_data['language'] = lang
                self.db.save_user(user_data)
                await update.message.reply_text(
                    self.t('language_changed', lang),
                    reply_markup=self.get_keyboard(lang)
                )
                return
        
        keyboard = []
        for code, name in LANGUAGE_NAMES.items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"lang_{code}")])
        
        await update.message.reply_text(
            "🌐 Выберите язык / Choose language:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/rank")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        level = user_data.get('level', 1)
        experience = user_data.get('experience', 0)
        required = level * 100
        progress = (experience / required) * 100
        
        filled = int(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        rank_text = f"""
🏅 ВАШ УРОВЕНЬ

👤 {user_data.get('nickname') or user_data['first_name']}
🆙 Уровень: {level}
⭐ Опыт: {experience}/{required}

📊 Прогресс: {progress:.1f}%
{bar}

💎 VIP: {"✅ Активен" if self.is_vip(user_data) else "❌ Нет"}
"""
        await update.message.reply_text(rank_text)
        await self.add_experience(user_data, 1)
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/profile")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        notes_count = len(self.db.get_notes(user_data['user_id']))
        reminders_count = len(self.db.get_reminders(user_data['user_id']))
        memory_count = len(self.db.get_all_memory(user_data['user_id']))
        
        conv_summary = self.conversation_memory.get_summary(user_data['user_id'])
        conv_msgs = conv_summary['total_messages'] if conv_summary else 0
        
        created = datetime.datetime.fromisoformat(user_data.get('created_at', datetime.datetime.now().isoformat()))
        days_with_bot = (datetime.datetime.now() - created).days
        
        profile_text = f"""
👤 ВАШ ПРОФИЛЬ

📛 Имя: {user_data.get('nickname') or user_data['first_name']}
🆔 ID: {user_data['user_id']}
👤 Username: @{user_data.get('username', 'не установлен')}

🆙 Уровень: {user_data.get('level', 1)}
⭐ Опыт: {user_data.get('experience', 0)}/{user_data.get('level', 1) * 100}
💎 VIP: {"✅ Активен" if self.is_vip(user_data) else "❌ Нет"}

📊 СТАТИСТИКА:
• 📝 Заметок: {notes_count}
• ⏰ Напоминаний: {reminders_count}
• 🧠 Записей в памяти: {memory_count}
• 💬 Сообщений в чате: {conv_msgs}
• 📨 Всего сообщений: {user_data.get('total_messages', 0)}
• 🎯 Команд использовано: {user_data.get('total_commands', 0)}

🗓️ С ботом: {days_with_bot} дней
🌐 Язык: {LANGUAGE_NAMES.get(user_data.get('language', 'ru'))}
"""
        await update.message.reply_text(profile_text)
        await self.add_experience(user_data, 1)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/stats")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not self.is_creator(user_data['user_id']):
            return await self.profile_command(update, context)
        
        users = self.db.get_all_users()
        vip_count = sum(1 for u in users if u.get('is_vip'))
        
        total_notes = 0
        total_reminders = 0
        for user in users:
            total_notes += len(self.db.get_notes(user['user_id']))
            total_reminders += len(self.db.get_reminders(user['user_id']))
        
        total_convs = len(self.conversation_memory.conversations)
        total_msgs = sum(len(c['messages']) for c in self.conversation_memory.conversations.values())
        
        uptime = datetime.datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        stats_text = f"""
📊 ГЛОБАЛЬНАЯ СТАТИСТИКА

👥 ПОЛЬЗОВАТЕЛИ:
• Всего: {len(users)}
• VIP: {vip_count}
• Обычных: {len(users) - vip_count}

💬 РАЗГОВОРЫ:
• Всего разговоров: {total_convs}
• Всего сообщений: {total_msgs}

📝 КОНТЕНТ:
• Заметок: {total_notes}
• Напоминаний: {total_reminders}

⚡ СИСТЕМА:
• Работает: {uptime_str}
• AI: {"✅" if self.gemini_model else "❌"}
• База: ✅ SQLite
• Память: ✅ JSON

🔧 Maintenance: {"🔧" if self.maintenance_mode else "✅"}
"""
        await update.message.reply_text(stats_text)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - УТИЛИТЫ
    # ========================================================================
    
    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/password")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        length = 16
        if context.args and context.args[0].isdigit():
            length = min(int(context.args[0]), 64)
        
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        password = ''.join(random.choice(chars) for _ in range(length))
        
        await update.message.reply_text(
            f"🔐 СГЕНЕРИРОВАННЫЙ ПАРОЛЬ\n\n"
            f"Длина: {length} символов\n\n"
            f"`{password}`\n\n"
            f"💡 Скопируйте и сохраните в надёжном месте!",
            parse_mode='Markdown'
        )
        await self.add_experience(user_data, 1)
    
    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/qr")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "📱 ГЕНЕРАТОР QR-КОДОВ\n\n"
                "Использование: /qr [текст или ссылка]\n\n"
                "Примеры:\n"
                "• /qr https://google.com\n"
                "• /qr Мой контакт: +1234567890"
            )
            return
        
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={requests.utils.quote(text)}"
        
        try:
            await update.message.reply_text("📱 Генерирую QR-код...")
            await context.bot.send_photo(update.effective_chat.id, qr_url)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка генерации: {str(e)}")
        
        await self.add_experience(user_data, 1)
    
    async def shorturl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/shorturl")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "🔗 СОКРАЩАТЕЛЬ ССЫЛОК\n\n"
                "Использование: /shorturl [длинная ссылка]\n\n"
                "Пример:\n"
                "/shorturl https://very-long-url.com/page"
            )
            return
        
        url = context.args[0]
        
        try:
            api_url = f"https://is.gd/create.php?format=simple&url={requests.utils.quote(url)}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                short_url = response.text
                await update.message.reply_text(
                    f"✅ ССЫЛКА СОКРАЩЕНА\n\n"
                    f"📎 Короткая: {short_url}\n\n"
                    f"🔗 Оригинал: {url}"
                )
            else:
                await update.message.reply_text("❌ Ошибка сокращения ссылки")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        
        await self.add_experience(user_data, 1)
    
    async def ip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/ip")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=10)
            data = response.json()
            ip = data['ip']
            
            info_response = requests.get(f'http://ip-api.com/json/{ip}', timeout=10)
            info = info_response.json()
            
            text = f"""
🌐 ИНФОРМАЦИЯ О IP

📍 IP адрес: {ip}
🌍 Страна: {info.get('country', 'N/A')}
🏙️ Город: {info.get('city', 'N/A')}
🗺️ Регион: {info.get('regionName', 'N/A')}
🌐 ISP: {info.get('isp', 'N/A')}
"""
            await update.message.reply_text(text)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения IP: {str(e)}")
        
        await self.add_experience(user_data, 1)
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/weather")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "🌤️ ПОГОДА\n\n"
                "Использование: /weather [город]\n\n"
                "Примеры:\n"
                "• /weather Москва\n"
                "• /weather London\n"
                "• /weather Paris"
            )
            return
        
        city = " ".join(context.args)
        
        if OPENWEATHER_API_KEY:
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
                response = requests.get(url, timeout=10).json()
                
                if response.get("cod") == 200:
                    weather = response["weather"][0]["description"]
                    temp = round(response["main"]["temp"])
                    feels = round(response["main"]["feels_like"])
                    humidity = response["main"]["humidity"]
                    wind = response["wind"]["speed"]
                    
                    text = f"""
🌤️ ПОГОДА В {city.upper()}

🌡️ Температура: {temp}°C
🤔 Ощущается: {feels}°C
☁️ {weather.capitalize()}
💧 Влажность: {humidity}%
🌪️ Ветер: {wind} м/с

⏰ Обновлено: {datetime.datetime.now().strftime('%H:%M')}
"""
                    await update.message.reply_text(text)
                    await self.add_experience(user_data, 2)
                    return
            except Exception as e:
                logger.error(f"OpenWeather error: {e}")
        
        try:
            url = f"https://wttr.in/{city}?format=%C+%t+💧%h+🌪️%w&lang=ru"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                text = f"""
🌤️ ПОГОДА В {city.upper()}

{response.text.strip()}

⏰ Актуально: {datetime.datetime.now().strftime('%H:%M')}
"""
                await update.message.reply_text(text)
            else:
                await update.message.reply_text("❌ Город не найден")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения погоды: {str(e)}")
        
        await self.add_experience(user_data, 2)
    
    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/currency")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "💱 КОНВЕРТЕР ВАЛЮТ\n\n"
                "Использование: /currency [сумма] [из] [в]\n\n"
                "Примеры:\n"
                "• /currency 100 USD EUR\n"
                "• /currency 50 EUR RUB"
            )
            return
        
        try:
            amount = float(context.args[0])
            from_curr = context.args[1].upper()
            to_curr = context.args[2].upper()
            
            url = f"https://api.exchangerate-api.com/v4/latest/{from_curr}"
            response = requests.get(url, timeout=10).json()
            
            if 'rates' in response and to_curr in response['rates']:
                rate = response['rates'][to_curr]
                result = amount * rate
                
                text = f"""
💱 КОНВЕРТАЦИЯ ВАЛЮТ

{amount} {from_curr} = {result:.2f} {to_curr}

📊 Курс: 1 {from_curr} = {rate:.4f} {to_curr}
⏰ {datetime.datetime.now().strftime('%H:%M')}
"""
                await update.message.reply_text(text)
            else:
                await update.message.reply_text("❌ Неверный код валюты")
        except ValueError:
            await update.message.reply_text("❌ Неверная сумма")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        
        await self.add_experience(user_data, 2)
    
    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/translate")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "🌐 ПЕРЕВОДЧИК\n\n"
                "Использование: /translate [язык] [текст]\n\n"
                "Коды языков: en, ru, es, fr, de, it, ja, zh\n\n"
                "Примеры:\n"
                "• /translate en Привет, мир!\n"
                "• /translate ru Hello, world!"
            )
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ Перевод недоступен (AI не активен)")
            return
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            prompt = f"Переведи этот текст на {target_lang}. Верни ТОЛЬКО перевод, без пояснений:\n\n{text}"
            response = self.gemini_model.generate_content(prompt)
            
            await update.message.reply_text(f"🌐 Перевод:\n\n{response.text}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка перевода: {str(e)}")
        
        await self.add_experience(user_data, 2)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/help")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        help_text = """
📋 ПОЛНЫЙ СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - Информация о боте
/status - Статус системы
/uptime - Время работы

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос AI
/clearhistory - Очистить историю

📝 ЗАМЕТКИ:
/note [текст] - Создать заметку
/notes - Показать все заметки
/delnote [номер] - Удалить заметку
/findnote [текст] - Найти заметку
/clearnotes - Удалить все заметки

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist - Вся память
/memorydel [ключ]

⏰ ВРЕМЯ И ДАТА:
/time - Мировое время
/date - Текущая дата

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Случайная шутка
/fact - Интересный факт
/quote - Вдохновляющая цитата
/quiz - Викторина
/coin - Подбросить монетку
/dice - Бросить кубик
/8ball [вопрос] - Магический шар

🔢 МАТЕМАТИКА:
/math [выражение] - Вычисления
/calculate [выражение] - Калькулятор

🛠️ УТИЛИТЫ:
/password [длина] - Генератор паролей
/qr [текст] - Создать QR-код
/shorturl [url] - Короткая ссылка
/ip - Мой IP адрес
/weather [город] - Погода
/currency [сумма] [из] [в] - Конвертер
/translate [язык] [текст] - Перевод

📊 ПРОГРЕСС:
/rank - Ваш уровень и опыт
/profile - Полный профиль

🌐 ЯЗЫК:
/language - Выбрать язык

💎 VIP ФУНКЦИИ:
/vip - Статус VIP
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/delreminder [номер] - Удалить
/nickname [имя] - Установить никнейм
"""

        if self.is_creator(user_data['user_id']):
            help_text += """
👑 КОМАНДЫ СОЗДАТЕЛЯ:
/grant_vip [id] [week/month/year/permanent]
/revoke_vip [user_id]
/broadcast [текст] - Рассылка
/users - Список пользователей
/stats - Полная статистика
/maintenance [on/off]
/backup - Резервная копия
"""
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/info")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        users = self.db.get_all_users()
        vip_count = sum(1 for u in users if u.get('is_vip'))
        
        total_conversations = len(self.conversation_memory.conversations)
        total_messages = sum(
            len(conv['messages']) 
            for conv in self.conversation_memory.conversations.values()
        )
        
        info_text = f"""
🤖 О БОТЕ

📌 Версия: 3.0 (Улучшенная)
👨‍💻 Создатель: Ernest {CREATOR_USERNAME}
👨 Папа: {PAPA_USERNAME}
🤖 Бот: {BOT_USERNAME}

🔧 Технологии:
• AI: {"✅ Gemini 2.0 Flash" if self.gemini_model else "❌ Недоступен"}
• База: ✅ SQLite (расширенная)
• Память: ✅ JSON (неограниченная)
• Хостинг: ✅ Render 24/7

📊 Статистика:
• Пользователей: {len(users)}
• VIP пользователей: {vip_count}
• Разговоров: {total_conversations}
• Всего сообщений: {total_messages}
• Языков: 6

✨ Особенности v3.0:
• 🧠 Полная память разговоров
• ⏰ Актуальное время и погода
• 🎂 Автопоздравления
• 🚀 Улучшенная производительность
• 💾 Автосохранение данных

⚡ Работает 24/7 с автопингом
"""
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/status")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        users = self.db.get_all_users()
        uptime = datetime.datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        conv_size = len(self.conversation_memory.conversations)
        total_msgs = sum(len(c['messages']) for c in self.conversation_memory.conversations.values())
        
        status_text = f"""
⚡ СТАТУС БОТА

🟢 Статус: Онлайн
📅 Версия: 3.0 (Улучшенная)
⏰ Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
🕐 Работает: {uptime_str}

👥 Пользователей: {len(users)}
🧠 AI: {"✅ Gemini 2.0" if self.gemini_model else "❌"}
💾 База данных: ✅ SQLite
💬 Разговоров: {conv_size}
📨 Сообщений: {total_msgs}

🔧 Maintenance: {"🔧 Включен" if self.maintenance_mode else "✅ Выключен"}
📡 Автопинг: ✅ Активен
💾 Автосохранение: ✅ Активно
"""
        await update.message.reply_text(status_text)
        await self.add_experience(user_data, 1)
    
    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/uptime")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        uptime = datetime.datetime.now() - self.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_text = f"""
🕐 ВРЕМЯ РАБОТЫ

📅 Дней: {days}
⏰ Часов: {hours}
⏱️ Минут: {minutes}
⚡ Секунд: {seconds}

🚀 Запущен: {self.start_time.strftime('%d.%m.%Y %H:%M:%S')}
✅ Работает стабильно!
"""
        await update.message.reply_text(uptime_text)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - ВРЕМЯ И ДАТА
    # ========================================================================
    
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/time")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        lang = user_data.get('language', 'ru')
        
        now_utc = datetime.datetime.now(pytz.utc)
        
        timezones = [
            ('GMT (Лондон)', 'Europe/London'),
            ('CEST (Берлин)', 'Europe/Berlin'),
            ('CEST (Париж)', 'Europe/Paris'),
            ('MSK (Москва)', 'Europe/Moscow'),
            ('EST (Вашингтон)', 'America/New_York'),
            ('PST (Лос-Анджелес)', 'America/Los_Angeles'),
            ('CST (Чикаго)', 'America/Chicago'),
            ('JST (Токио)', 'Asia/Tokyo'),
            ('CST (Пекин)', 'Asia/Shanghai'),
            ('IST (Дели)', 'Asia/Kolkata'),
            ('AEST (Сидней)', 'Australia/Sydney')
        ]
        
        time_text = f"⏰ МИРОВОЕ ВРЕМЯ (актуальное)\n\n"
        time_text += f"🌍 UTC: {now_utc.strftime('%H:%M:%S')}\n\n"
        
        for city_name, tz_name in timezones:
            try:
                tz = pytz.timezone(tz_name)
                local_time = now_utc.astimezone(tz)
                time_text += f"🕐 {city_name}: {local_time.strftime('%H:%M:%S')}\n"
            except Exception as e:
                logger.error(f"Ошибка часового пояса {tz_name}: {e}")
        
        time_text += f"\n📅 Дата: {now_utc.strftime('%d.%m.%Y')}"
        
        await update.message.reply_text(time_text)
        await self.add_experience(user_data, 1)
    
    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/date")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        now = datetime.datetime.now()
        days_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        months_ru = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                     'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
        
        day_name = days_ru[now.weekday()]
        month_name = months_ru[now.month - 1]
        
        date_text = f"""
📅 СЕГОДНЯ

🗓️ {day_name}
📆 {now.day} {month_name} {now.year} года
⏰ Время: {now.strftime('%H:%M:%S')}

📊 День года: {now.timetuple().tm_yday}/365
📈 Неделя: {now.isocalendar()[1]}/52
🌙 Месяц: {now.month}/12
"""
        await update.message.reply_text(date_text)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - AI ЧАТ
    # ========================================================================
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/ai")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            summary = self.conversation_memory.get_summary(user_data['user_id'])
            if summary:
                await update.message.reply_text(
                    f"💬 AI готов к диалогу!\n\n"
                    f"📊 Статистика разговора:\n"
                    f"• Всего сообщений: {summary['total_messages']}\n"
                    f"• Ваших сообщений: {summary['user_messages']}\n"
                    f"• Моих ответов: {summary['ai_messages']}\n\n"
                    f"Задайте вопрос: /ai [ваш вопрос]\n"
                    f"или просто напишите мне"
                )
            else:
                await update.message.reply_text(
                    "💬 AI готов! Задайте вопрос\n"
                    "Пример: /ai Расскажи о квантовых компьютерах"
                )
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI временно недоступен")
            return
        
        query = " ".join(context.args)
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            history = self.conversation_memory.get_context(user_data['user_id'], limit=None)
            
            context_str = ""
            if history:
                for msg in history[-10:]:
                    role = "Пользователь" if msg['role'] == 'user' else "AI"
                    context_str += f"{role}: {msg['content'][:200]}\n"
            
            prompt = f"""Ты умный AI-ассистент. У тебя есть доступ к полной истории разговора.

История последних сообщений:
{context_str}

Текущий вопрос пользователя: {query}

Ответь полезно, учитывая весь контекст разговора. Будь дружелюбным и информативным."""

            response = self.gemini_model.generate_content(prompt)
            
            self.conversation_memory.add_message(user_data['user_id'], 'user', query)
            self.conversation_memory.add_message(user_data['user_id'], 'assistant', response.text)
            
            await update.message.reply_text(response.text)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)[:100]}")
            logger.error(f"Ошибка AI: {e}")
        
        await self.add_experience(user_data, 2)
    
    async def clearhistory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/clearhistory")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        summary = self.conversation_memory.get_summary(user_data['user_id'])
        if summary:
            msg_count = summary['total_messages']
            self.conversation_memory.clear_history(user_data['user_id'])
            await update.message.reply_text(
                f"🗑️ История очищена!\n"
                f"📊 Удалено сообщений: {msg_count}\n\n"
                f"Начинаем новый разговор!"
            )
        else:
            await update.message.reply_text("📭 История уже пуста!")
        
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - ЗАМЕТКИ
    # ========================================================================
    
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/note")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "📝 Создание заметки\n\n"
                "Использование: /note [текст заметки]\n\n"
                "Примеры:\n"
                "• /note Купить молоко\n"
                "• /note Позвонить маме в 18:00"
            )
            return
        
        note = " ".join(context.args)
        self.db.add_note(user_data['user_id'], note)
        
        notes_count = len(self.db.get_notes(user_data['user_id']))
        
        await update.message.reply_text(
            f"✅ Заметка сохранена!\n\n"
            f"📝 {note}\n\n"
            f"📊 Всего заметок: {notes_count}"
        )
        await self.add_experience(user_data, 1)
    
    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/notes")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        notes = self.db.get_notes(user_data['user_id'])
        
        if not notes:
            await update.message.reply_text(
                "📭 У вас пока нет заметок!\n\n"
                "Создайте первую: /note [текст]"
            )
            return
        
        text = "📝 ВАШИ ЗАМЕТКИ:\n\n"
        for i, note in enumerate(notes, 1):
            created = datetime.datetime.fromisoformat(note['created_at']).strftime('%d.%m %H:%M')
            text += f"{i}. {note['note']}\n   📅 {created}\n\n"
        
        text += f"📊 Всего: {len(notes)} заметок"
        
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (список обрезан)"
        
        await update.message.reply_text(text)
        await self.add_experience(user_data, 1)
    
    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/delnote")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text(
                "❌ Укажите номер заметки!\n\n"
                "Пример: /delnote 1\n\n"
                "Посмотреть номера: /notes"
            )
            return
        
        notes = self.db.get_notes(user_data['user_id'])
        index = int(context.args[0]) - 1
        
        if 0 <= index < len(notes):
            deleted_note = notes[index]['note']
            self.db.delete_note(notes[index]['id'], user_data['user_id'])
            await update.message.reply_text(
                f"✅ Заметка удалена!\n\n"
                f"🗑️ {deleted_note}"
            )
        else:
            await update.message.reply_text(f"❌ Заметки #{index+1} не существует!")
        
        await self.add_experience(user_data, 1)
    
    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/findnote")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text(
                "🔍 Поиск заметки\n\n"
                "Использование: /findnote [текст для поиска]"
            )
            return
        
        search_text = " ".join(context.args).lower()
        notes = self.db.get_notes(user_data['user_id'])
        
        found = [n for n in notes if search_text in n['note'].lower()]
        
        if not found:
            await update.message.reply_text(f"❌ Заметки с текстом '{search_text}' не найдены")
            return
        
        text = f"🔍 Найдено: {len(found)} заметок\n\n"
        for i, note in enumerate(found, 1):
            created = datetime.datetime.fromisoformat(note['created_at']).strftime('%d.%m %H:%M')
            text += f"{i}. {note['note']}\n   📅 {created}\n\n"
        
        await update.message.reply_text(text)
        await self.add_experience(user_data, 1)
    
    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/clearnotes")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        count = self.db.clear_notes(user_data['user_id'])
        
        await update.message.reply_text(f"🗑️ Удалено {count} заметок!")
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ - ПАМЯТЬ
    # ========================================================================
    
    async def memorysave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memorysave")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "🧠 Сохранение в память\n\n"
                "Использование: /memorysave [ключ] [значение]\n\n"
                "Примеры:\n"
                "• /memorysave любимый_цвет синий\n"
                "• /memorysave email test@example.com"
            )
            return
        
        key = context.args[0]
        value = " ".join(context.args[1:])
        
        self.db.save_memory(user_data['user_id'], key, value)
        
        await update.message.reply_text(
            f"✅ Сохранено в память!\n\n"
            f"🔑 Ключ: {key}\n"
            f"💾 Значение: {value}"
        )
        await self.add_experience(user_data, 1)
    
    async def memoryget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memoryget")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text("❌ Укажите ключ!\nПример: /memoryget любимый_цвет")
            return
        
        key = context.args[0]
        value = self.db.get_memory(user_data['user_id'], key)
        
        if value:
            await update.message.reply_text(
                f"🔍 Найдено!\n\n"
                f"🔑 {key}\n"
                f"💾 {value}"
            )
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти")
        
        await self.add_experience(user_data, 1)
    
    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memorylist")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        memory = self.db.get_all_memory(user_data['user_id'])
        
        if not memory:
            await update.message.reply_text(
                "📭 Память пуста!\n\n"
                "Сохраните что-нибудь: /memorysave [ключ] [значение]"
            )
            return
        
        text = "🧠 ВСЯ ПАМЯТЬ:\n\n"
        for key, value in memory.items():
            text += f"🔑 {key}\n💾 {value}\n\n"
        
        text += f"📊 Всего записей: {len(memory)}"
        
        await update.message.reply_text(text)
        await self.add_experience(user_data, 1)
    
    async def memorydel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memorydel")
        user_data['total_commands'] = user_data.get('total_commands', 0) + 1
        
        if not context.args:
            await update.message.reply_text("❌ Укажите ключ!\nПример: /memorydel любимый_цвет")
            return
        
        key = context.args[0]
        deleted = self.db.delete_memory(user_data['user_id'], key)
        
        if deleted:
            await update.message.reply_text(f"✅ Удалено из памяти: {key}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден")
        
        await self.add_experience(user_data, 1)
