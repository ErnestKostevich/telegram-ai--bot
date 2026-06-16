"""HTTP server that runs alongside the polling bot.

Public endpoints:
  GET    /                       — health
  GET    /healthz                — JSON health
  POST   /webhook/nowpayments    — NOWPayments IPN (HMAC-verified)
  GET    /webapp                 — Telegram Mini App shell HTML

Mini-App API (all auth via Telegram initData HMAC):
  POST   /api/me                 — extended profile (the dashboard payload)
  POST   /api/claim-daily        — claim today's reward, +50–200 XP, bumps streak
  POST   /api/seen-level         — mark level as seen, suppress confetti next open
  POST   /api/settings           — patch {lang?, persona?}
  POST   /api/memory             — add {key, value}
  POST   /api/memory/delete      — delete {key}
  POST   /api/topup/stars        — return Stars invoice URL for tg.openInvoice()
  POST   /api/topup/crypto       — return NOWPayments invoice URL
  POST   /api/quick-action       — log intent (ask / image / note / search)
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.parse

import aiohttp
from aiohttp import web

from bot.config import (
    NOWPAYMENTS_IPN_SECRET,
    NOWPAYMENTS_API_KEY,
    PUBLIC_BASE_URL,
    WEBHOOK_PORT,
    BOT_VERSION,
    TIERS,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Health + NOWPayments webhook (unchanged behaviour)
# ===========================================================================

async def _root(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def _healthz(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "version": BOT_VERSION})


async def _nowpayments_webhook(request: web.Request) -> web.Response:
    sig = request.headers.get("x-nowpayments-sig", "")
    raw = await request.read()

    from bot.handlers.payments import verify_nowpayments_signature, handle_nowpayments_webhook
    if not verify_nowpayments_signature(raw, sig, NOWPAYMENTS_IPN_SECRET):
        logger.warning("NOWPayments webhook: signature mismatch")
        return web.Response(status=401, text="bad signature")
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:
        return web.Response(status=400, text="bad json")

    bot = request.app["bot"]
    try:
        await handle_nowpayments_webhook(bot, body)
    except Exception as e:
        # Return 500 → NOWPayments retries. Handler is idempotent on `pending_crypto`.
        logger.exception(f"NOWPayments webhook handler error: {e}")
        return web.Response(status=500, text="handler error")
    return web.Response(text="ok")


# ===========================================================================
# Telegram WebApp initData verification
# ===========================================================================

def _verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Verify per Telegram's WebApp spec. Returns parsed `user` dict if OK."""
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, strict_parsing=False))
    except Exception:
        return None
    hash_received = parsed.pop("hash", None)
    if not hash_received:
        return None
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"),
                          hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check.encode("utf-8"),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, hash_received):
        return None
    user_json = parsed.get("user")
    if not user_json:
        return None
    try:
        return json.loads(user_json)
    except Exception:
        return None


async def _authed(request: web.Request) -> tuple[dict | None, dict | None]:
    """Pull initData from JSON body, verify, return (user_info, body) or (None, None).
    If invalid, the caller should return 401."""
    try:
        body = await request.json()
    except Exception:
        return None, None
    init_data = body.get("init_data", "")
    user_info = _verify_telegram_init_data(init_data, request.app["bot_token"])
    if not user_info:
        return None, None
    return user_info, body


# ===========================================================================
# /api/me — the big dashboard payload
# ===========================================================================

async def _api_me(request: web.Request) -> web.Response:
    user_info, _ = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)

    from bot.storage import storage
    from bot.handlers.profile_api import assemble_profile

    uid = str(int(user_info["id"]))
    user = storage.get_user(int(uid))
    payload = assemble_profile(
        user=user,
        all_users=storage.data.get("users", {}),
        target_uid=uid,
        tg_first_name=user_info.get("first_name"),
    )
    return web.json_response(payload)


# ===========================================================================
# /api/claim-daily — same logic as /daily command, but idempotent for the
# Mini App auto-claim on open.
# ===========================================================================

async def _api_claim_daily(request: web.Request) -> web.Response:
    user_info, _ = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)

    from bot.storage import storage
    from bot.handlers.base import award_weekly_xp
    from bot.handlers.profile_api import assemble_profile

    uid = str(int(user_info["id"]))
    user = storage.get_user(int(uid))

    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    last = user.get("daily_last")
    already = (last == today)

    bonus_xp = 0
    if not already:
        streak = int(user.get("daily_streak", 0))
        streak = streak + 1 if last == yesterday else 1
        bonus_xp = min(50 + (streak - 1) * 10, 200)
        user["daily_last"] = today
        user["daily_streak"] = streak
        award_weekly_xp(user, bonus_xp)
        await storage.save()

    return web.json_response({
        "already_claimed": already,
        "bonus_xp": bonus_xp,
        "profile": assemble_profile(
            user=user,
            all_users=storage.data.get("users", {}),
            target_uid=uid,
            tg_first_name=user_info.get("first_name"),
        ),
    })


# ===========================================================================
# /api/seen-level — suppress confetti replay
# ===========================================================================

async def _api_seen_level(request: web.Request) -> web.Response:
    user_info, body = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)

    from bot.storage import storage
    user = storage.get_user(int(user_info["id"]))
    level = int(body.get("level", 0))
    if level > int(user.get("last_seen_level", 0)):
        user["last_seen_level"] = level
        await storage.save()
    return web.json_response({"ok": True, "last_seen_level": user["last_seen_level"]})


# ===========================================================================
# /api/settings — patch language and persona
# ===========================================================================

async def _api_settings(request: web.Request) -> web.Response:
    user_info, body = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)

    from bot.storage import storage
    from bot.i18n import SUPPORTED_LANGS
    from bot.handlers.wow import PERSONAS

    user = storage.get_user(int(user_info["id"]))
    changed = False
    new_lang = body.get("lang")
    if new_lang in SUPPORTED_LANGS and new_lang != user.get("language"):
        user["language"] = new_lang
        changed = True
    new_persona = body.get("persona")
    if new_persona in PERSONAS and new_persona != user.get("persona"):
        user["persona"] = new_persona
        changed = True
    if changed:
        await storage.save()
    return web.json_response({
        "ok": True,
        "lang": user.get("language", "en"),
        "persona": user.get("persona", "default"),
    })


# ===========================================================================
# /api/memory + /api/memory/delete — single-row memory edits
# ===========================================================================

_KEY_MAX = 60
_VALUE_MAX = 240


async def _api_memory_add(request: web.Request) -> web.Response:
    user_info, body = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)
    key = (body.get("key") or "").strip()[:_KEY_MAX]
    value = (body.get("value") or "").strip()[:_VALUE_MAX]
    if not key or not value:
        return web.json_response({"error": "empty"}, status=400)

    from bot.storage import storage
    user = storage.get_user(int(user_info["id"]))
    mem = user.setdefault("memory", {})
    if len(mem) >= 100 and key not in mem:
        return web.json_response({"error": "memory_full"}, status=409)
    mem[key] = value
    await storage.save()
    return web.json_response({"ok": True, "memory": mem})


async def _api_memory_delete(request: web.Request) -> web.Response:
    user_info, body = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)
    key = (body.get("key") or "").strip()
    from bot.storage import storage
    user = storage.get_user(int(user_info["id"]))
    mem = user.setdefault("memory", {})
    mem.pop(key, None)
    await storage.save()
    return web.json_response({"ok": True, "memory": mem})


# ===========================================================================
# /api/topup/stars — Stars invoice link (opens via tg.openInvoice)
# ===========================================================================

