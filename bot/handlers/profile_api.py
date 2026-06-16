"""Computed-profile helpers for the Mini App `/api/me` endpoint.

The Mini App's "Level Ring" hero fuses 5 signals into one shape:
tier, level, XP-to-next, streak, and per-day weekly progress.
This module derives those signals from the existing `user` dict so
the API layer stays thin and the bot side keeps using the same fields.
"""
from __future__ import annotations

import datetime
import math
import time
from typing import Any

from bot.config import TIERS, BOT_VERSION


# ---- XP / Level curve ------------------------------------------------------
# xp_for_level(n) = 60 * n^1.5 — Duolingo-style power-law.
# L1: 60, L5: 670, L10: 1,897, L20: 5,366, L50: 21,213.
# At ~700 XP/week (avg user), L5 in ~1 week, L10 in ~1 month.

def xp_for_level(n: int) -> int:
    if n <= 0:
        return 0
    return int(60 * (n ** 1.5))


def level_from_xp(total_xp: int) -> tuple[int, int, int]:
    """Return (level, xp_into_level, xp_needed_for_next_level)."""
    if total_xp <= 0:
        return 1, 0, xp_for_level(1)
    remaining = total_xp
    level = 1
    while True:
        cost = xp_for_level(level)
        if remaining < cost:
            return level, remaining, cost
        remaining -= cost
        level += 1
        if level > 99:
            return 99, 0, xp_for_level(99)


# ---- Aggregations from user dict -------------------------------------------

def _iso_week_key(dt: datetime.datetime | None = None) -> str:
    d = dt or datetime.datetime.utcnow()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def total_xp(user: dict) -> int:
    """Sum of all weekly XP buckets we've kept (last 8 weeks) plus a small
    legacy contribution from `stats.commands` so existing users don't start at L1."""
    weekly = sum(int(v) for v in (user.get("xp_by_week") or {}).values())
    legacy = int(user.get("stats", {}).get("commands", 0)) * 5
    return weekly + legacy


def weekly_xp_by_day(user: dict) -> list[int]:
    """Return XP earned on each of the last 7 days, ordered oldest→newest (Mon→Sun
    relative to today is not used — we return literal last 7 calendar days)."""
    today = datetime.date.today()
    bucket = user.get("xp_by_day") or {}
    out = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        out.append(int(bucket.get(d.isoformat(), 0)))
    return out


def streak_at_risk(user: dict) -> bool:
    """True when the user has a streak but hasn't claimed today AND there are
    less than 2 hours left in UTC day. The Mini App turns the MainButton red
    in this case."""
    streak = int(user.get("daily_streak", 0))
    if streak < 1:
        return False
    today = datetime.date.today().isoformat()
    if user.get("daily_last") == today:
        return False
    now = datetime.datetime.utcnow()
    seconds_left = (24 * 3600) - (now.hour * 3600 + now.minute * 60 + now.second)
    return seconds_left < 2 * 3600


def claimed_today(user: dict) -> bool:
    return user.get("daily_last") == datetime.date.today().isoformat()


def leaderboard_rank(all_users: dict, target_uid: str) -> tuple[int | None, int | None]:
    """Return (current_rank, delta_since_last_week). Rank is 1-indexed.
    None if user has no XP this week."""
    wk_now = _iso_week_key()
    last_wk_dt = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    wk_last = _iso_week_key(last_wk_dt)

    def score_for(u: dict, wk: str) -> int:
        return int(u.get("xp_by_week", {}).get(wk, 0))

    now_ranked = sorted(
        all_users.items(),
        key=lambda kv: score_for(kv[1], wk_now),
        reverse=True,
    )
    now_ranked = [(uid, u) for (uid, u) in now_ranked if score_for(u, wk_now) > 0]
    rank_now = None
    for i, (uid, _) in enumerate(now_ranked, 1):
        if uid == target_uid:
            rank_now = i
            break

    last_ranked = sorted(
        all_users.items(),
        key=lambda kv: score_for(kv[1], wk_last),
        reverse=True,
    )
    last_ranked = [(uid, u) for (uid, u) in last_ranked if score_for(u, wk_last) > 0]
    rank_last = None
    for i, (uid, _) in enumerate(last_ranked, 1):
        if uid == target_uid:
            rank_last = i
            break

    if rank_now and rank_last:
        return rank_now, rank_last - rank_now  # positive = climbed
    return rank_now, None


# ---- The big extended-profile assembler ------------------------------------

def assemble_profile(
    user: dict,
    all_users: dict,
    target_uid: str,
    tg_first_name: str | None,
) -> dict[str, Any]:
    """Build the full /api/me response."""
    xp = total_xp(user)
    level, xp_into, xp_next = level_from_xp(xp)
    streak = int(user.get("daily_streak", 0))
    tier = user.get("tier", "free")
    rank_now, rank_delta = leaderboard_rank(all_users, target_uid)
    tier_info = TIERS.get(tier, TIERS["free"])

    # First-name preference: TG name (current API call) > stored profile > id
    first_name = (tg_first_name or "").strip() or user.get("first_name") or "you"

    # Recent commands log — derive from /api/me/recent if needed, but we have
    # nothing per-user (commands count is global). Surface the per-day XP for
    # "Today" instead.
    today_xp = weekly_xp_by_day(user)[-1]

    # Personas — pull names from wow.py
    try:
        from bot.handlers.wow import PERSONAS
        personas = list(PERSONAS.keys())
    except Exception:
        personas = ["default"]

    return {
        # Identity
        "first_name": first_name,
        "lang": user.get("language", "en"),
        "version": BOT_VERSION,

        # Tier / billing
        "tier": tier,
        "tier_label": tier_info.get("label", "Free"),
        "tier_renews_at": user.get("tier_expires"),
        "image_credits": int(user.get("image_credits", 0)),
        "image_credits_max": int(tier_info.get("image_credits", 0)),

        # Progression
        "xp_total": xp,
        "xp_current": xp_into,
        "xp_for_next": xp_next,
        "level": level,
        "last_seen_level": int(user.get("last_seen_level", 0)),

        # Streak
        "streak_days": streak,
        "streak_at_risk": streak_at_risk(user),
        "claimed_today": claimed_today(user),
        "today_xp": today_xp,

        # Weekly histogram (7 ints, oldest→newest)
        "weekly_xp_by_day": weekly_xp_by_day(user),

        # Social
        "leaderboard_rank": rank_now,
        "rank_delta_week": rank_delta,
        "referrals": int(user.get("referrals", 0)),
        "referral_code": str(target_uid),

        # Settings
        "persona": user.get("persona", "default"),
        "personas": personas,
        "ai_provider": user.get("ai_provider", "gemini"),

        # Content (truncated for payload size)
        "memory": dict(list((user.get("memory") or {}).items())[:50]),
        "memory_count": len(user.get("memory") or {}),
        "notes": [
            {"id": i, "text": (n.get("text", "")[:240])}
            for i, n in enumerate(user.get("notes") or [])
        ][:30],
        "notes_count": len(user.get("notes") or []),

        # Server time for client to avoid clock-skew on "at risk" countdown
        "server_time": int(time.time()),
    }
