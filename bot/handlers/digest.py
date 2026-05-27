"""Morning digest — opt-in daily recap delivered at the user's local time.

Each user picks:
  /digest on|off — toggle delivery
  /digest [HH:MM] — set delivery time (defaults to 08:00)
  /tz [IANA zone] — set timezone (defaults to UTC). Examples:
    /tz Europe/Moscow
    /tz America/New_York
    /tz Asia/Tokyo

Scheduler fires every 15 minutes. For each opted-in user, we compute their
local time. If the time matches the configured digest_time within a 7-minute
window AND we haven't delivered today already (local date), we send the
digest. Idempotent via last_digest_date.

The digest itself shows:
- Greeting with first name
- Today's open todos (top 3)
- Active reminders for today
- Daily streak
- Weekly XP rank (if user is in top 10)
"""
import datetime
import html
import re
import time
from telegram import Update
from telegram.ext import ContextTypes
import pytz
from bot.storage import storage
from bot.i18n import t


def _validate_tz(name: str) -> bool:
    try:
        pytz.timezone(name)
        return True
    except Exception:
        return False


def _local_now(user: dict) -> datetime.datetime:
    tz_name = user.get("timezone", "UTC") or "UTC"
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.UTC
    return datetime.datetime.now(tz)


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/digest on|off|<HH:MM> — manage morning digest preferences."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    if not context.args:
        st = "ON ✅" if user.get("digest_enabled") else "OFF ❌"
        await update.message.reply_text(
            t(lang, "digest_status",
              status=st,
              time=user.get("digest_time", "08:00"),
              tz=user.get("timezone", "UTC")),
            parse_mode="HTML",
        )
        return

    arg = context.args[0].lower()

    if arg in ("on", "вкл"):
        user["digest_enabled"] = True
        await storage.save()
        await update.message.reply_text(
            t(lang, "digest_on",
              time=user.get("digest_time", "08:00"),
              tz=user.get("timezone", "UTC")),
            parse_mode="HTML",
        )
        return

    if arg in ("off", "выкл"):
        user["digest_enabled"] = False
        await storage.save()
        await update.message.reply_text(t(lang, "digest_off"))
        return

    # Maybe HH:MM
    if re.match(r"^\d{1,2}:\d{2}$", arg):
        h, m = arg.split(":")
        try:
            hh, mm = int(h), int(m)
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                user["digest_time"] = f"{hh:02d}:{mm:02d}"
                user["digest_enabled"] = True
                await storage.save()
                await update.message.reply_text(
                    t(lang, "digest_time_set",
                      time=user["digest_time"], tz=user.get("timezone", "UTC")),
                    parse_mode="HTML",
                )
                return
        except ValueError:
            pass

    await update.message.reply_text(t(lang, "digest_bad_arg"), parse_mode="HTML")


async def tz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tz [zone] — set IANA timezone (e.g. Europe/Moscow)."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    if not context.args:
        await update.message.reply_text(
            t(lang, "tz_status", tz=user.get("timezone", "UTC")),
            parse_mode="HTML",
        )
        return

    name = context.args[0]
    if not _validate_tz(name):
        await update.message.reply_text(t(lang, "tz_invalid"), parse_mode="HTML")
        return
    user["timezone"] = name
    await storage.save()
    await update.message.reply_text(
        t(lang, "tz_set", tz=name), parse_mode="HTML",
    )


def _build_digest_message(user: dict, lang: str) -> str:
    """Render the morning digest body for this user."""
    first_name = (user.get("username") or "").strip() or "friend"
    now = _local_now(user)
    today_iso = now.strftime("%Y-%m-%d")

    parts = [t(lang, "digest_greeting", name=html.escape(first_name), date=today_iso)]

    # Pending todos
    tasks = [tk for tk in (user.get("tasks") or []) if not tk.get("done")]
    if tasks:
        section = t(lang, "digest_todos_header") + "\n"
        for i, tk in enumerate(tasks[:3], 1):
            section += f"  {i}. {html.escape(tk.get('text', '')[:120])}\n"
        if len(tasks) > 3:
            section += f"  <i>... +{len(tasks) - 3}</i>\n"
        parts.append(section)

    # Active reminders for today
    reminders = storage.data.get("reminders", []) or []
    uid = user["id"]
    end_of_day_local = now.replace(hour=23, minute=59, second=59)
    end_of_day_ts = end_of_day_local.timestamp()
    today_reminders = [
        r for r in reminders
        if r.get("user_id") == uid and r.get("time", 0) <= end_of_day_ts
    ]
    if today_reminders:
        section = t(lang, "digest_reminders_header") + "\n"
        for r in today_reminders[:5]:
            rt = r.get("time", 0)
            local_dt = datetime.datetime.fromtimestamp(rt, tz=now.tzinfo)
            section += f"  ⏰ <b>{local_dt.strftime('%H:%M')}</b> — {html.escape(r.get('text', '')[:120])}\n"
        parts.append(section)

    # Daily streak
    streak = int(user.get("daily_streak", 0))
    if streak > 0:
        parts.append(t(lang, "digest_streak", days=streak))

    # Weekly rank if in top 10
    try:
        from bot.handlers.base import _iso_week_key
        wk = _iso_week_key()
        all_users = storage.data.get("users", {})
        ranked = sorted(
            all_users.items(),
            key=lambda kv: int(kv[1].get("xp_by_week", {}).get(wk, 0)),
            reverse=True,
        )
        ranked_uids = [u for u, _ in ranked if int(_.get("xp_by_week", {}).get(wk, 0)) > 0]
        if str(uid) in ranked_uids:
            rank = ranked_uids.index(str(uid)) + 1
            if rank <= 10:
                parts.append(t(lang, "digest_weekly_rank", rank=rank))
    except Exception:
        pass

    # CTA
    parts.append(t(lang, "digest_footer"))
    return "\n".join(parts)


async def _maybe_send_digest(bot, user: dict) -> bool:
    """Send the digest if the user's local time matches their digest_time
    window and we haven't already delivered today. Returns True if sent."""
    if not user.get("digest_enabled"):
        return False
    now = _local_now(user)
    today_local = now.strftime("%Y-%m-%d")
    if user.get("last_digest_date") == today_local:
        return False

    target = user.get("digest_time", "08:00")
    try:
        target_h, target_m = (int(x) for x in target.split(":"))
    except (ValueError, AttributeError):
        target_h, target_m = 8, 0

    target_today_local = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
    delta_min = abs((now - target_today_local).total_seconds()) / 60
    if delta_min > 7:
        return False
    # Don't fire if "target time" is more than 1h in the past (e.g. bot was down)
    if now < target_today_local - datetime.timedelta(minutes=7):
        return False

    lang = user.get("language", "ru")
    try:
        text = _build_digest_message(user, lang)
        await bot.send_message(user["id"], text, parse_mode="HTML")
        user["last_digest_date"] = today_local
        return True
    except Exception:
        # Even on failure, mark sent so we don't retry-spam
        user["last_digest_date"] = today_local
        return False


async def morning_digest_scheduler_task(bot):
    """Called by APScheduler every 15 minutes. Iterates opted-in users."""
    users = storage.data.get("users", {})
    sent = 0
    for uid_str, user_obj in list(users.items()):
        if not isinstance(user_obj, dict):
            continue
        try:
            if await _maybe_send_digest(bot, user_obj):
                sent += 1
        except Exception:
            continue
    if sent:
        await storage.save()
