"""Monetization: Telegram Stars + NOWPayments crypto + tiers + partner rewards.

All paid features are gated through tier_active(user, "plus"|"pro") — not the
legacy `vip` boolean (which we keep updated for back-compat with the older code).

Telegram Stars (XTR):
- /buy shows the tier picker with Stars price tags
- callback `tier_stars_<tier>` -> bot.send_invoice(currency='XTR', payload=...)
- pre_checkout_callback always approves (Stars don't bounce)
- successful_payment_callback grants the tier and triggers partner reward

NOWPayments crypto:
- /buycrypto shows the tier picker
- callback `tier_crypto_<tier>` -> POST api.nowpayments.io/v1/invoice
- bot replies with the hosted checkout URL
- Webhook endpoint (bot/server.py) verifies HMAC-SHA512 of the JSON body
  using NOWPAYMENTS_IPN_SECRET, then grants the tier
"""
import asyncio
import datetime
import hashlib
import hmac
import html
import json
import secrets
import time
import aiohttp
from telegram import (
    Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t
from bot.config import (
    TIERS, NOWPAYMENTS_API_KEY, PUBLIC_BASE_URL, PARTNER_REWARD_DAYS,
)


# ====== Tier helpers ======

def tier_active(user: dict, required: str = "plus") -> bool:
    """True if the user has at least `required` tier active right now.
    `required` is one of: 'plus', 'pro'."""
    tier = user.get("tier", "free")
    expires = user.get("tier_expires")
    if tier == "free":
        return False
    # Check expiration
    if expires is not None:
        if time.time() > expires:
            user["tier"] = "free"
            user["tier_expires"] = None
            user["vip"] = False
            return False
    # Tier ordering: free < plus < pro
    order = {"free": 0, "plus": 1, "pro": 2}
    return order.get(tier, 0) >= order.get(required, 1)


def grant_tier(user: dict, tier: str, days: int = 30):
    """Apply a paid tier to the user starting now."""
    if tier not in TIERS or tier == "free":
        return
    now = time.time()
    # Extend from current expiry if still active and same/lower tier
    base = user.get("tier_expires")
    cur_tier = user.get("tier", "free")
    order = {"free": 0, "plus": 1, "pro": 2}
    if (cur_tier == tier or order.get(cur_tier, 0) < order.get(tier, 0)) and base and base > now:
        # Stack on top of remaining time when tier is same or upgrade
        start = base
    else:
        start = now
    expires = start + days * 86400 if days > 0 else None
    user["tier"] = tier
    user["tier_expires"] = expires
    # Back-compat: keep `vip` true if Plus or Pro
    user["vip"] = True
    user["vip_expires"] = expires
    # Reset/credit the monthly image budget
    user["image_credits"] = TIERS[tier]["image_credits"]
    user["image_credits_reset"] = expires if expires else (now + 30 * 86400)


def consume_image_credit(user: dict) -> bool:
    """Decrement one credit. Returns True if the user had a credit to spend."""
    # Refill if past reset point AND tier is still active
    if user.get("tier", "free") != "free":
        reset = float(user.get("image_credits_reset") or 0)
        if reset and time.time() > reset:
            user["image_credits"] = TIERS.get(user["tier"], {}).get("image_credits", 0)
            user["image_credits_reset"] = time.time() + 30 * 86400
    n = int(user.get("image_credits", 0))
    if n <= 0:
        return False
    user["image_credits"] = n - 1
    return True


# ====== Common UI: tier picker ======

def _tier_picker_kb(payment_kind: str, lang: str) -> InlineKeyboardMarkup:
    """Build the tier-picker inline keyboard for either 'stars' or 'crypto'."""
    rows = []
    for tier_id in ("plus", "pro"):
        info = TIERS[tier_id]
        if payment_kind == "stars":
            label = f"⭐ {info['label']} — {info['stars']} Stars"
        else:
            label = f"💎 {info['label']} — ${info['usd']:.2f}"
        rows.append([InlineKeyboardButton(label, callback_data=f"tier_{payment_kind}_{tier_id}")])
    return InlineKeyboardMarkup(rows)


def _tiers_text(lang: str) -> str:
    """Render the tier comparison message."""
    parts = [t(lang, "tier_header")]
    for tier_id, info in TIERS.items():
        feats = "\n".join(f"  • {f}" for f in info["features"])
        if tier_id == "free":
            price = t(lang, "tier_price_free")
        else:
            price = f"⭐ {info['stars']} Stars · 💎 ${info['usd']:.2f} ({info['days']} {t(lang, 'days')})"
        parts.append(f"<b>{info['label']}</b>\n{price}\n{feats}")
    return "\n\n".join(parts)


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show tier comparison + pay-with-Stars buttons."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    text = _tiers_text(lang) + "\n\n" + t(lang, "buy_choose_stars")
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=_tier_picker_kb("stars", lang),
    )


