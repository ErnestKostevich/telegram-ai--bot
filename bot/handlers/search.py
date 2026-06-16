"""Web search via DuckDuckGo Instant Answer API — free, no API key.

DDG's "Instant Answer" gives a structured response for many queries:
- Abstract (Wikipedia summary for entities)
- RelatedTopics (suggestions)
- Definition (dictionary)
- Answer (direct calculation/conversion)

For queries with no instant answer, we fall back to a DDG HTML link
suggestion and ask the user's own AI to answer with whatever context
the response provided (BYOK — never our key).
"""
import html
import urllib.parse
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler
from bot.i18n import t


DDG_API = "https://api.duckduckgo.com/"


async def _ddg_instant(query: str) -> dict:
    """Query DuckDuckGo's Instant Answer API. Returns the JSON dict."""
    params = {
        "q": query,
        "format": "json",
        "no_redirect": "1",
        "no_html": "1",
        "skip_disambig": "1",
    }
    url = f"{DDG_API}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "ai-disco-bot/3.0 (https://t.me/AI_DISCO_BOT)"}
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as s:
        async with s.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"DDG HTTP {resp.status}")
            # DDG sometimes returns HTML-style content-type — read as text first
            text = await resp.text()
            import json as _json
            return _json.loads(text)


def _format_ddg(result: dict, query: str, lang: str) -> tuple[str, bool]:
    """Render the DDG result as HTML.
    Returns (html_text, had_useful_info)."""
    parts = []
    had_info = False

    abstract = (result.get("AbstractText") or "").strip()
    abstract_url = result.get("AbstractURL") or ""
    abstract_src = result.get("AbstractSource") or ""

    answer = (result.get("Answer") or "").strip()
    answer_type = result.get("AnswerType") or ""

    definition = (result.get("Definition") or "").strip()
    definition_url = result.get("DefinitionURL") or ""
    definition_src = result.get("DefinitionSource") or ""

    related = result.get("RelatedTopics") or []

    # 1) Direct answer (calculations, conversions)
    if answer:
        parts.append(f"💡 <b>{html.escape(answer)}</b>")
        if answer_type:
            parts.append(f"<i>({html.escape(answer_type)})</i>")
        had_info = True

    # 2) Abstract (entity summary, usually Wikipedia)
    if abstract:
        parts.append(html.escape(abstract))
        if abstract_url and abstract_src:
            parts.append(f'<i>— <a href="{html.escape(abstract_url)}">{html.escape(abstract_src)}</a></i>')
        had_info = True

    # 3) Definition (dictionary)
    if definition and not abstract:
        parts.append(f"📖 {html.escape(definition)}")
        if definition_url and definition_src:
            parts.append(f'<i>— <a href="{html.escape(definition_url)}">{html.escape(definition_src)}</a></i>')
        had_info = True

    # 4) Related topics (up to 4)
    if related and not (abstract or answer):
        rel_lines = []
        for topic in related[:4]:
            if not isinstance(topic, dict):
                continue
            txt = (topic.get("Text") or "").strip()
            url_v = topic.get("FirstURL") or ""
            if txt:
                if url_v:
                    rel_lines.append(f'• <a href="{html.escape(url_v)}">{html.escape(txt[:200])}</a>')
                else:
                    rel_lines.append(f"• {html.escape(txt[:200])}")
        if rel_lines:
            parts.append("\n".join(rel_lines))
            had_info = True

    if not had_info:
        # No useful info from DDG
        return "", False

    header = t(lang, "search_header", q=html.escape(query[:80]))
    return header + "\n\n" + "\n\n".join(parts), True


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/search [query] — DuckDuckGo lookup with AI-augmented summary."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "en")
    if not context.args:
        await update.message.reply_text(t(lang, "search_usage"), parse_mode="HTML")
        return
    query = " ".join(context.args).strip()
    if len(query) > 200:
        query = query[:200]

    msg = await update.message.reply_text(t(lang, "search_loading", q=html.escape(query)),
                                            parse_mode="HTML")

    try:
        ddg = await _ddg_instant(query)
    except Exception as e:
        await msg.edit_text(t(lang, "search_error", err=html.escape(str(e))[:200]),
                            parse_mode="HTML")
        return

    formatted, had_info = _format_ddg(ddg, query, lang)
    if had_info:
        # Append a DDG link footer
        safe_q = urllib.parse.quote(query)
        formatted += (f'\n\n<i>🔎 <a href="https://duckduckgo.com/?q={safe_q}">'
                       f'{t(lang, "search_full_results")}</a></i>')
        try:
            await msg.edit_text(formatted[:4000], parse_mode="HTML",
                                 disable_web_page_preview=True)
        except Exception:
            try:
                await msg.edit_text(formatted[:4000], disable_web_page_preview=True)
            except Exception:
                pass
        return

    # No instant answer — ask the user's own AI to attempt a brief answer
    # if they have a key set. We tell the AI explicitly its knowledge may be
    # outdated.
    if not user.get("api_keys"):
        safe_q = urllib.parse.quote(query)
        link = f"https://duckduckgo.com/?q={safe_q}"
        await msg.edit_text(
            t(lang, "search_no_instant", q=html.escape(query), link=link),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    try:
        ai_response = await ai_handler.generate_response(
            uid,
            f"Web search query: {query!r}\nDuckDuckGo had no instant answer. "
            f"Briefly answer the query from your training knowledge (cap: 4-6 sentences). "
            f"If you're unsure or it likely needs current info, say so plainly.",
            system_prompt="You are a concise search assistant. No fluff, no markdown headings.",
            use_history=False,
        )
        if ai_response.startswith("❌"):
            raise RuntimeError(ai_response)
        safe_q = urllib.parse.quote(query)
        result_text = (
            f"{t(lang, 'search_header', q=html.escape(query[:80]))}\n\n"
            f"{html.escape(ai_response)}\n\n"
            f'<i>🔎 <a href="https://duckduckgo.com/?q={safe_q}">{t(lang, "search_full_results")}</a></i>'
        )
        await msg.edit_text(result_text[:4000], parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        safe_q = urllib.parse.quote(query)
        link = f"https://duckduckgo.com/?q={safe_q}"
        await msg.edit_text(
            t(lang, "search_no_instant", q=html.escape(query), link=link),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