async def _api_topup_stars(request: web.Request) -> web.Response:
    user_info, body = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)

    from telegram import LabeledPrice

    tier_id = body.get("tier", "plus")
    if tier_id not in TIERS or tier_id == "free":
        return web.json_response({"error": "bad_tier"}, status=400)
    info = TIERS[tier_id]

    uid = int(user_info["id"])
    payload = f"stars:{tier_id}:{uid}:{secrets.token_urlsafe(6)}"
    bot = request.app["bot"]
    try:
        url = await bot.create_invoice_link(
            title=f"AI DISCO BOT {info['label']}",
            description=f"{info['days']} days · {info['image_credits']} image credits",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=info["label"], amount=info["stars"])],
        )
    except Exception as e:
        logger.exception(f"Stars invoice link failed: {e}")
        return web.json_response({"error": "invoice_failed"}, status=500)

    return web.json_response({"invoice_url": url, "tier": tier_id, "stars": info["stars"]})


# ===========================================================================
# /api/topup/crypto — NOWPayments invoice URL
# ===========================================================================

async def _api_topup_crypto(request: web.Request) -> web.Response:
    user_info, body = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)
    if not NOWPAYMENTS_API_KEY:
        return web.json_response({"error": "crypto_disabled"}, status=503)
    tier_id = body.get("tier", "plus")
    if tier_id not in TIERS or tier_id == "free":
        return web.json_response({"error": "bad_tier"}, status=400)
    info = TIERS[tier_id]
    uid = int(user_info["id"])

    order_id = f"u{uid}-t{tier_id}-{secrets.token_urlsafe(6)}"
    np_payload = {
        "price_amount": info["usd"],
        "price_currency": "usd",
        "order_id": order_id,
        "order_description": f"AI DISCO BOT {info['label']} ({info['days']} days)",
        "is_fee_paid_by_user": False,
    }
    if PUBLIC_BASE_URL:
        np_payload["ipn_callback_url"] = f"{PUBLIC_BASE_URL}/webhook/nowpayments"

    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
            async with s.post("https://api.nowpayments.io/v1/invoice",
                              headers=headers, json=np_payload) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    return web.json_response(
                        {"error": "nowpayments_error", "detail": data},
                        status=502,
                    )
        url = data.get("invoice_url")
        if not url:
            return web.json_response({"error": "no_invoice_url"}, status=502)
    except Exception as e:
        logger.exception(f"NOWPayments error: {e}")
        return web.json_response({"error": "network"}, status=502)

    from bot.storage import storage
    storage.data.setdefault("pending_crypto", {})[order_id] = {
        "user_id": uid, "tier": tier_id, "ts": time.time(),
    }
    await storage.save()
    return web.json_response({"invoice_url": url, "tier": tier_id, "usd": info["usd"]})


# ===========================================================================
# /api/quick-action — log intent. The Mini App calls this then tg.close()
# so the user lands back in the chat to use the command.
# ===========================================================================

async def _api_quick_action(request: web.Request) -> web.Response:
    user_info, body = await _authed(request)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)
    action = (body.get("action") or "").strip().lower()
    if action not in {"ask", "image", "note", "search", "memory"}:
        return web.json_response({"error": "bad_action"}, status=400)
    # We don't persist this — purely a hook for analytics later.
    return web.json_response({"ok": True, "action": action})


# ===========================================================================
# Mini App shell (the new beautiful one — single HTML doc)
# ===========================================================================

async def _webapp_dashboard(request: web.Request) -> web.Response:
    return web.Response(text=_MINIAPP_HTML, content_type="text/html")


# ===========================================================================
# Wire up
# ===========================================================================

async def start_webhook_server(application):
    app = web.Application()
    app["bot"] = application.bot
    app["bot_token"] = application.bot.token

    app.router.add_get("/", _root)
    app.router.add_get("/healthz", _healthz)
    app.router.add_post("/webhook/nowpayments", _nowpayments_webhook)
    app.router.add_get("/webapp", _webapp_dashboard)
    # API
    app.router.add_post("/api/me", _api_me)
    # back-compat: the old endpoint just returned the basic profile too
    app.router.add_post("/api/profile", _api_me)
    app.router.add_post("/api/claim-daily", _api_claim_daily)
    app.router.add_post("/api/seen-level", _api_seen_level)
    app.router.add_post("/api/settings", _api_settings)
    app.router.add_post("/api/memory", _api_memory_add)
    app.router.add_post("/api/memory/delete", _api_memory_delete)
    app.router.add_post("/api/topup/stars", _api_topup_stars)
    app.router.add_post("/api/topup/crypto", _api_topup_crypto)
    app.router.add_post("/api/quick-action", _api_quick_action)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logger.info(f"HTTP server listening on 0.0.0.0:{WEBHOOK_PORT}")
    return runner


# ===========================================================================
# THE MINI APP — single self-contained HTML doc.
# Spec source: design synthesis = Progress Engine + minimal-zen polish +
# iridescent tier ring. Killer feature: The Level Ring (5 signals → 1 shape).
# Vanilla CSS+JS. No framework, no build, no external libs except
# telegram-web-app.js.
# ===========================================================================

