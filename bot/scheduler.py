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
                    await bot.send_message(
                        chat_id=r["chat_id"],
                        text=f"⏰ <b>НАПОМИНАНИЕ:</b>\n\n{r['text']}",
                        parse_mode="HTML"
                    )
                    to_remove.append(r)
                except Exception as e:
                    logger.error(f"Failed to send reminder: {e}")
                    to_remove.append(r)
                    
        if to_remove:
            for r in to_remove:
                storage.data["reminders"].remove(r)
            await storage.save()
            
    except Exception as e:
        logger.error(f"Error in scheduler task: {e}")

def start_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_check_reminders_task, 'interval', minutes=1, args=[bot])
    scheduler.start()
    logger.info("APScheduler started for reminders.")
