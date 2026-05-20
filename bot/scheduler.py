import logging
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.storage import storage

logger = logging.getLogger(__name__)


async def _check_reminders_task(bot):
    try:
        now = time.time()
        reminders = storage.data.get("reminders", [])
        to_remove = []

        for r in reminders:
            if r["time"] <= now:
                try:
                    overdue_min = int((now - r["time"]) / 60)
                    prefix = "⏰ <b>НАПОМИНАНИЕ:</b>"
                    if overdue_min > 5:
                        prefix = f"⏰ <b>НАПОМИНАНИЕ</b> (опоздало на {overdue_min} мин):"
                    await bot.send_message(
                        chat_id=r["chat_id"],
                        text=f"{prefix}\n\n{r['text']}",
                        parse_mode="HTML",
                    )
                    to_remove.append(r)
                except Exception as e:
                    logger.error(f"Failed to send reminder: {e}")
                    to_remove.append(r)

        if to_remove:
            for r in to_remove:
                try:
                    storage.data["reminders"].remove(r)
                except ValueError:
                    pass
            await storage.save()

    except Exception as e:
        logger.error(f"Error in scheduler task: {e}")


async def _periodic_save_task():
    """Persist in-memory state (group stats, message buffer, etc.) every few minutes.
    Without this, the group_message_tracker's writes only land on disk when an admin
    command happens to call save()."""
    try:
        await storage.save()
        logger.debug("Periodic save complete.")
    except Exception as e:
        logger.error(f"Periodic save failed: {e}")


def start_scheduler(bot_or_app):
    # Accept either a Bot or an Application for compatibility
    bot = getattr(bot_or_app, "bot", None) or bot_or_app
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_check_reminders_task, "interval", minutes=1, args=[bot])
    scheduler.add_job(_periodic_save_task, "interval", minutes=5)
    scheduler.start()
    logger.info("APScheduler started: reminders (1m) + periodic save (5m).")
