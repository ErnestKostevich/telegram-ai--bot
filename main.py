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

async def main():
    logger.info("Starting AI DISCO BOT (BYOK Edition)...")
    
    # Load data from GitHub API
    await storage.load()
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Base
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("info", handlers.info_command))
    application.add_handler(CommandHandler("status", handlers.status_command))

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

    # Groups
    application.add_handler(CommandHandler("grouphelp", handlers.grouphelp_command))
    application.add_handler(CommandHandler("ban", handlers.ban_command))
    application.add_handler(CommandHandler("ask", handlers.ask_command))
    application.add_handler(CommandHandler("rules", handlers.rules_command))
    application.add_handler(CommandHandler("setrules", handlers.setrules_command))

    # Start the scheduler for reminders
    from bot.scheduler import start_scheduler
    start_scheduler(application.bot)

    logger.info("Bot is polling...")
    await application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
