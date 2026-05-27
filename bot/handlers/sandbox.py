"""Code execution sandbox via the free public Piston API (emkc.org).

Piston is sandboxed (no network, time/memory limits) and free with a
generous rate limit. We never trust user code and pass nothing
sensitive to it.

Usage:
  /run python
  ```
  print("hello")
  ```

  /run js
  ```
  console.log(2 + 2)
  ```

  Or single-line: /run python print(1+1)
"""
import html
import re
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t


PISTON_URL = "https://emkc.org/api/v2/piston/execute"

# Common languages and their default Piston versions (best-effort; Piston
# falls back to latest if version unknown).
LANGUAGES = {
    "python":     ("python",     "3.10.0"),
    "py":         ("python",     "3.10.0"),
    "js":         ("javascript", "18.15.0"),
    "javascript": ("javascript", "18.15.0"),
    "node":       ("javascript", "18.15.0"),
    "ts":         ("typescript", "5.0.3"),
    "typescript": ("typescript", "5.0.3"),
    "go":         ("go",         "1.16.2"),
    "rust":       ("rust",       "1.68.2"),
    "c":          ("c",          "10.2.0"),
    "cpp":        ("c++",        "10.2.0"),
    "c++":        ("c++",        "10.2.0"),
    "java":       ("java",       "15.0.2"),
    "ruby":       ("ruby",       "3.0.1"),
    "bash":       ("bash",       "5.2.0"),
    "sh":         ("bash",       "5.2.0"),
    "php":        ("php",        "8.2.3"),
    "lua":        ("lua",        "5.4.4"),
    "kt":         ("kotlin",     "1.8.20"),
    "kotlin":     ("kotlin",     "1.8.20"),
    "cs":         ("csharp.net", "5.0.201"),
    "csharp":     ("csharp.net", "5.0.201"),
    "swift":      ("swift",      "5.3.3"),
    "haskell":    ("haskell",    "9.0.1"),
}
MAX_CODE_BYTES = 6000
MAX_STDOUT_CHARS = 2500


def _parse_run_args(text: str) -> tuple[str | None, str | None]:
    """Parse the `/run` payload. Returns (language_key, code) or (None, None) on failure.

    Accepts:
      /run python print(1)
      /run python\n```\ncode\n```
      /run python\n<code>
      /run python ```code```
    """
    # Strip the leading /run command itself
    body = re.sub(r"^/run(?:@\w+)?\s*", "", text, count=1)
    if not body.strip():
        return None, None
    # First token = language
    m = re.match(r"^(\S+)\s*(.*)$", body, re.DOTALL)
    if not m:
        return None, None
    lang = m.group(1).lower()
    rest = m.group(2)

    # Strip markdown fences if present
    fence_match = re.search(r"```(?:\w+)?\n?(.*?)```", rest, re.DOTALL)
    if fence_match:
        code = fence_match.group(1)
    else:
        code = rest
    code = code.strip()
    if not code:
        return None, None
    return lang, code


async def _piston_run(language: str, version: str, code: str) -> dict:
    payload = {
        "language": language,
        "version": version,
        "files": [{"name": f"main", "content": code}],
        "stdin": "",
        "args": [],
        "compile_timeout": 10000,
        "run_timeout": 10000,
        "compile_memory_limit": -1,
        "run_memory_limit": -1,
    }
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(PISTON_URL, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Piston HTTP {resp.status}: {body[:200]}")
            return await resp.json()


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    raw_text = update.message.text or ""
    language_key, code = _parse_run_args(raw_text)

    if not language_key or not code:
        await update.message.reply_text(
            t(lang, "run_usage", langs=", ".join(sorted(set(LANGUAGES.keys())))),
            parse_mode="HTML",
        )
        return

    if language_key not in LANGUAGES:
        await update.message.reply_text(
            t(lang, "run_lang_unknown", langs=", ".join(sorted(set(LANGUAGES.keys()))[:20]) + "..."),
            parse_mode="HTML",
        )
        return

    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        await update.message.reply_text(t(lang, "run_code_too_big", max=MAX_CODE_BYTES))
        return

    piston_lang, piston_ver = LANGUAGES[language_key]
    placeholder = await update.message.reply_text(
        t(lang, "run_running", lang=piston_lang), parse_mode="HTML"
    )

    try:
        result = await _piston_run(piston_lang, piston_ver, code)
    except Exception as e:
        await placeholder.edit_text(t(lang, "run_error", err=html.escape(str(e))[:300]),
                                     parse_mode="HTML")
        return

    run_part = result.get("run") or {}
    compile_part = result.get("compile") or {}
    stdout = (run_part.get("stdout") or "").rstrip()
    stderr = (run_part.get("stderr") or "").rstrip()
    code_exit = run_part.get("code", 0)

    # Compile errors (for compiled langs)
    compile_err = (compile_part.get("stderr") or "").rstrip()

    sections = []
    if stdout:
        sections.append(f"<b>stdout:</b>\n<pre>{html.escape(stdout[:MAX_STDOUT_CHARS])}</pre>")
        if len(stdout) > MAX_STDOUT_CHARS:
            sections.append(t(lang, "run_truncated"))
    if compile_err:
        sections.append(f"<b>compile error:</b>\n<pre>{html.escape(compile_err[:1200])}</pre>")
    if stderr:
        sections.append(f"<b>stderr:</b>\n<pre>{html.escape(stderr[:1200])}</pre>")
    if not sections:
        sections.append(f"<i>{t(lang, 'run_no_output')}</i>")

    header = t(lang, "run_done", lang=piston_lang, exit=code_exit)
    final = header + "\n\n" + "\n\n".join(sections)
    try:
        await placeholder.edit_text(final[:4000], parse_mode="HTML")
    except Exception:
        try:
            await placeholder.edit_text(final[:4000])
        except Exception:
            pass