_MINIAPP_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>AI DISCO</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  /* ===========================================================================
     Design tokens — dark-first, light supported. Bridged from Telegram theme.
     Synthesis: dark = #0E1116 / surface #161B22 / accent --xp #A78BFA
     Light = warm #FAFAF9 / surface #FFFFFF / borders only (no shadows).
  =========================================================================== */
  :root {
    --bg:           #0E1116;
    --surface:      #161B22;
    --surface-2:    #1F262F;
    --border:       rgba(255,255,255,.08);
    --text:         #F0F3F8;
    --text-dim:     #8B95A5;
    --text-faint:   #6B7280;
    --xp:           #A78BFA;
    --xp-soft:      rgba(167,139,250,.16);
    --tier-free:    #6B7280;
    --tier-plus-a:  #60A5FA;
    --tier-plus-b:  #A78BFA;
    --tier-pro-a:   #FBBF24;
    --tier-pro-b:   #F472B6;
    --tier-pro-c:   #34D399;
    --streak-1:     #FCD34D;
    --streak-2:     #FB923C;
    --streak-3:     #EF4444;
    --streak-4:     #A855F7;
    --credit-full:  #34D399;
    --credit-mid:   #FBBF24;
    --credit-low:   #EF4444;
    --success:      #34D399;
    --danger:       #EF4444;
    --r-sm: 8px;
    --r-md: 12px;
    --r-lg: 16px;
    --r-xl: 24px;
    --ease-silk: cubic-bezier(.32,.72,0,1);
    --ease-overshoot: cubic-bezier(.34,1.56,.64,1);
  }
  :root[data-theme="light"] {
    --bg:           #FAFAF9;
    --surface:      #FFFFFF;
    --surface-2:    #F4F4F2;
    --border:       #ECEAE6;
    --text:         #1C1B1A;
    --text-dim:     #6B6864;
    --text-faint:   #A8A5A0;
    --xp-soft:      rgba(167,139,250,.10);
  }

  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
               font-family: 'Inter', -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
               font-size: 15px; line-height: 22px; font-weight: 400;
               overscroll-behavior-y: contain; }
  body { padding: 0 16px 96px; max-width: 480px; margin: 0 auto; }

  .mono { font-family: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
          font-variant-numeric: tabular-nums; }
  .display { font-size: 56px; line-height: 60px; font-weight: 800; letter-spacing: -.02em; }
  .title   { font-size: 20px; line-height: 26px; font-weight: 600; letter-spacing: -.015em; }
  .heading { font-size: 15px; line-height: 20px; font-weight: 600; }
  .caption { font-size: 13px; line-height: 18px; font-weight: 500; color: var(--text-dim); }
  .micro   { font-size: 11px; line-height: 14px; font-weight: 500;
             letter-spacing: .06em; text-transform: uppercase; color: var(--text-faint); }

  /* ===== Header ===== */
  .hdr { display: flex; align-items: center; justify-content: space-between;
         padding: 16px 0; gap: 12px; }
  .hdr h1 { margin: 0; font-size: 16px; font-weight: 600; letter-spacing: .04em;
            text-transform: uppercase; opacity: .8; }
  .hdr .lang-sel {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-md); padding: 6px 10px; color: var(--text);
    font-size: 13px; font-weight: 500; cursor: pointer;
    appearance: none; -webkit-appearance: none;
    background-image: linear-gradient(45deg, transparent 50%, var(--text-dim) 50%),
                      linear-gradient(135deg, var(--text-dim) 50%, transparent 50%);
    background-position: calc(100% - 16px) 13px, calc(100% - 11px) 13px;
    background-size: 5px 5px; background-repeat: no-repeat;
    padding-right: 28px;
  }

  /* ===== HERO: Level Ring (the killer feature) ===== */
  .hero { display: flex; flex-direction: column; align-items: center;
          padding: 20px 0 8px; position: relative; min-height: 200px; }
  .ring-wrap { width: 200px; height: 200px; position: relative; cursor: pointer;
               perspective: 800px; transform-style: preserve-3d; }
  .ring-wrap .face { position: absolute; inset: 0; transition: transform .6s var(--ease-silk);
                     backface-visibility: hidden; transform-style: preserve-3d; }
  .ring-wrap .face.back { transform: rotateY(180deg); }
  .ring-wrap.flipped .face.front { transform: rotateY(180deg); }
  .ring-wrap.flipped .face.back  { transform: rotateY(360deg); }

  .ring-svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .ring-track { fill: none; stroke: var(--surface-2); stroke-width: 8; }
  .ring-progress { fill: none; stroke: var(--xp); stroke-width: 8; stroke-linecap: round;
                   stroke-dasharray: 552;
                   stroke-dashoffset: 552;
                   transition: stroke-dashoffset .9s var(--ease-overshoot); }
  /* Tier ring on Plus / Pro: a conic SVG ring overlay via mask. */
  .tier-conic { position: absolute; inset: 0; border-radius: 50%;
                opacity: 0; transition: opacity .4s;
                -webkit-mask: radial-gradient(circle, transparent 78px, #000 78px, #000 92px, transparent 92px);
                        mask: radial-gradient(circle, transparent 78px, #000 78px, #000 92px, transparent 92px); }
  [data-tier="plus"] .tier-conic { opacity: 1;
    background: conic-gradient(from 0deg, var(--tier-plus-a), var(--tier-plus-b), var(--tier-plus-a));
    animation: spin 8s linear infinite; }
  [data-tier="pro"] .tier-conic { opacity: 1;
    background: conic-gradient(from 0deg, var(--tier-pro-a), var(--tier-pro-b), var(--tier-pro-c), var(--tier-pro-a));
    animation: spin 4s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Streak ticks orbit at radius 100, container is 200x200 → center 100,100. */
  .ring-ticks { position: absolute; inset: 0; }
  .ring-ticks circle { fill: var(--surface-2); }
  .ring-ticks circle.lit { fill: var(--streak-1); filter: drop-shadow(0 0 4px var(--streak-1)); }
  [data-streak-tier="2"] .ring-ticks circle.lit { fill: var(--streak-2); filter: drop-shadow(0 0 5px var(--streak-2)); }
  [data-streak-tier="3"] .ring-ticks circle.lit { fill: var(--streak-3); filter: drop-shadow(0 0 6px var(--streak-3)); }
  [data-streak-tier="4"] .ring-ticks circle.lit { fill: var(--streak-4); filter: drop-shadow(0 0 8px var(--streak-4)); }

  /* Level number inside ring */
  .ring-center { position: absolute; inset: 0; display: flex; flex-direction: column;
                 align-items: center; justify-content: center; gap: 2px; }
  .ring-center .lv-label { font-size: 11px; letter-spacing: .12em; color: var(--text-faint); text-transform: uppercase; }
  .ring-center .lv-num { font-size: 52px; line-height: 52px; font-weight: 800;
                         font-variant-numeric: tabular-nums; }
  .ring-center .first-name { margin-top: 4px; font-size: 12px; color: var(--text-dim);
                             max-width: 120px; text-overflow: ellipsis; overflow: hidden;
                             white-space: nowrap; text-align: center; }

  /* Back face content */
  .ring-back { position: absolute; inset: 0; display: flex; flex-direction: column;
               align-items: center; justify-content: center; padding: 30px;
               text-align: center; gap: 6px; }
  .ring-back .big { font-size: 24px; font-weight: 700; }
  .ring-back small { color: var(--text-dim); font-size: 11px; }
  .ring-back .earn-line { font-size: 12px; color: var(--text-dim); line-height: 16px; }

  /* XP progress line below hero */
  .xp-line { text-align: center; margin: 14px 0 2px; font-size: 14px; color: var(--text-dim); }
  .xp-line .curr { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }
  .xp-line .to-next { color: var(--xp); font-weight: 600; margin-left: 4px; }

  /* ===== Stat strip: Streak + Credits ===== */
  .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 20px; }
  .stat { background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--r-lg); padding: 16px; display: flex; flex-direction: column;
          gap: 6px; min-height: 90px; }
  .stat .row { display: flex; align-items: center; gap: 8px; }
  .stat .flame, .stat .battery { width: 28px; height: 28px; flex: 0 0 28px;
                                  display: inline-flex; align-items: center; justify-content: center; }
  .stat b { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .stat small { font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
                color: var(--text-faint); font-weight: 500; }
  .stat[data-kind="credits-low"] .battery-fill { background: var(--credit-low);
                                                 animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: .55; } }
  .battery-frame { width: 30px; height: 16px; border: 1.5px solid var(--text-dim);
                   border-radius: 3px; position: relative; padding: 1.5px; }
  .battery-frame::after { content: ''; position: absolute; right: -3.5px; top: 5px;
                          width: 2px; height: 6px; background: var(--text-dim); border-radius: 0 1px 1px 0; }
  .battery-fill { display: block; height: 100%; border-radius: 1.5px;
                  background: var(--credit-full); transition: width .8s var(--ease-silk); }
  .flame svg { width: 26px; height: 26px; }
  .flame .flame-core { animation: flicker 1.6s ease-in-out infinite alternate; transform-origin: center bottom; }
  @keyframes flicker { from { transform: scaleY(1) translateY(0); } to { transform: scaleY(1.05) translateY(-1px); } }

  /* ===== Tier card ===== */
  .tier-card { margin-top: 14px; background: var(--surface); border: 1px solid var(--border);
               border-radius: var(--r-lg); padding: 16px; display: flex; align-items: center;
               justify-content: space-between; gap: 12px; cursor: pointer;
               transition: border-color .2s; }
  .tier-card:active { border-color: var(--xp); }
  .tier-card .name { font-size: 16px; font-weight: 700; letter-spacing: .02em; }
  .tier-card[data-t="plus"] .name { background: linear-gradient(90deg, var(--tier-plus-a), var(--tier-plus-b));
                                    -webkit-background-clip: text; background-clip: text; color: transparent; }
  .tier-card[data-t="pro"] .name { background: linear-gradient(90deg, var(--tier-pro-a), var(--tier-pro-b), var(--tier-pro-c));
                                   -webkit-background-clip: text; background-clip: text; color: transparent; }
  .tier-card .renews { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
  .tier-card .arrow { font-size: 18px; color: var(--text-dim); }

  /* ===== Weekly histogram ===== */
  .week { margin-top: 14px; background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--r-lg); padding: 16px; }
  .week header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
  .week header b { font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
                   color: var(--text-faint); font-weight: 500; }
  .week .rank { font-size: 13px; font-weight: 600; }
  .week .rank.up { color: var(--success); }
  .week .rank.down { color: var(--danger); }
  .week .bars { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; height: 56px;
                align-items: flex-end; }
  .week .bar { background: var(--xp-soft); border-radius: 4px 4px 0 0; position: relative;
               min-height: 6px; transition: height .8s var(--ease-overshoot); }
  .week .bar.today { background: var(--xp); }
  .week .bar.today::after { content: ''; position: absolute; inset: 0;
                            background: var(--xp); border-radius: 4px 4px 0 0;
                            animation: breath 2s ease-in-out infinite; }
  @keyframes breath { 50% { opacity: .65; } }
  .week .labels { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; margin-top: 6px; }
  .week .labels span { font-size: 10px; color: var(--text-faint); text-align: center;
                       text-transform: uppercase; letter-spacing: .04em; }

  /* ===== Referrals ===== */
  .refs { margin-top: 14px; background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--r-lg); padding: 16px; }
  .refs .row { display: flex; justify-content: space-between; align-items: center; }
  .refs .count { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .refs .delta { font-size: 12px; color: var(--success); margin-left: 8px; }
  .refs .copy-btn { background: var(--xp-soft); color: var(--xp); border: 0; padding: 10px 14px;
                    border-radius: var(--r-md); font-weight: 600; font-size: 13px; cursor: pointer;
                    transition: transform .15s; width: 100%; margin-top: 12px; }
  .refs .copy-btn:active { transform: scale(.97); }
  .refs .copy-btn.copied { background: var(--success); color: #0E1116; }

  /* ===== Quick actions ===== */
  .quick { margin-top: 14px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .quick button { background: var(--surface); border: 1px solid var(--border);
                  border-radius: var(--r-md); padding: 14px 4px; color: var(--text);
                  font-size: 12px; font-weight: 500; cursor: pointer;
                  display: flex; flex-direction: column; align-items: center; gap: 6px;
                  transition: transform .15s, border-color .2s; }
  .quick button:active { transform: scale(.95); border-color: var(--xp); }
  .quick button svg { width: 20px; height: 20px; }

  /* ===== Memory section (collapsible) ===== */
  .section { margin-top: 18px; border-top: 1px solid var(--border); }
  .section .head { width: 100%; background: none; border: 0; color: var(--text);
                   display: flex; align-items: center; justify-content: space-between;
                   padding: 18px 0; cursor: pointer; }
  .section .head .left { display: flex; align-items: center; gap: 10px; }
  .section .head .left svg { width: 18px; height: 18px; color: var(--text-dim); }
  .section .head .name { font-size: 15px; font-weight: 600; }
  .section .head .count { font-size: 13px; color: var(--text-dim); margin-left: 4px; }
  .section .head .chev { transition: transform .2s; color: var(--text-dim); }
  .section.open .head .chev { transform: rotate(180deg); }
  .section .body { display: none; padding-bottom: 18px; }
  .section.open .body { display: block; animation: slideDown .25s var(--ease-silk); }
  @keyframes slideDown { from { opacity: 0; transform: translateY(-4px); } }

  .memo-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
  .memo-row { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-md);
              padding: 10px 12px; display: flex; justify-content: space-between; align-items: center;
              gap: 12px; }
  .memo-row .k { font-weight: 600; font-size: 13px; min-width: 0; }
  .memo-row .v { color: var(--text-dim); font-size: 13px; min-width: 0;
                 flex: 1; text-align: right;
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .memo-row button { background: transparent; border: 0; color: var(--text-faint); font-size: 18px;
                     cursor: pointer; padding: 0 4px; line-height: 1; transition: color .15s; }
  .memo-row button:hover, .memo-row button:active { color: var(--danger); }

  .memo-form { display: flex; gap: 8px; margin-top: 12px; }
  .memo-form input { flex: 1; background: var(--surface); border: 1px solid var(--border);
                     border-radius: var(--r-md); padding: 10px 12px; color: var(--text);
                     font-size: 14px; font-family: inherit; min-width: 0; }
  .memo-form input:focus { outline: none; border-color: var(--xp); }
  .memo-form button { background: var(--xp); color: #fff; border: 0; border-radius: var(--r-md);
                      padding: 10px 16px; font-weight: 600; cursor: pointer; font-size: 14px; }

  .persona-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
  .persona-row { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-md);
                 padding: 10px 12px; display: flex; justify-content: space-between; align-items: center;
                 cursor: pointer; transition: border-color .15s; }
  .persona-row.active { border-color: var(--xp); background: var(--xp-soft); }
  .persona-row .nm { font-weight: 500; text-transform: capitalize; font-size: 14px; }
  .persona-row .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--surface-2); }
  .persona-row.active .dot { background: var(--xp); }

  /* ===== Top-up bottom sheet ===== */
  .scrim { position: fixed; inset: 0; background: rgba(0,0,0,.5); opacity: 0;
           transition: opacity .25s; pointer-events: none; z-index: 50; }
  .scrim.open { opacity: 1; pointer-events: auto; }
  .sheet { position: fixed; left: 0; right: 0; bottom: 0; background: var(--bg);
           border-top: 1px solid var(--border);
           border-radius: var(--r-xl) var(--r-xl) 0 0;
           padding: 12px 20px 32px; transform: translateY(100%);
           transition: transform .32s var(--ease-silk); z-index: 51;
           max-width: 480px; margin: 0 auto; max-height: 88vh; overflow-y: auto; }
  .sheet.open { transform: translateY(0); }
  .sheet .grabber { width: 36px; height: 4px; background: var(--surface-2); border-radius: 2px;
                    margin: 0 auto 12px; }
  .sheet h2 { margin: 0 0 6px; font-size: 18px; font-weight: 700; }
  .sheet .lead { color: var(--text-dim); font-size: 13px; margin-bottom: 18px; }
  .tier-pick { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .tier-opt { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
              padding: 14px; cursor: pointer; transition: border-color .15s, transform .15s;
              display: flex; flex-direction: column; gap: 4px; }
  .tier-opt:active { transform: scale(.98); }
  .tier-opt.sel { border-color: var(--xp); }
  .tier-opt .nm { font-weight: 700; font-size: 15px; }
  .tier-opt .price { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .tier-opt .price small { font-size: 11px; font-weight: 500; color: var(--text-dim); }
  .tier-opt .feat { font-size: 11px; color: var(--text-dim); line-height: 15px; }
  .pay-routes { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 18px; }
  .pay-routes button { background: var(--surface); border: 1px solid var(--border);
                       border-radius: var(--r-md); padding: 14px; color: var(--text);
                       font-size: 14px; font-weight: 600; cursor: pointer;
                       display: flex; flex-direction: column; gap: 4px; align-items: center; }
  .pay-routes button:active { transform: scale(.97); border-color: var(--xp); }
  .pay-routes button .sub { font-size: 11px; color: var(--text-dim); font-weight: 500; }

  /* ===== Confetti canvas (level-up moment) ===== */
  #confetti { position: fixed; inset: 0; pointer-events: none; z-index: 100; }

  /* ===== Toast ===== */
  .toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%) translateY(40px);
           background: var(--surface-2); color: var(--text); padding: 10px 16px;
           border-radius: var(--r-md); border: 1px solid var(--border);
           font-size: 13px; font-weight: 500; opacity: 0; transition: transform .25s, opacity .25s;
           z-index: 60; box-shadow: 0 8px 24px rgba(0,0,0,.3); pointer-events: none; }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

  /* ===== Footer ===== */
  .footer { text-align: center; padding: 32px 0 0; font-size: 11px;
            color: var(--text-faint); letter-spacing: .08em; text-transform: uppercase; }

  /* ===== Loading skeleton ===== */
  .skeleton { animation: skeleton 1.4s ease-in-out infinite; }
  @keyframes skeleton { 0%, 100% { opacity: .4; } 50% { opacity: .7; } }

  /* ===== Reduced motion ===== */
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition-duration: 0ms !important; }
  }
