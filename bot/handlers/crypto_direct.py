"""Direct on-chain crypto payments to the creator's own wallets.

No third-party processor. The user pays USDT to our wallet, submits the
transaction hash, and we verify it ON-CHAIN with keyless public endpoints:

  * USDT-TRC20 (TRON)     -> TronGrid public API
  * USDT-ERC20 (Ethereum) -> public JSON-RPC nodes

We guard against replay (a tx hash can be claimed once, globally), require
the payment to be recent, and require the amount to cover the tier price.
On success we grant the tier exactly like a Stars purchase does.
"""
import asyncio
import logging
import os
import re
import time

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.storage import storage
from bot.i18n import t
from bot.config import TIERS

logger = logging.getLogger(__name__)

# ---- Wallets (creator-owned) ----------------------------------------------
WALLETS = {
    "trc20": "TV1EBHTyvpP98jZGerz6sRmZvipn15LqDA",            # USDT on TRON
    "erc20": "0x9339686861079c781e0249ee64a509F893E2367c",   # USDT on Ethereum
}
NET_LABEL = {
    "trc20": "USDT · TRON (TRC-20) · ~$1 fee",
    "erc20": "USDT · Ethereum (ERC-20) · high gas",
}
NET_ORDER = ["trc20", "erc20"]

# ---- Token contracts (USDT, 6 decimals on both chains) --------------------
USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_ERC20 = "0xdac17f958d2ee523a2206206994597c13d831ec7"  # lowercase for compares
USDT_DECIMALS = 6
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

TRONGRID = "https://api.trongrid.io"
ETH_RPCS = [
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://rpc.ankr.com/eth",
    "https://cloudflare-eth.com",
]

AMOUNT_TOLERANCE = 0.05          # USDT — allow tiny rounding under-pay
MAX_AGE_SEC = 24 * 3600          # payment must be within the last 24h
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=25)

_TXHASH_RE = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")


# ===========================================================================
# Keyboards / UI
# ===========================================================================

def crypto_tier_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for tid in ("plus", "pro"):
        info = TIERS[tid]
        rows.append([InlineKeyboardButton(
            f"💎 {info['label']} — ${info['usd']:.2f} / {info['days']}d",
            callback_data=f"cd_t_{tid}")])
    return InlineKeyboardMarkup(rows)


def crypto_network_keyboard(tier: str, lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(NET_LABEL[n], callback_data=f"cd_n_{tier}_{n}")]
            for n in NET_ORDER]
    rows.append([InlineKeyboardButton(t(lang, "ik_back"), callback_data="cd_back")])
    return InlineKeyboardMarkup(rows)


async def buycrypto_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/buycrypto — direct on-chain USDT payment to our wallets."""
    user = storage.get_user(update.effective_user.id)
    lang = user.get("language", "en")
    await update.message.reply_text(
        t(lang, "cd_pick_tier"),
        parse_mode="HTML",
        reply_markup=crypto_tier_keyboard(lang),
    )


async def crypto_direct_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cd_* callbacks: tier pick -> network pick -> show address."""
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "en")
    data = query.data or ""

    if data == "cd_back":
        await query.edit_message_text(
            t(lang, "cd_pick_tier"), parse_mode="HTML",
            reply_markup=crypto_tier_keyboard(lang))
        return

    if data.startswith("cd_t_"):
        tier = data[len("cd_t_"):]
        if tier not in TIERS or tier == "free":
            return
        info = TIERS[tier]
        await query.edit_message_text(
            t(lang, "cd_pick_network", tier=info["label"], usd=f"{info['usd']:.2f}"),
            parse_mode="HTML",
            reply_markup=crypto_network_keyboard(tier, lang),
        )
        return

    if data.startswith("cd_n_"):
        rest = data[len("cd_n_"):]
        # rest = "<tier>_<net>"
        try:
            tier, net = rest.rsplit("_", 1)
        except ValueError:
            return
        if tier not in TIERS or tier == "free" or net not in WALLETS:
            return
        info = TIERS[tier]
        addr = WALLETS[net]

        # Arm the awaiting-hash state + remember a pending order (anchor time).
        user["state"] = f"awaiting_txhash:{tier}:{net}"
        storage.data.setdefault("pending_crypto_direct", {})[str(uid)] = {
            "tier": tier, "net": net, "ts": time.time(),
        }
        await storage.save()

        await query.edit_message_text(
            t(lang, "cd_pay_instructions",
              tier=info["label"], usd=f"{info['usd']:.2f}",
              network=NET_LABEL[net], address=addr),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "cd_copy_hint"), callback_data="cd_noop")],
                [InlineKeyboardButton(t(lang, "ik_back"), callback_data=f"cd_t_{tier}")],
            ]),
            disable_web_page_preview=True,
        )
        return

    if data == "cd_noop":
        return


