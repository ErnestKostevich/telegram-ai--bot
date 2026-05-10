import logging
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

def main():
    logger.info("Starting AI DISCO BOT (BYOK Edition)...")
    
    from bot import handlers

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Base
    for cmd, fn in [
        ("start", handlers.start_command), ("help", handlers.help_command),
        ("info", handlers.info_command), ("status", handlers.status_command),
        ("lang", handlers.lang_command), ("profile", handlers.profile_command),
        ("disco", handlers.disco_command),
    ]:
        application.add_handler(CommandHandler(cmd, fn))

    # AI & Memory
    for cmd, fn in [
        ("setprovider", handlers.setprovider_command), ("setkey", handlers.setkey_command),
        ("setmodel", handlers.setmodel_command), ("ai", handlers.ai_command),
        ("memorysave", handlers.memorysave_command), ("memoryget", handlers.memoryget_command),
        ("memorylist", handlers.memorylist_command), ("memorydel", handlers.memorydel_command),
    ]:
        application.add_handler(CommandHandler(cmd, fn))

    # Notes & Todo
    for cmd, fn in [
        ("note", handlers.note_command), ("notes", handlers.notes_command),
        ("delnote", handlers.delnote_command), ("todo", handlers.todo_command),
    ]:
        application.add_handler(CommandHandler(cmd, fn))

    # VIP & Creator
    for cmd, fn in [
        ("vip", handlers.vip_command), ("remind", handlers.remind_command),
        ("reminders", handlers.reminders_command), ("grant_vip", handlers.grant_vip_command),
        ("broadcast", handlers.broadcast_command), ("stats", handlers.stats_command),
    ]:
        application.add_handler(CommandHandler(cmd, fn))

    # Games & Utils
    for cmd, fn in [
        ("dice", handlers.dice_command), ("coinflip", handlers.coinflip_command),
        ("random", handlers.random_command), ("joke", handlers.joke_command),
        ("time", handlers.time_command), ("weather", handlers.weather_command),
        ("calc", handlers.calc_command), ("password", handlers.password_command),
        ("generate", handlers.generate_command),
    ]:
        application.add_handler(CommandHandler(cmd, fn))

    # Groups
    for cmd, fn in [
        ("grouphelp", handlers.grouphelp_command), ("ban", handlers.ban_command),
        ("warn", handlers.warn_command), ("mute", handlers.mute_command),
        ("kick", handlers.kick_command), ("ask", handlers.ask_command),
        ("summary", handlers.summary_command), ("translate", handlers.translate_command),
        ("rules", handlers.rules_command), ("setrules", handlers.setrules_command),
        ("guardian", handlers.guardian_command), ("groupstats", handlers.groupstats_command),
    ]:
        application.add_handler(CommandHandler(cmd, fn))

    # Extended commands (stubs for less common ones)
    from bot.handlers.extended import generic_mock_command, daily_command, rep_command, roast_command
    for cmd, fn in [("daily", daily_command), ("rep", rep_command), ("roast", roast_command)]:
        application.add_handler(CommandHandler(cmd, fn))
    for cmd in ["warnings", "unwarn", "unmute", "antilink", "caps", "leaderboard", "welcome",
                 "goodbye", "topic", "idea", "rules_ai", "quest", "quiz", "vote", "event",
                 "pin", "unpin", "announce", "slowmode", "logs", "purge", "antispam",
                 "vipgroup", "setpremium", "customwelcome", "autorole", "aivoice", "rank"]:
        application.add_handler(CommandHandler(cmd, generic_mock_command))

    # Interactive
    application.add_handler(CallbackQueryHandler(handlers.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.keyboard_message_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handlers.media_message_handler))

    logger.info("Bot is polling...")
    application.run_polling(drop_pending_updates=True)

async def post_init(application):
    from bot.storage import storage
    from bot.scheduler import start_scheduler

    logger.info("Initializing storage and scheduler...")
    await storage.load()
    start_scheduler(application)
    logger.info("Bot is ready!")

if __name__ == "__main__":
    print("Menu")
    main()
