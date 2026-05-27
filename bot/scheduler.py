import html
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
                    # Escape so a reminder body with < or & doesn't fail delivery
                    body = html.escape(r.get("text", ""))
                    await bot.send_message(
                        chat_id=r["chat_id"],
                        text=f"{prefix}\n\n{body}",
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


async def _spam_cache_cleanup_task():
    """Drop antispam buckets that haven't been touched in 5 minutes so the cache
    doesn't grow forever in long-lived groups."""
    try:
        from bot.handlers import groups
        cutoff = time.time() - 300
        to_drop = [
            key for key, bucket in groups._spam_cache.items()
            if not bucket or bucket[-1][1] < cutoff
        ]
        for key in to_drop:
            groups._spam_cache.pop(key, None)
        if to_drop:
            logger.debug(f"Spam-cache cleanup: dropped {len(to_drop)} stale buckets.")
    except Exception as e:
        logger.error(f"Spam-cache cleanup failed: {e}")


async def _morning_digest_job(bot):
    """Wraps the digest scheduler task with error swallowing."""
    try:
        from bot.handlers.digest import morning_digest_scheduler_task
        await morning_digest_scheduler_task(bot)
    except Exception as e:
        logger.error(f"Morning digest job failed: {e}")


def start_scheduler(bot_or_app):
    bot = getattr(bot_or_app, "bot", None) or bot_or_app
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_check_reminders_task, "interval", minutes=1, args=[bot])
    scheduler.add_job(_periodic_save_task, "interval", minutes=5)
    scheduler.add_job(_spam_cache_cleanup_task, "interval", minutes=10)
    # Morning digest: every 15 min, fires per-user when their local clock matches
    scheduler.add_job(_morning_digest_job, "interval", minutes=15, args=[bot])
    scheduler.start()
    logger.info(
        "APScheduler started: reminders (1m) + save (5m) + spam cleanup (10m) + digest (15m)."
    )