async def buycrypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show tier comparison + pay-with-crypto buttons."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not NOWPAYMENTS_API_KEY:
        await update.message.reply_text(t(lang, "crypto_disabled"), parse_mode="HTML")
        return
    text = _tiers_text(lang) + "\n\n" + t(lang, "buy_choose_crypto")
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=_tier_picker_kb("crypto", lang),
    )


async def vip_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/vip — show current tier and renewal info."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    cur = user.get("tier", "free")
    info = TIERS.get(cur, TIERS["free"])
    if cur == "free":
        status = t(lang, "tier_status_free")
    else:
        exp = user.get("tier_expires")
        if exp:
            until = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d")
            status = t(lang, "tier_status_paid", tier=info["label"], until=until,
                        credits=user.get("image_credits", 0))
        else:
            status = t(lang, "tier_status_paid_forever", tier=info["label"],
                        credits=user.get("image_credits", 0))
    text = status + "\n\n" + _tiers_text(lang) + "\n\n" + t(lang, "buy_hint")
    await update.message.reply_text(text, parse_mode="HTML")


# ====== Telegram Stars flow ======

async def tier_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a Stars invoice when user picks a tier from /buy."""
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    parts = (query.data or "").split("_", 2)
    if len(parts) != 3:
        return
    tier_id = parts[2]
    if tier_id not in TIERS or tier_id == "free":
        return
    info = TIERS[tier_id]

    # Payload encodes intent: "stars:<tier>:<uid>:<nonce>"
    payload = f"stars:{tier_id}:{uid}:{secrets.token_urlsafe(6)}"
    try:
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=t(lang, "invoice_title", tier=info["label"]),
            description=t(lang, "invoice_desc",
                           tier=info["label"], days=info["days"], credits=info["image_credits"]),
            payload=payload,
            provider_token="",     # Stars: provider_token MUST be empty
            currency="XTR",
            prices=[LabeledPrice(label=info["label"], amount=info["stars"])],
        )
    except Exception as e:
        try:
            await query.edit_message_text(t(lang, "invoice_error", err=html.escape(str(e))[:200]),
                                            parse_mode="HTML")
        except Exception:
            pass


async def pre_checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve every Stars pre-checkout immediately — Stars don't fail later."""
    q = update.pre_checkout_query
    try:
        await q.answer(ok=True)
    except Exception:
        pass


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant tier on Stars payment success."""
    msg = update.message
    if not msg or not msg.successful_payment:
        return
    sp = msg.successful_payment
    payload = sp.invoice_payload or ""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    # Parse payload: stars:<tier>:<uid>:<nonce>
    parts = payload.split(":")
    if len(parts) < 3 or parts[0] != "stars":
        return
    tier_id = parts[1]
    if tier_id not in TIERS or tier_id == "free":
        return
    info = TIERS[tier_id]
    grant_tier(user, tier_id, days=info["days"])
    await _award_partner_if_first_paid(context, user)
    await storage.save()
    await msg.reply_text(
        t(lang, "purchase_success",
          tier=info["label"], days=info["days"], credits=info["image_credits"]),
        parse_mode="HTML",
    )


# ====== NOWPayments crypto flow ======

async def tier_crypto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a NOWPayments invoice and reply with the checkout URL."""
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not NOWPAYMENTS_API_KEY:
        try:
            await query.edit_message_text(t(lang, "crypto_disabled"), parse_mode="HTML")
        except Exception:
            pass
        return
    parts = (query.data or "").split("_", 2)
    if len(parts) != 3:
        return
    tier_id = parts[2]
    if tier_id not in TIERS or tier_id == "free":
        return
    info = TIERS[tier_id]

    # The order_id encodes intent so the webhook can find user+tier
    order_id = f"u{uid}-t{tier_id}-{secrets.token_urlsafe(6)}"
    payload = {
        "price_amount": info["usd"],
        "price_currency": "usd",
        "order_id": order_id,
        "order_description": f"AI DISCO BOT {info['label']} ({info['days']} days)",
        "is_fee_paid_by_user": False,
    }
    if PUBLIC_BASE_URL:
        payload["ipn_callback_url"] = f"{PUBLIC_BASE_URL}/webhook/nowpayments"
        payload["success_url"] = f"https://t.me/{(await context.bot.get_me()).username}?start=paid_{order_id}"
        payload["cancel_url"] = f"https://t.me/{(await context.bot.get_me()).username}?start=cancel_{order_id}"
    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post("https://api.nowpayments.io/v1/invoice", headers=headers, json=payload) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    raise RuntimeError(f"NOWPayments HTTP {resp.status}: {data}")
        url = data.get("invoice_url")
        if not url:
            raise RuntimeError("NOWPayments returned no invoice_url")
    except Exception as e:
        try:
            await query.edit_message_text(t(lang, "crypto_error", err=html.escape(str(e))[:200]),
                                            parse_mode="HTML")
        except Exception:
            pass
        return

    # Remember the pending order so the webhook can correlate
    storage.data.setdefault("pending_crypto", {})[order_id] = {
        "user_id": uid, "tier": tier_id, "ts": time.time(),
    }
    # GC stale pending entries (older than 24h)
    cutoff = time.time() - 86400
    pending = storage.data["pending_crypto"]
    for k in [k for k, v in pending.items() if v.get("ts", 0) < cutoff]:
        pending.pop(k, None)
    await storage.save()

    text = t(lang, "crypto_invoice_ready",
             tier=info["label"], usd=info["usd"], url=url)
    try:
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(lang, "crypto_open_btn"), url=url)
            ]]),
            disable_web_page_preview=True,
        )
    except Exception:
        pass