</style>
</head>
<body>

<div id="loading" class="hero">
  <div class="ring-wrap skeleton" style="background: var(--surface-2); border-radius: 50%;"></div>
</div>

<div id="app" hidden>
  <header class="hdr">
    <h1>AI DISCO</h1>
    <select class="lang-sel" id="langSel" aria-label="Language">
      <option value="en">EN</option>
      <option value="ru">RU</option>
      <option value="it">IT</option>
    </select>
  </header>

  <section class="hero" id="hero" data-tier="free" data-streak-tier="1">
    <div class="ring-wrap" id="ringWrap">
      <div class="face front">
        <div class="tier-conic"></div>
        <svg class="ring-svg" viewBox="0 0 200 200">
          <circle class="ring-track" cx="100" cy="100" r="88"/>
          <circle class="ring-progress" id="ringProgress" cx="100" cy="100" r="88"/>
        </svg>
        <svg class="ring-ticks" id="ringTicks" viewBox="0 0 200 200"></svg>
        <div class="ring-center">
          <div class="lv-label" data-i18n="level">LEVEL</div>
          <div class="lv-num" id="lvNum">1</div>
          <div class="first-name" id="firstName">—</div>
        </div>
      </div>
      <div class="face back">
        <div class="ring-back">
          <div class="big" id="backNext">+0 XP</div>
          <small data-i18n="to_next">to next level</small>
          <div class="earn-line" id="earnLine">/ask +5 · /img +15 · daily +50</div>
          <small style="margin-top: 6px;" data-i18n="tap_flip">Tap to flip back</small>
        </div>
      </div>
    </div>
  </section>

  <p class="xp-line">
    <span class="mono curr" id="xpCurr">0</span>
    <span class="muted"> / </span>
    <span class="mono" id="xpMax">100</span>
    <span class="caption" data-i18n="xp">XP</span>
    <span class="to-next" id="xpToNext"></span>
  </p>

  <section class="stats">
    <div class="stat" id="streakStat">
      <div class="row">
        <span class="flame">
          <svg viewBox="0 0 24 24" fill="none"><path class="flame-core" d="M12 2c0 4-4 5-4 9a4 4 0 0 0 8 0c0-2-1-3-1-5 2 1 3 3 3 5a6 6 0 1 1-12 0c0-5 5-5 6-9z" fill="currentColor"/></svg>
        </span>
        <b><span id="streakNum">0</span></b>
      </div>
      <small data-i18n="streak">STREAK</small>
    </div>
    <div class="stat" id="creditStat">
      <div class="row">
        <div class="battery-frame"><span class="battery-fill" id="battFill" style="width: 0%"></span></div>
        <b><span id="creditN">0</span><span style="color: var(--text-faint); font-weight: 500; font-size: 14px;"> / <span id="creditMax">0</span></span></b>
      </div>
      <small data-i18n="credits">IMAGE CREDITS</small>
    </div>
  </section>

  <section class="tier-card" id="tierCard" data-t="free" data-action="topup">
    <div>
      <div class="name" id="tierName">FREE</div>
      <div class="renews" id="tierRenews" data-i18n="upgrade_to_unlock">Upgrade to unlock more</div>
    </div>
    <div class="arrow">→</div>
  </section>

  <section class="week">
    <header>
      <b data-i18n="this_week">THIS WEEK</b>
      <span class="rank" id="rankLabel"></span>
    </header>
    <div class="bars" id="weekBars"></div>
    <div class="labels" id="weekLabels"></div>
  </section>

  <section class="refs">
    <div class="row">
      <div>
        <small style="font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--text-faint); font-weight: 500;" data-i18n="invited">INVITED</small>
        <div><span class="count" id="refCount">0</span><span class="delta" id="refDelta"></span></div>
      </div>
    </div>
    <button class="copy-btn" id="copyRef" data-i18n="copy_invite">Copy invite link</button>
  </section>

  <nav class="quick">
    <button data-action="ask">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
      <span data-i18n="ask">Ask</span>
    </button>
    <button data-action="image">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>
      <span data-i18n="image">Image</span>
    </button>
    <button data-action="note">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <span data-i18n="note">Note</span>
    </button>
    <button data-action="search">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <span data-i18n="search">Search</span>
    </button>
  </nav>

  <section class="section" id="secMemory">
    <button class="head">
      <div class="left">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.5 2A2.5 2.5 0 0 0 7 4.5v15A2.5 2.5 0 0 0 9.5 22h5a2.5 2.5 0 0 0 2.5-2.5v-15A2.5 2.5 0 0 0 14.5 2zM9 6h6M9 10h6M9 14h4"/></svg>
        <span class="name" data-i18n="memory">Memory</span>
        <span class="count" id="memCount">0</span>
      </div>
      <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
    <div class="body">
      <ul class="memo-list" id="memoList"></ul>
      <form class="memo-form" id="memoForm">
        <input name="key" placeholder="key" maxlength="60" required>
        <input name="value" placeholder="value" maxlength="240" required>
        <button type="submit" data-i18n="save">Save</button>
      </form>
    </div>
  </section>

  <section class="section" id="secSettings">
    <button class="head">
      <div class="left">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span class="name" data-i18n="persona">Persona</span>
      </div>
      <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
    <div class="body">
      <ul class="persona-list" id="personaList"></ul>
      <div style="margin-top: 16px; font-size: 12px; color: var(--text-dim);">
        <span data-i18n="ai_provider">AI provider</span>: <b id="providerName" style="color: var(--text);">—</b>
        <span style="color: var(--text-faint); margin-left: 4px;" data-i18n="byok_note">(BYOK · use /key in chat)</span>
      </div>
    </div>
  </section>

  <footer class="footer">AI DISCO · v<span id="ver">3.4.0</span></footer>