# ===========================================================================
# Tx-hash submission -> on-chain verification -> grant
# ===========================================================================

async def handle_txhash_submission(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   state: str, txhash: str):
    """Called from the text-state dispatcher when state is awaiting_txhash:*."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "en")

    # state = "awaiting_txhash:<tier>:<net>"
    try:
        _, tier, net = state.split(":", 2)
    except ValueError:
        return
    if tier not in TIERS or net not in WALLETS:
        return
    info = TIERS[tier]

    txhash = txhash.strip()
    if not _TXHASH_RE.match(txhash):
        # Re-arm so they can just paste the hash again.
        user["state"] = state
        await storage.save()
        await update.message.reply_text(t(lang, "cd_bad_hash"), parse_mode="HTML")
        return

    norm = txhash.lower()
    if not norm.startswith("0x") and net == "erc20":
        norm = "0x" + norm
    key = f"{net}:{norm}"

    used = storage.data.setdefault("used_tx", {})
    if key in used:
        await update.message.reply_text(t(lang, "cd_already_used"), parse_mode="HTML")
        return

    await update.message.reply_text(t(lang, "cd_checking"), parse_mode="HTML")

    min_amount = info["usd"] - AMOUNT_TOLERANCE
    try:
        if net == "trc20":
            ok, amount, age, reason = await _verify_trc20(norm, WALLETS["trc20"], min_amount)
        else:
            ok, amount, age, reason = await _verify_erc20(norm, WALLETS["erc20"], min_amount)
    except Exception as e:
        logger.exception(f"crypto verify error: {e}")
        user["state"] = state  # let them retry
        await storage.save()
        await update.message.reply_text(t(lang, "cd_check_failed"), parse_mode="HTML")
        return

    if not ok:
        user["state"] = state  # allow retry (e.g. not yet confirmed)
        await storage.save()
        msg = {
            "not_found": "cd_not_found",
            "no_transfer": "cd_no_transfer",
            "too_old": "cd_too_old",
            "low_amount": "cd_low_amount",
        }.get(reason, "cd_not_found")
        await update.message.reply_text(
            t(lang, msg, got=f"{amount:.2f}", need=f"{info['usd']:.2f}"),
            parse_mode="HTML")
        return

    # Success — record the tx (replay guard) and grant the tier.
    used[key] = {"uid": uid, "tier": tier, "amount": amount, "ts": time.time()}
    # bound the used_tx store
    if len(used) > 5000:
        for k in sorted(used, key=lambda k: used[k].get("ts", 0))[:1000]:
            used.pop(k, None)

    from bot.handlers.payments import grant_tier, _award_partner_if_first_paid
    grant_tier(user, tier, days=info["days"])
    try:
        await _award_partner_if_first_paid(context, user)
    except Exception:
        pass
    storage.data.get("pending_crypto_direct", {}).pop(str(uid), None)
    await storage.save()

    await update.message.reply_text(
        t(lang, "cd_success",
          tier=info["label"], days=info["days"],
          credits=info["image_credits"], amount=f"{amount:.2f}"),
        parse_mode="HTML",
    )


# ===========================================================================
# Chain verifiers — return (ok: bool, amount: float, age_sec: int, reason: str)
# ===========================================================================

async def _verify_trc20(txhash: str, to_addr: str, min_amount: float):
    """Verify a USDT-TRC20 transfer to `to_addr` via TronGrid (keyless).

    We query the recipient's recent incoming USDT transfers and match the
    hash — this sidesteps TRON address-encoding pitfalls entirely.
    """
    norm = txhash[2:] if txhash.startswith("0x") else txhash
    min_ts = int((time.time() - MAX_AGE_SEC) * 1000)
    url = (f"{TRONGRID}/v1/accounts/{to_addr}/transactions/trc20"
           f"?only_to=true&limit=200&order_by=block_timestamp,desc"
           f"&min_timestamp={min_ts}&contract_address={USDT_TRC20}")
    headers = {"Accept": "application/json"}
    # Optional free TronGrid key (env TRONGRID_API_KEY) lifts the rate limit.
    _tg_key = os.getenv("TRONGRID_API_KEY", "")
    if _tg_key:
        headers["TRON-PRO-API-KEY"] = _tg_key
    data = None
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as s:
        for attempt in range(3):
            async with s.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    break
                # Keyless TronGrid is rate-limited — back off and retry on 429.
                if r.status == 429 and attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return (False, 0.0, 0, "not_found")
    if data is None:
        return (False, 0.0, 0, "not_found")
    for tx in data.get("data", []):
        if str(tx.get("transaction_id", "")).lower() != norm.lower():
            continue
        # Confirm it's USDT to our address (the query already filters, but verify)
        ti = tx.get("token_info", {})
        if ti.get("address") and ti["address"] != USDT_TRC20:
            return (False, 0.0, 0, "no_transfer")
        if tx.get("to") and tx["to"] != to_addr:
            return (False, 0.0, 0, "no_transfer")
        decimals = int(ti.get("decimals", USDT_DECIMALS))
        try:
            amount = int(tx.get("value", "0")) / (10 ** decimals)
        except (ValueError, TypeError):
            return (False, 0.0, 0, "no_transfer")
        age = int(time.time() - tx.get("block_timestamp", 0) / 1000)
        if age > MAX_AGE_SEC:
            return (False, amount, age, "too_old")
        if amount < min_amount:
            return (False, amount, age, "low_amount")
        return (True, amount, age, "ok")
    return (False, 0.0, 0, "not_found")


async def _eth_rpc(session, method: str, params: list):
    """Try each public RPC until one answers."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last = None
    for rpc in ETH_RPCS:
        try:
            async with session.post(rpc, json=payload) as r:
                if r.status != 200:
                    last = f"HTTP {r.status}"
                    continue
                j = await r.json()
                if "result" in j:
                    return j["result"]
                last = j.get("error")
        except Exception as e:
            last = str(e)
            continue
    logger.warning(f"all ETH RPCs failed: {last}")
    return None


