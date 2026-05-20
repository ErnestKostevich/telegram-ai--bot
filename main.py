import logging
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")


def main():
    logger.info("Starting AI DISCO BOT v2 (BYOK + Memory + Vision)...")

    from bot import handlers

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # ============== Commands ==============
    base = [
        ("start", handlers.start_command), ("help", handlers.help_command),
        ("info", handlers.info_command), ("status", handlers.status_command),
        ("lang", handlers.lang_command), ("profile", handlers.profile_command),
        ("disco", handlers.disco_command),
        ("version", handlers.version_command),
        ("changelog", handlers.changelog_command),
        ("export", handlers.export_command),
    ]
    ai_mem = [
        ("setprovider", handlers.setprovider_command), ("setkey", handlers.setkey_command),
        ("setmodel", handlers.setmodel_command), ("ai", handlers.ai_command),
        ("clear", handlers.clear_command),
        ("memorysave", handlers.memorysave_command), ("memoryget", handlers.memoryget_command),
        ("memorylist", handlers.memorylist_command), ("memorydel", handlers.memorydel_command),
    ]
    notes = [
        ("note", handlers.note_command), ("notes", handlers.notes_command),
        ("delnote", handlers.delnote_command), ("todo", handlers.todo_command),
    ]
    vip_creator = [
        ("vip", handlers.vip_command), ("remind", handlers.remind_command),
        ("reminders", handlers.reminders_command),
        ("feedback", handlers.feedback_command),
        ("grant_vip", handlers.grant_vip_command), ("broadcast", handlers.broadcast_command),
        ("stats", handlers.stats_command), ("users", handlers.users_command),
    ]
    games_utils = [
        ("dice", handlers.dice_command), ("coinflip", handlers.coinflip_command),
        ("random", handlers.random_command), ("joke", handlers.joke_command),
        ("time", handlers.time_command), ("weather", handlers.weather_command),
        ("calc", handlers.calc_command), ("password", handlers.password_command),
        ("generate", handlers.generate_command),
        ("daily", handlers.daily_command), ("rep", handlers.rep_command),
        ("roast", handlers.roast_command),
        # WOW commands
        ("persona", handlers.persona_command),
        ("today", handlers.today_command),
        ("quiz", handlers.quiz_command),
        ("slots", handlers.slots_command),
        ("basket", handlers.basket_command),
        ("football", handlers.football_command),
        ("dart", handlers.dart_command),
        ("bowl", handlers.bowl_command),
    ]
    groups = [
        ("grouphelp", handlers.grouphelp_command),
        ("ban", handlers.ban_command), ("kick", handlers.kick_command),
        ("warn", handlers.warn_command), ("warnings", handlers.warnings_command),
        ("unwarn", handlers.unwarn_command),
        ("mute", handlers.mute_command), ("unmute", handlers.unmute_command),
        ("purge", handlers.purge_command),
        ("antilink", handlers.antilink_command), ("antispam", handlers.antispam_command),
        ("welcome", handlers.welcome_command), ("goodbye", handlers.goodbye_command),
        ("ask", handlers.ask_command),
        ("summary", handlers.summary_command), ("translate", handlers.translate_command),
        ("rules", handlers.rules_command), ("setrules", handlers.setrules_command),
        ("guardian", handlers.guardian_command), ("groupstats", handlers.groupstats_command),
    ]

    for batch in (base, ai_mem, notes, vip_creator, games_utils, groups):
        for cmd, fn in batch:
            application.add_handler(CommandHandler(cmd, fn))

    # Group activity tracker (must run on every group message before catch-all text handler)
    # Use group=-1 so it runs first in the dispatcher pipeline.
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION | filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER),
                       handlers.group_message_tracker),
        group=-1,
    )

    # Quiz callbacks have their own prefix → dedicated handler
    application.add_handler(CallbackQueryHandler(handlers.quiz_callback, pattern=r"^quizans_"))
    # Catch-all callbacks
    application.add_handler(CallbackQueryHandler(handlers.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.keyboard_message_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handlers.media_message_handler))
    # Voice / audio → Whisper transcribe → AI
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handlers.voice_message_handler))

    logger.info("Bot is polling...")
    application.run_polling(drop_pending_updates=True)


async def post_init(application):
    from bot.storage import storage
    from bot.scheduler import start_scheduler

    logger.info("Initializing storage and scheduler...")
    await storage.load()
    start_scheduler(application.bot)
    await _set_bot_commands(application)
    logger.info("Bot is ready!")


async def _set_bot_commands(application):
    """Register a clean BotCommand list so users see them in Telegram's UI."""
    from telegram import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
    private_cmds = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Command reference"),
        BotCommand("ai", "Ask the AI"),
        BotCommand("clear", "Reset conversation context"),
        BotCommand("setprovider", "Choose AI provider"),
        BotCommand("setkey", "Set API key"),
        BotCommand("setmodel", "Pick model"),
        BotCommand("note", "Create a note"),
        BotCommand("notes", "List notes"),
        BotCommand("todo", "Tasks"),
        BotCommand("memorysave", "Save to memory"),
        BotCommand("memorylist", "View memory"),
        BotCommand("vip", "VIP status"),
        BotCommand("generate", "Generate image (VIP)"),
        BotCommand("remind", "Set reminder (VIP)"),
        BotCommand("profile", "Your profile"),
        BotCommand("daily", "Daily reward"),
        BotCommand("today", "AI fortune of the day"),
        BotCommand("quiz", "AI-generated quiz"),
        BotCommand("persona", "Switch AI persona"),
        BotCommand("slots", "🎰 Slots mini-game"),
        BotCommand("basket", "🏀 Basketball game"),
        BotCommand("football", "⚽ Football game"),
        BotCommand("dart", "🎯 Darts game"),
        BotCommand("bowl", "🎳 Bowling game"),
        BotCommand("feedback", "Send feedback"),
        BotCommand("changelog", "What's new"),
        BotCommand("lang", "Change language"),
    ]
    group_cmds = [
        BotCommand("ask", "Ask AI in group"),
        BotCommand("summary", "Summarize recent chat"),
        BotCommand("translate", "Translate text/reply"),
        BotCommand("warn", "Warn user (reply)"),
        BotCommand("warnings", "Show warnings"),
        BotCommand("mute", "Mute user (reply)"),
        BotCommand("ban", "Ban user (reply)"),
        BotCommand("kick", "Kick user (reply)"),
        BotCommand("purge", "Delete N messages"),
        BotCommand("antilink", "Auto-delete links"),
        BotCommand("welcome", "Welcome message"),
        BotCommand("rules", "Show rules"),
        BotCommand("grouphelp", "Group commands"),
    ]
    try:
        await application.bot.set_my_commands(private_cmds, scope=BotCommandScopeAllPrivateChats())
        await application.bot.set_my_commands(group_cmds, scope=BotCommandScopeAllGroupChats())
    except Exception as e:
        logger.warning(f"set_my_commands failed: {e}")


if __name__ == "__main__":
    main()