</div>

<div class="scrim" id="scrim"></div>
<aside class="sheet" id="topupSheet" aria-hidden="true">
  <div class="grabber"></div>
  <h2 data-i18n="topup_title">Top up</h2>
  <p class="lead" data-i18n="topup_lead">Choose a plan and a payment method.</p>
  <div class="tier-pick" id="tierPick"></div>
  <div class="pay-routes">
    <button data-pay="stars">
      <span>⭐ <span data-i18n="pay_stars">Pay with Stars</span></span>
      <span class="sub" id="starsPriceSub">—</span>
    </button>
    <button data-pay="crypto">
      <span>🪙 <span data-i18n="pay_crypto">Pay with crypto</span></span>
      <span class="sub" id="cryptoPriceSub">—</span>
    </button>
  </div>
</aside>

<canvas id="confetti" hidden></canvas>
<div class="toast" id="toast"></div>

<script>
/* ===========================================================================
   THE MINI APP — vanilla JS, no framework. ~700 LoC.
   Killer feature: The Level Ring (XP progress arc + tier conic + streak ticks
   + level number + flip-to-help, all in one element).
=========================================================================== */
'use strict';

const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

/* ---- i18n -------------------------------------------------------------- */
const I18N = {
  en: {
    level: "LEVEL", streak: "STREAK", credits: "IMAGE CREDITS", xp: "XP",
    to_next: "to next level", tap_flip: "Tap to flip back",
    this_week: "THIS WEEK", invited: "INVITED", copy_invite: "Copy invite link",
    copied: "Link copied", ask: "Ask", image: "Image", note: "Note", search: "Search",
    memory: "Memory", persona: "Persona", save: "Save",
    upgrade_to_unlock: "Tap to upgrade →",
    renews_in: "Renews in {n}", expires_in: "Expires in {n}", forever: "Lifetime",
    main_ask: "ASK ANYTHING", main_streak: "🔥 KEEP YOUR {n}-DAY STREAK",
    main_upgrade: "UPGRADE — UNLOCK MORE", main_close_to_level: "+{n} XP TO LEVEL {l}",
    main_save: "Save",
    topup_title: "Top up", topup_lead: "Choose a plan and a payment method.",
    pay_stars: "Pay with Stars", pay_crypto: "Pay with crypto",
    days: "{n} days", days_one: "{n} day",
    err_full: "Memory full — delete an entry first.",
    err_network: "Network error",
    daily_claimed: "+{n} XP claimed",
    confetti_levelup: "LEVEL {n}!",
    ai_provider: "AI provider", byok_note: "(BYOK · use /key in chat)",
  },
  ru: {
    level: "УРОВЕНЬ", streak: "СЕРИЯ", credits: "КРЕДИТЫ НА КАРТИНКИ", xp: "XP",
    to_next: "до следующего уровня", tap_flip: "Нажмите чтобы вернуться",
    this_week: "ЭТА НЕДЕЛЯ", invited: "ПРИГЛАШЕНО", copy_invite: "Скопировать инвайт-ссылку",
    copied: "Ссылка скопирована", ask: "Спросить", image: "Картинка", note: "Заметка", search: "Поиск",
    memory: "Память", persona: "Персона", save: "Сохранить",
    upgrade_to_unlock: "Открыть полный доступ →",
    renews_in: "Продление через {n}", expires_in: "Закончится через {n}", forever: "Навсегда",
    main_ask: "СПРОСИТЬ AI", main_streak: "🔥 СОХРАНИ СЕРИЮ — {n} ДН.",
    main_upgrade: "ОТКРЫТЬ БОЛЬШЕ — UPGRADE", main_close_to_level: "+{n} XP ДО УР. {l}",
    main_save: "Сохранить",
    topup_title: "Пополнение", topup_lead: "Выберите тариф и способ оплаты.",
    pay_stars: "Оплатить Stars", pay_crypto: "Оплатить криптой",
    days: "{n} дн.", days_one: "{n} день",
    err_full: "Память переполнена — удалите запись.",
    err_network: "Ошибка сети",
    daily_claimed: "+{n} XP получено",
    confetti_levelup: "УРОВЕНЬ {n}!",
    ai_provider: "AI-провайдер", byok_note: "(BYOK · /key в чате)",
  },
  it: {
    level: "LIVELLO", streak: "SERIE", credits: "CREDITI IMMAGINE", xp: "XP",
    to_next: "al prossimo livello", tap_flip: "Tocca per tornare",
    this_week: "QUESTA SETTIMANA", invited: "INVITATI", copy_invite: "Copia link invito",
    copied: "Link copiato", ask: "Chiedi", image: "Immagine", note: "Nota", search: "Cerca",
    memory: "Memoria", persona: "Persona", save: "Salva",
    upgrade_to_unlock: "Tocca per fare upgrade →",
    renews_in: "Si rinnova tra {n}", expires_in: "Scade tra {n}", forever: "Per sempre",
    main_ask: "CHIEDI QUALSIASI COSA", main_streak: "🔥 MANTIENI LA SERIE DI {n} GIORNI",
    main_upgrade: "FAI UPGRADE — SBLOCCA TUTTO", main_close_to_level: "+{n} XP AL LIV. {l}",
    main_save: "Salva",
    topup_title: "Ricarica", topup_lead: "Scegli un piano e un metodo.",
    pay_stars: "Paga con Stars", pay_crypto: "Paga con crypto",
    days: "{n} giorni", days_one: "{n} giorno",
    err_full: "Memoria piena — elimina una voce.",
    err_network: "Errore di rete",
    daily_claimed: "+{n} XP ricevuti",
    confetti_levelup: "LIVELLO {n}!",
    ai_provider: "Provider AI", byok_note: "(BYOK · usa /key in chat)",
  },
};
let lang = 'en';
const t = (k, vars) => {
  let s = (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k;
  if (vars) Object.keys(vars).forEach(v => { s = s.replace(new RegExp('\\{' + v + '\\}', 'g'), vars[v]); });
  return s;
};
const formatDays = (n) => {
  if (n === 1) return t('days_one', { n });
  if (lang === 'ru') {
    const k = n % 10, k100 = n % 100;
    if (k === 1 && k100 !== 11) return `${n} день`;
    if (k >= 2 && k <= 4 && (k100 < 10 || k100 >= 20)) return `${n} дня`;
    return `${n} дней`;
  }
  return t('days', { n });
};
const applyI18N = () => {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
};

/* ---- API client -------------------------------------------------------- */
const api = async (path, body = {}) => {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ init_data: tg.initData, ...body }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ---- State ------------------------------------------------------------- */
let profile = null;

/* ---- Theme bridge ------------------------------------------------------ */
const applyTheme = () => {
  const isLight = tg.colorScheme === 'light';
  document.documentElement.dataset.theme = isLight ? 'light' : 'dark';
};
tg.onEvent('themeChanged', applyTheme);
applyTheme();

/* ---- Renderers --------------------------------------------------------- */
const ringCircumference = 2 * Math.PI * 88;  // 552.92
document.getElementById('ringProgress').setAttribute('stroke-dasharray', ringCircumference);

const streakTier = (days) => {
  if (days >= 100) return '4';
  if (days >= 30) return '3';
  if (days >= 7) return '2';
  return '1';
};

const renderHero = () => {
  const hero = document.getElementById('hero');
  hero.dataset.tier = profile.tier;
  hero.dataset.streakTier = streakTier(profile.streak_days);
  document.getElementById('lvNum').textContent = profile.level;
  document.getElementById('firstName').textContent = profile.first_name;
  // XP arc
  const pct = profile.xp_for_next > 0 ? profile.xp_current / profile.xp_for_next : 0;
  const offset = ringCircumference * (1 - pct);
  // start at 0 then animate to actual
  const ring = document.getElementById('ringProgress');
  ring.setAttribute('stroke-dashoffset', ringCircumference);
  requestAnimationFrame(() => {
    ring.setAttribute('stroke-dashoffset', offset);
  });
  // Streak ticks
  const ticks = document.getElementById('ringTicks');
  ticks.innerHTML = '';
  const total = Math.max(30, Math.min(60, profile.streak_days || 30));
  const lit = Math.min(profile.streak_days, total);
  for (let i = 0; i < total; i++) {
    const angle = (i / total) * 360 - 90;  // start at top
    const x = 100 + Math.cos(angle * Math.PI / 180) * 96;
    const y = 100 + Math.sin(angle * Math.PI / 180) * 96;
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', x);
    c.setAttribute('cy', y);
    c.setAttribute('r', i === lit - 1 ? 2.2 : 1.4);
    if (i < lit) c.classList.add('lit');
    ticks.appendChild(c);
  }
  // Back face
  document.getElementById('backNext').textContent = `+${profile.xp_for_next - profile.xp_current} XP`;
};

const renderXPLine = () => {
  // Animate count-up
  const target = profile.xp_current;
  const start = 0;
  const dur = 800;
  const t0 = Date.now();
  const el = document.getElementById('xpCurr');
  const tick = () => {
    const now = Date.now();
    const p = Math.min(1, (now - t0) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(start + (target - start) * eased).toLocaleString(lang);
    if (p < 1) requestAnimationFrame(tick);
  };
  tick();
  document.getElementById('xpMax').textContent = profile.xp_for_next.toLocaleString(lang);
  const toNext = profile.xp_for_next - profile.xp_current;
  document.getElementById('xpToNext').textContent = ` · +${toNext.toLocaleString(lang)}`;
};

const renderStats = () => {
  document.getElementById('streakNum').textContent = profile.streak_days;
  document.getElementById('creditN').textContent = profile.image_credits;
  document.getElementById('creditMax').textContent = profile.image_credits_max || '∞';
  // Battery
  const max = profile.image_credits_max || 100;
  const pct = Math.max(2, Math.min(100, (profile.image_credits / max) * 100));
  const fill = document.getElementById('battFill');
  fill.style.width = pct + '%';
  const stat = document.getElementById('creditStat');
  if (pct < 20) {
    stat.dataset.kind = 'credits-low';
    fill.style.background = 'var(--credit-low)';
  } else if (pct < 50) {
    fill.style.background = 'var(--credit-mid)';
  } else {
    fill.style.background = 'var(--credit-full)';
  }
};

const renderTier = () => {
  const card = document.getElementById('tierCard');
  card.dataset.t = profile.tier;
  document.getElementById('tierName').textContent = profile.tier_label.toUpperCase();
  const renews = document.getElementById('tierRenews');
  if (profile.tier === 'free') {
    renews.textContent = t('upgrade_to_unlock');
  } else if (profile.tier_renews_at) {
    const days = Math.max(0, Math.ceil((profile.tier_renews_at - profile.server_time) / 86400));
    renews.textContent = days > 0 ? t('expires_in', { n: formatDays(days) }) : t('forever');
  } else {
    renews.textContent = t('forever');
  }
};

const renderWeek = () => {
  const bars = document.getElementById('weekBars');
  const labels = document.getElementById('weekLabels');
  bars.innerHTML = '';
  labels.innerHTML = '';
  const max = Math.max(1, ...profile.weekly_xp_by_day);
  const today = new Date();
  const dayShorts = lang === 'ru'
    ? ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
    : lang === 'it'
      ? ['L','M','M','G','V','S','D']
      : ['M','T','W','T','F','S','S'];
  // weekly_xp_by_day is oldest→newest (last 7 days). Index 6 = today.
  profile.weekly_xp_by_day.forEach((xp, i) => {
    const bar = document.createElement('div');
    bar.className = 'bar' + (i === 6 ? ' today' : '');
    bar.style.height = '0px';
    bars.appendChild(bar);
    // Animate
    setTimeout(() => {
      bar.style.height = (Math.max(6, (xp / max) * 56)) + 'px';
    }, 100 + i * 50);
    // Label
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    const lab = document.createElement('span');
    lab.textContent = dayShorts[(d.getDay() + 6) % 7];
    labels.appendChild(lab);
  });
  // Rank
  const rl = document.getElementById('rankLabel');
  if (profile.leaderboard_rank) {
    let s = `#${profile.leaderboard_rank}`;
    rl.className = 'rank';
    if (profile.rank_delta_week > 0) { s += ` ↑${profile.rank_delta_week}`; rl.classList.add('up'); }
    else if (profile.rank_delta_week < 0) { s += ` ↓${Math.abs(profile.rank_delta_week)}`; rl.classList.add('down'); }
    rl.textContent = s;
  } else {
    rl.textContent = '';
  }
};

const renderRefs = () => {
  document.getElementById('refCount').textContent = profile.referrals;
};

const renderMemory = () => {
  document.getElementById('memCount').textContent = profile.memory_count;
  const list = document.getElementById('memoList');
  list.innerHTML = '';
  Object.entries(profile.memory).forEach(([k, v]) => {
    const li = document.createElement('li');
    li.className = 'memo-row';
    li.innerHTML = `<span class="k"></span><span class="v"></span><button class="del" aria-label="delete">×</button>`;
    li.querySelector('.k').textContent = k;
    li.querySelector('.v').textContent = v;
    li.querySelector('.del').addEventListener('click', async () => {
      tg.HapticFeedback?.impactOccurred?.('medium');
      try {
        const r = await api('/api/memory/delete', { key: k });
        profile.memory = r.memory;
        profile.memory_count = Object.keys(r.memory).length;
        renderMemory();
      } catch (e) { toast(t('err_network')); }
    });
    list.appendChild(li);
  });
};

const renderPersona = () => {
  const list = document.getElementById('personaList');
  list.innerHTML = '';
  (profile.personas || ['default']).forEach(name => {
    const li = document.createElement('li');
    li.className = 'persona-row' + (name === profile.persona ? ' active' : '');
    li.innerHTML = `<span class="nm"></span><span class="dot"></span>`;
    li.querySelector('.nm').textContent = name;
    li.addEventListener('click', async () => {
      tg.HapticFeedback?.selectionChanged?.();
      try {
        const r = await api('/api/settings', { persona: name });
        profile.persona = r.persona;
        renderPersona();
      } catch (e) { toast(t('err_network')); }
    });
    list.appendChild(li);
  });
  document.getElementById('providerName').textContent = profile.ai_provider;
};

const renderTopupSheet = () => {
  // Build tier pick — Plus + Pro
  const pick = document.getElementById('tierPick');
  pick.innerHTML = '';
  let selectedTier = 'plus';
  const TIER_DATA = [
    { id: 'plus', label: 'Plus', stars: 199, usd: 3.99,  credits: 20,  feat: '20 image credits · reminders · TTS' },
    { id: 'pro',  label: 'Pro',  stars: 399, usd: 7.99,  credits: 100, feat: '100 credits · vision · documents' },
  ];
  TIER_DATA.forEach((td, i) => {
    const el = document.createElement('div');
    el.className = 'tier-opt' + (i === 0 ? ' sel' : '');
    el.dataset.tier = td.id;
    el.innerHTML = `
      <span class="nm">${td.label}</span>
      <span class="price">⭐${td.stars} <small>· $${td.usd}</small></span>
      <span class="feat"></span>
    `;
    el.querySelector('.feat').textContent = td.feat;
    el.addEventListener('click', () => {
      pick.querySelectorAll('.tier-opt').forEach(x => x.classList.remove('sel'));
      el.classList.add('sel');
      selectedTier = td.id;
      updatePriceSubs(td);
      tg.HapticFeedback?.selectionChanged?.();
    });
    pick.appendChild(el);
  });
  const updatePriceSubs = (td) => {
    document.getElementById('starsPriceSub').textContent = `⭐ ${td.stars}`;
    document.getElementById('cryptoPriceSub').textContent = `$ ${td.usd}`;
  };
  updatePriceSubs(TIER_DATA[0]);

  document.querySelectorAll('.pay-routes button').forEach(btn => {
    btn.onclick = async () => {
      tg.HapticFeedback?.impactOccurred?.('medium');
      try {
        if (btn.dataset.pay === 'stars') {
          const r = await api('/api/topup/stars', { tier: selectedTier });
          tg.openInvoice(r.invoice_url, status => {
            if (status === 'paid') {
              tg.HapticFeedback?.notificationOccurred?.('success');
              closeSheet();
              setTimeout(refresh, 1500);
            }
          });
        } else {
          const r = await api('/api/topup/crypto', { tier: selectedTier });
          tg.openLink(r.invoice_url);
        }
      } catch (e) { toast(t('err_network')); }
    };
  });
};

/* ---- MainButton state machine ----------------------------------------- */
/* tg.MainButton.onClick STACKS handlers — we MUST offClick the exact same
   function reference before binding a new one. */
let _mbHandler = null;
const setMainButton = () => {
  const mb = tg.MainButton;
  if (_mbHandler) { try { mb.offClick(_mbHandler); } catch (e) {} }
  let handler, params;
  const toNext = profile.xp_for_next - profile.xp_current;
  if (profile.streak_at_risk) {
    params = { text: t('main_streak', { n: profile.streak_days }), color: '#FB923C', text_color: '#0E1116' };
    handler = () => quickAction('ask');
  } else if (toNext > 0 && toNext <= 50 && profile.xp_current > 0) {
    params = { text: t('main_close_to_level', { n: toNext, l: profile.level + 1 }), color: '#A78BFA', text_color: '#FFFFFF' };
    handler = () => quickAction('ask');
  } else if (profile.tier === 'free' && profile.image_credits === 0) {
    params = { text: t('main_upgrade'), color: '#A78BFA', text_color: '#FFFFFF' };
    handler = openSheet;
  } else {
    params = { text: t('main_ask'), color: '#A78BFA', text_color: '#FFFFFF' };
    handler = () => quickAction('ask');
  }
  mb.setParams(params);
  mb.onClick(handler);
  _mbHandler = handler;
  mb.show();
};

/* ---- Actions ----------------------------------------------------------- */
const quickAction = async (action) => {
  tg.HapticFeedback?.impactOccurred?.('light');
  try { await api('/api/quick-action', { action }); } catch (e) {}
  tg.close();
};

let _backHandler = null;
const openSheet = () => {
  document.getElementById('topupSheet').classList.add('open');
  document.getElementById('scrim').classList.add('open');
  document.getElementById('topupSheet').setAttribute('aria-hidden', 'false');
  if (_backHandler) { try { tg.BackButton.offClick(_backHandler); } catch (e) {} }
  _backHandler = closeSheet;
  tg.BackButton.onClick(_backHandler);
  tg.BackButton.show();
};
const closeSheet = () => {
  document.getElementById('topupSheet').classList.remove('open');
  document.getElementById('scrim').classList.remove('open');
  document.getElementById('topupSheet').setAttribute('aria-hidden', 'true');
  if (_backHandler) { try { tg.BackButton.offClick(_backHandler); } catch (e) {} _backHandler = null; }
  tg.BackButton.hide();
};

const toast = (msg) => {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2400);
};

/* ---- Confetti (level-up) ---------------------------------------------- */
const fireConfetti = () => {
  const cvs = document.getElementById('confetti');
  cvs.hidden = false;
  cvs.width = window.innerWidth;
  cvs.height = window.innerHeight;
  const ctx = cvs.getContext('2d');
  const colors = ['#A78BFA', '#FBBF24', '#F472B6', '#34D399', '#60A5FA'];
  const parts = [];
  for (let i = 0; i < 80; i++) {
    parts.push({
      x: cvs.width / 2, y: cvs.height / 2,
      vx: (Math.random() - 0.5) * 14, vy: (Math.random() - 1) * 14,
      g: 0.4, c: colors[i % colors.length], r: 4 + Math.random() * 4,
      rot: Math.random() * 360, vrot: (Math.random() - 0.5) * 20,
    });
  }
  const start = Date.now();
  const tick = () => {
    const dt = Date.now() - start;
    if (dt > 2400) { cvs.hidden = true; return; }
    ctx.clearRect(0, 0, cvs.width, cvs.height);
    parts.forEach(p => {
      p.vy += p.g;
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.vrot;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot * Math.PI / 180);
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);
      ctx.restore();
    });
    requestAnimationFrame(tick);
  };
  tick();
  tg.HapticFeedback?.notificationOccurred?.('success');
  toast(t('confetti_levelup', { n: profile.level }));
};

