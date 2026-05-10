import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import bot.handlers as handlers
from bot.config import BOT_TOKEN
from bot.storage import storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    logger.info("Initializing storage and scheduler...")
    await storage.load()
    
    from bot.scheduler import start_scheduler
    start_scheduler(application.bot)
    logger.info("Bot is ready!")

def main():
    logger.info("Starting AI DISCO BOT (BYOK Edition)...")
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        return

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Base
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("info", handlers.info_command))
    application.add_handler(CommandHandler("status", handlers.status_command))
    application.add_handler(CommandHandler("lang", handlers.lang_command))

    # AI & Memory
    application.add_handler(CommandHandler("setprovider", handlers.setprovider_command))
    application.add_handler(CommandHandler("setkey", handlers.setkey_command))
    application.add_handler(CommandHandler("ai", handlers.ai_command))
    application.add_handler(CommandHandler("memorysave", handlers.memorysave_command))
    application.add_handler(CommandHandler("memoryget", handlers.memoryget_command))
    application.add_handler(CommandHandler("memorylist", handlers.memorylist_command))
    application.add_handler(CommandHandler("memorydel", handlers.memorydel_command))

    # Notes
    application.add_handler(CommandHandler("note", handlers.note_command))
    application.add_handler(CommandHandler("notes", handlers.notes_command))
    application.add_handler(CommandHandler("delnote", handlers.delnote_command))

    # VIP
    application.add_handler(CommandHandler("vip", handlers.vip_command))
    application.add_handler(CommandHandler("remind", handlers.remind_command))
    application.add_handler(CommandHandler("reminders", handlers.reminders_command))

    # Creator
    application.add_handler(CommandHandler("grant_vip", handlers.grant_vip_command))
    application.add_handler(CommandHandler("broadcast", handlers.broadcast_command))
    application.add_handler(CommandHandler("stats", handlers.stats_command))

    # Games & Utils
    application.add_handler(CommandHandler("dice", handlers.dice_command))
    application.add_handler(CommandHandler("coinflip", handlers.coinflip_command))
    application.add_handler(CommandHandler("random", handlers.random_command))
    application.add_handler(CommandHandler("joke", handlers.joke_command))
    application.add_handler(CommandHandler("time", handlers.time_command))
    application.add_handler(CommandHandler("weather", handlers.weather_command))
    application.add_handler(CommandHandler("calc", handlers.calc_command))
    application.add_handler(CommandHandler("password", handlers.password_command))

    # Groups
    application.add_handler(CommandHandler("grouphelp", handlers.grouphelp_command))
    application.add_handler(CommandHandler("ban", handlers.ban_command))
    application.add_handler(CommandHandler("ask", handlers.ask_command))
    application.add_handler(CommandHandler("rules", handlers.rules_command))
    application.add_handler(CommandHandler("setrules", handlers.setrules_command))

    # Interactive
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(handlers.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.keyboard_message_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handlers.media_message_handler))

    logger.info("Bot is polling...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