# ====== Webhook: called by NOWPayments after payment status changes ======

def verify_nowpayments_signature(raw_body: bytes, signature_header: str, ipn_secret: str) -> bool:
    """Verify HMAC-SHA512 signature provided in x-nowpayments-sig header."""
    if not signature_header or not ipn_secret:
        return False
    # NOWPayments signs the JSON body after sorting keys alphabetically.
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return False
    canonical = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("utf-8")
    expected = hmac.new(ipn_secret.encode("utf-8"), canonical, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected.lower(), signature_header.strip().lower())


async def handle_nowpayments_webhook(bot, body: dict):
    """Process a verified NOWPayments IPN. Called from the aiohttp server."""
    payment_status = body.get("payment_status")
    order_id = body.get("order_id")
    if not order_id:
        return
    # We grant tier only on 'finished' (full payment confirmed)
    if payment_status not in ("finished", "confirmed"):
        return

    pending = storage.data.get("pending_crypto", {})
    entry = pending.pop(order_id, None)
    if entry is None:
        # Already processed or unknown — skip
        return
    uid = entry["user_id"]
    tier_id = entry["tier"]
    if tier_id not in TIERS or tier_id == "free":
        return

    user = storage.get_user(uid)
    info = TIERS[tier_id]
    grant_tier(user, tier_id, days=info["days"])
    # Pseudo-context for partner reward
    class _Ctx:
        def __init__(self, b):
            self.bot = b
    await _award_partner_if_first_paid(_Ctx(bot), user)
    await storage.save()
    try:
        lang = user.get("language", "ru")
        await bot.send_message(
            uid,
            t(lang, "purchase_success",
              tier=info["label"], days=info["days"], credits=info["image_credits"]),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ====== Partner program ======

async def _award_partner_if_first_paid(context, user: dict):
    """If this is the user's first paid purchase AND they were referred,
    give the referrer PARTNER_REWARD_DAYS of free Plus tier."""
    if user.get("first_paid"):
        return
    user["first_paid"] = True
    referrer_uid = user.get("referred_by")
    if not referrer_uid:
        return
    referrer = storage.data.get("users", {}).get(str(referrer_uid))
    if not referrer:
        return
    grant_tier(referrer, "plus", days=PARTNER_REWARD_DAYS)
    # Notify the referrer
    try:
        ref_lang = referrer.get("language", "ru")
        await context.bot.send_message(
            referrer_uid,
            t(ref_lang, "partner_reward",
              days=PARTNER_REWARD_DAYS,
              name=user.get("username") or "friend"),
            parse_mode="HTML",
        )
    except Exception:
        pass