/* ---- Section toggling ------------------------------------------------- */
const wireSections = () => {
  document.querySelectorAll('.section').forEach(sec => {
    const head = sec.querySelector('.head');
    head.addEventListener('click', () => {
      const wasOpen = sec.classList.toggle('open');
      tg.HapticFeedback?.impactOccurred?.('light');
    });
  });
};

const wireRingFlip = () => {
  const rw = document.getElementById('ringWrap');
  rw.addEventListener('click', () => {
    rw.classList.toggle('flipped');
    tg.HapticFeedback?.impactOccurred?.('light');
  });
};

const wireLangSel = () => {
  const sel = document.getElementById('langSel');
  sel.value = lang;
  sel.addEventListener('change', async () => {
    lang = sel.value;
    applyI18N();
    tg.HapticFeedback?.selectionChanged?.();
    try {
      await api('/api/settings', { lang });
      profile.lang = lang;
      // Re-render derived strings
      renderTier();
      renderWeek();
      setMainButton();
    } catch (e) { toast(t('err_network')); }
  });
};

const wireMemoryForm = () => {
  document.getElementById('memoForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const key = fd.get('key').toString().trim();
    const value = fd.get('value').toString().trim();
    if (!key || !value) return;
    try {
      const r = await api('/api/memory', { key, value });
      profile.memory = r.memory;
      profile.memory_count = Object.keys(r.memory).length;
      renderMemory();
      e.target.reset();
      tg.HapticFeedback?.notificationOccurred?.('success');
    } catch (err) {
      if (err.message.includes('409')) toast(t('err_full'));
      else toast(t('err_network'));
    }
  });
};