async def _verify_erc20(txhash: str, to_addr: str, min_amount: float):
    """Verify a USDT-ERC20 transfer to `to_addr` via public JSON-RPC."""
    to_clean = to_addr.lower().replace("0x", "")
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as s:
        receipt = await _eth_rpc(s, "eth_getTransactionReceipt", [txhash])
        if not receipt:
            return (False, 0.0, 0, "not_found")
        if str(receipt.get("status", "")).lower() not in ("0x1", "1"):
            return (False, 0.0, 0, "no_transfer")

        amount = None
        for log in receipt.get("logs", []):
            if str(log.get("address", "")).lower() != USDT_ERC20:
                continue
            topics = [str(x).lower() for x in log.get("topics", [])]
            if len(topics) < 3 or topics[0] != TRANSFER_TOPIC:
                continue
            to_topic = topics[2][-40:]  # last 20 bytes = address
            if to_topic != to_clean:
                continue
            try:
                amount = int(log.get("data", "0x0"), 16) / (10 ** USDT_DECIMALS)
            except (ValueError, TypeError):
                continue
            break
        if amount is None:
            return (False, 0.0, 0, "no_transfer")

        # Recency via the block timestamp
        age = 0
        blk = receipt.get("blockNumber")
        if blk:
            block = await _eth_rpc(s, "eth_getBlockByNumber", [blk, False])
            if block and block.get("timestamp"):
                ts = int(block["timestamp"], 16)
                age = int(time.time() - ts)
        if age > MAX_AGE_SEC:
            return (False, amount, age, "too_old")
        if amount < min_amount:
            return (False, amount, age, "low_amount")
        return (True, amount, age, "ok")
