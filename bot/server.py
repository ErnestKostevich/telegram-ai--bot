"""Minimal HTTP server that runs alongside the polling bot.

Endpoints:
  GET  /                       — health check (returns "ok")
  GET  /healthz                — same
  POST /webhook/nowpayments    — NOWPayments IPN handler (HMAC-verified)
  GET  /webapp                 — Telegram Mini App dashboard (HTML)

We listen on 0.0.0.0:WEBHOOK_PORT (default 8080). On Fly.io with
http_service in fly.toml, this port is the one Fly load-balances.
"""
import hashlib
import hmac
import html
import json
import logging
import urllib.parse
from aiohttp import web
from bot.config import NOWPAYMENTS_IPN_SECRET, WEBHOOK_PORT, BOT_VERSION, TIERS

logger = logging.getLogger(__name__)


async def _root(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def _healthz(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "version": BOT_VERSION})


async def _nowpayments_webhook(request: web.Request) -> web.Response:
    """Verify HMAC signature then dispatch to handle_nowpayments_webhook()."""
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
        # Return 500 so NOWPayments retries (they back off and re-deliver up to
        # ~7 days). The handler is idempotent on `pending_crypto`, so retries
        # don't double-grant tier. Returning 200 here would silently drop a
        # payment if storage.save() blew up mid-grant.
        logger.exception(f"NOWPayments webhook handler error: {e}")
        return web.Response(status=500, text="handler error")
    return web.Response(text="ok")


# ===== Minimal Telegram Mini App =====
# Renders a server-side HTML profile dashboard. The page reads the user's
# Telegram init_data from window.Telegram.WebApp and fetches /api/profile
# for their personal data. Init-data signature verified server-side.

def _verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Verify Telegram WebApp initData per their algorithm. Returns parsed
    user dict if valid, else None."""
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, strict_parsing=False))
    except Exception:
        return None
    hash_received = parsed.pop("hash", None)
    if not hash_received:
        return None
    # Build data_check_string: alphabetically sorted key=value pairs joined by \n
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, hash_received):
        return None
    user_json = parsed.get("user")
    if not user_json:
        return None
    try:
        return json.loads(user_json)
    except Exception:
        return None


async def _webapp_dashboard(request: web.Request) -> web.Response:
    """Serve the Mini App HTML shell. JavaScript inside loads /api/profile."""
    html_doc = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>AI DISCO BOT — Dashboard</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 16px;
         background: var(--tg-theme-bg-color, #181818); color: var(--tg-theme-text-color, #fff); }
  h1 { font-size: 22px; margin: 0 0 16px; }
  .card { background: var(--tg-theme-secondary-bg-color, #2c2c2c); border-radius: 12px;
          padding: 16px; margin-bottom: 12px; }
  .row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #3a3a3a; }
  .row:last-child { border-bottom: none; }
  .k { opacity: .7; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px;
           background: var(--tg-theme-button-color, #5288c1); color: var(--tg-theme-button-text-color, #fff);
           font-size: 13px; font-weight: 600; }
  .err { color: #ff6b6b; padding: 12px; }
  .empty { opacity: .5; font-style: italic; }
  ul { margin: 6px 0 0; padding-left: 20px; }
</style>
</head>
<body>
  <div id="content">Loading...</div>

<script>
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

async function load() {
  const root = document.getElementById('content');
  try {
    const resp = await fetch('/api/profile', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({init_data: tg.initData})
    });
    if (!resp.ok) {
      root.innerHTML = '<div class="err">Auth failed (' + resp.status + '). Open via the WebApp button.</div>';
      return;
    }
    const d = await resp.json();
    const tier = d.tier || 'free';
    const exp = d.tier_expires ? new Date(d.tier_expires * 1000).toLocaleDateString() : '—';

    let memHtml = '<div class="empty">No memory entries yet.</div>';
    if (d.memory && Object.keys(d.memory).length) {
      memHtml = '<ul>' + Object.entries(d.memory).map(([k, v]) =>
        '<li><b>' + escape(k) + '</b>: ' + escape(v) + '</li>').join('') + '</ul>';
    }

    root.innerHTML = `
      <h1>👋 ${escape(d.first_name || 'You')}</h1>

      <div class="card">
        <div class="row"><span class="k">Tier</span><span class="badge">${escape(tier.toUpperCase())}</span></div>
        <div class="row"><span class="k">Expires</span><span>${exp}</span></div>
        <div class="row"><span class="k">Image credits</span><span>${d.image_credits || 0}</span></div>
        <div class="row"><span class="k">XP</span><span>${(d.stats && d.stats.commands || 0) * 10}</span></div>
        <div class="row"><span class="k">Provider</span><span>${escape(d.ai_provider || '—')}</span></div>
        <div class="row"><span class="k">Persona</span><span>${escape(d.persona || 'default')}</span></div>
        <div class="row"><span class="k">Referrals</span><span>${d.referrals || 0}</span></div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 8px">🧠 Memory (${Object.keys(d.memory || {}).length})</h3>
        ${memHtml}
      </div>

      <div class="card">
        <h3 style="margin:0 0 8px">📝 Notes (${(d.notes || []).length})</h3>
        ${(d.notes && d.notes.length) ? '<ul>' + d.notes.map(n => '<li>' + escape(n.text) + '</li>').join('') + '</ul>' : '<div class="empty">No notes yet.</div>'}
      </div>
    `;
  } catch (e) {
    root.innerHTML = '<div class="err">Error: ' + escape(e.message) + '</div>';
  }
}

function escape(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

load();
</script>
</body>
</html>"""
    return web.Response(text=html_doc, content_type="text/html")


async def _api_profile(request: web.Request) -> web.Response:
    """Return the authenticated user's profile data as JSON."""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "bad request"}, status=400)
    init_data = payload.get("init_data", "")
    bot_token = request.app["bot_token"]
    user_info = _verify_telegram_init_data(init_data, bot_token)
    if not user_info:
        return web.json_response({"error": "auth"}, status=401)

    from bot.storage import storage
    user = storage.get_user(int(user_info["id"]))
    return web.json_response({
        "first_name": user_info.get("first_name"),
        "tier": user.get("tier", "free"),
        "tier_expires": user.get("tier_expires"),
        "image_credits": user.get("image_credits", 0),
        "stats": user.get("stats", {}),
        "ai_provider": user.get("ai_provider"),
        "persona": user.get("persona", "default"),
        "referrals": user.get("referrals", 0),
        "memory": user.get("memory", {}),
        "notes": [{"text": n.get("text", "")[:200]} for n in (user.get("notes") or [])][:30],
    })


async def start_webhook_server(application):
    """Spin up the aiohttp server in parallel with the polling bot."""
    app = web.Application()
    app["bot"] = application.bot
    app["bot_token"] = application.bot.token
    app.router.add_get("/", _root)
    app.router.add_get("/healthz", _healthz)
    app.router.add_post("/webhook/nowpayments", _nowpayments_webhook)
    app.router.add_get("/webapp", _webapp_dashboard)
    app.router.add_post("/api/profile", _api_profile)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logger.info(f"HTTP server listening on 0.0.0.0:{WEBHOOK_PORT}")
    # Returning the runner so callers can later runner.cleanup() — we don't
    # actually shut down explicitly; PTB exits the whole process on stop.
    return runner