const wireQuickActions = () => {
  document.querySelectorAll('.quick button').forEach(b => {
    b.addEventListener('click', () => quickAction(b.dataset.action));
  });
};

const wireTierCard = () => {
  document.getElementById('tierCard').addEventListener('click', openSheet);
};

const wireScrim = () => {
  document.getElementById('scrim').addEventListener('click', closeSheet);
};

const wireCopyRef = () => {
  const btn = document.getElementById('copyRef');
  btn.addEventListener('click', () => {
    const url = `https://t.me/${tg.initDataUnsafe.bot?.username || 'AI_DISCO_BOT'}?start=ref_${profile.referral_code}`;
    const copy = navigator.clipboard?.writeText(url);
    Promise.resolve(copy).then(() => {
      btn.textContent = t('copied');
      btn.classList.add('copied');
      tg.HapticFeedback?.notificationOccurred?.('success');
      setTimeout(() => {
        btn.textContent = t('copy_invite');
        btn.classList.remove('copied');
      }, 1800);
    });
  });
};

/* ---- Boot ------------------------------------------------------------- */
const renderAll = () => {
  renderHero();
  renderXPLine();
  renderStats();
  renderTier();
  renderWeek();
  renderRefs();
  renderMemory();
  renderPersona();
  renderTopupSheet();
};

const detectLang = () => {
  const saved = profile?.lang;
  if (saved && I18N[saved]) return saved;
  const tgLang = (tg.initDataUnsafe?.user?.language_code || '').slice(0, 2);
  if (I18N[tgLang]) return tgLang;
  return 'en';
};

const refresh = async () => {
  profile = await api('/api/me');
  lang = detectLang();
  applyI18N();
  document.getElementById('langSel').value = lang;
  document.getElementById('ver').textContent = profile.version;
  renderAll();
  setMainButton();
};

const boot = async () => {
  try {
    profile = await api('/api/me');
    lang = detectLang();
    applyI18N();
    document.getElementById('langSel').value = lang;
    document.getElementById('ver').textContent = profile.version;
    // Auto-claim daily
    if (!profile.claimed_today) {
      try {
        const r = await api('/api/claim-daily');
        if (r.bonus_xp > 0) {
          profile = r.profile;
          toast(t('daily_claimed', { n: r.bonus_xp }));
        }
      } catch (e) {}
    }
    document.getElementById('loading').remove();
    document.getElementById('app').hidden = false;
    renderAll();
    setMainButton();
    wireSections();
    wireRingFlip();
    wireLangSel();
    wireMemoryForm();
    wireQuickActions();
    wireTierCard();
    wireScrim();
    wireCopyRef();
    // Level-up detection
    if (profile.level > profile.last_seen_level && profile.last_seen_level > 0) {
      setTimeout(() => {
        fireConfetti();
        api('/api/seen-level', { level: profile.level }).catch(() => {});
      }, 800);
    } else if (profile.last_seen_level === 0) {
      api('/api/seen-level', { level: profile.level }).catch(() => {});
    }
  } catch (e) {
    document.getElementById('loading').innerHTML =
      '<div style="padding: 24px; text-align: center; color: var(--danger);">Auth failed. Open via the WebApp button.</div>';
  }
};
boot();
</script>
</body>
</html>"""
