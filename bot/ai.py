import aiohttp
import base64
import datetime
import html
import json
from typing import Optional, List, Dict, Any, AsyncIterator, Tuple
from bot.storage import storage
from bot.config import (CHAT_HISTORY_LIMIT, SHARED_KEYS, FREE_TIER_DAILY_LIMIT,
                         FREE_TIER_FALLBACK_PROVIDER, has_shared_key_for, best_shared_key)

# Providers that support our streaming implementation
STREAMING_PROVIDERS = {
    "openai", "anthropic", "gemini", "groq", "together",
    "openrouter", "mistral", "xai", "deepseek",
}

PROVIDERS = [
    "gemini", "openai", "anthropic", "groq", "together",
    "openrouter", "mistral", "cohere", "xai", "deepseek"
]

DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "groq": "llama-3.3-70b-versatile",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "mistral": "mistral-large-latest",
    "xai": "grok-3-mini",
    "deepseek": "deepseek-chat",
    "cohere": "command-r-plus"
}

PROVIDER_MODELS = {
    "gemini": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.0-flash-lite"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o4-mini"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-haiku-20240307"],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"],
    "together": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "meta-llama/Llama-3.1-8B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
    "openrouter": ["meta-llama/llama-3.3-70b-instruct", "anthropic/claude-3.5-sonnet", "openai/gpt-4o-mini", "google/gemini-2.0-flash-exp:free"],
    "mistral": ["mistral-large-latest", "mistral-small-latest", "open-mistral-nemo"],
    "xai": ["grok-3-mini", "grok-3"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "cohere": ["command-r-plus", "command-r", "command-light"]
}

# Providers that support vision (image input)
VISION_PROVIDERS = {"openai", "anthropic", "gemini", "openrouter"}

PROVIDER_CONFIGS = {
    "openai":     ("https://api.openai.com/v1/chat/completions", "bearer"),
    "groq":       ("https://api.groq.com/openai/v1/chat/completions", "bearer"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "bearer"),
    "deepseek":   ("https://api.deepseek.com/v1/chat/completions", "bearer"),
    "mistral":    ("https://api.mistral.ai/v1/chat/completions", "bearer"),
    "together":   ("https://api.together.xyz/v1/chat/completions", "bearer"),
    "xai":        ("https://api.x.ai/v1/chat/completions", "bearer"),
}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)


def _no_key_msg(lang: str, provider: str) -> str:
    msgs = {
        "ru": (f"❌ Ключ для <b>{provider}</b> не установлен.\n"
               f"Используйте <code>/setkey {provider} КЛЮЧ</code> или нажмите ⚙️ Настройки → 🔑 API Ключ."),
        "en": (f"❌ API key for <b>{provider}</b> is not set.\n"
               f"Use <code>/setkey {provider} KEY</code> or tap ⚙️ Settings → 🔑 API Key."),
        "it": (f"❌ Chiave API per <b>{provider}</b> non impostata.\n"
               f"Usa <code>/setkey {provider} CHIAVE</code> o tocca ⚙️ Impostazioni → 🔑 Chiave API."),
    }
    return msgs.get(lang, msgs["en"])


def _free_tier_limit_msg(lang: str, limit: int) -> str:
    msgs = {
        "ru": (f"⏳ <b>Бесплатный лимит исчерпан</b> ({limit}/{limit} сегодня).\n\n"
               f"Чтобы продолжить без ожидания:\n"
               f"🔑 Установите свой ключ: ⚙️ Настройки → API Ключ\n"
               f"💎 Или получите VIP: /vip"),
        "en": (f"⏳ <b>Free tier limit reached</b> ({limit}/{limit} today).\n\n"
               f"To keep chatting without waiting:\n"
               f"🔑 Set your own key: ⚙️ Settings → API Key\n"
               f"💎 Or upgrade to VIP: /vip"),
        "it": (f"⏳ <b>Limite gratuito raggiunto</b> ({limit}/{limit} oggi).\n\n"
               f"Per continuare senza aspettare:\n"
               f"🔑 Imposta la tua chiave: ⚙️ Impostazioni → Chiave API\n"
               f"💎 O passa a VIP: /vip"),
    }
    return msgs.get(lang, msgs["en"])


def _today_utc() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _resolve_key(user_id: int) -> Tuple[str, str, str, bool]:
    """Decide which (provider, key, source) to use for a request.
    Returns (provider, api_key, source, is_free_tier).
      source: "user" — user's own key
              "shared" — creator-provided shared key (free tier)
              "" — no key available
      is_free_tier: True if we should debit the free-tier counter.
    """
    user = storage.get_user(user_id)
    preferred = user.get("ai_provider", "gemini")

    # 1) User's own key for their selected provider
    own = user.get("api_keys", {}).get(preferred)
    if own:
        return preferred, own, "user", False

    # 2) Shared key for their selected provider
    if has_shared_key_for(preferred) and FREE_TIER_DAILY_LIMIT > 0:
        return preferred, SHARED_KEYS[preferred], "shared", True

    # 3) Best available shared key on any provider (auto-switch)
    sp, sk = best_shared_key()
    if sk and FREE_TIER_DAILY_LIMIT > 0:
        return sp, sk, "shared", True

    return "", "", "", False


def _free_tier_remaining(user: dict) -> int:
    ft = user.setdefault("free_tier", {"date": "", "count": 0})
    today = _today_utc()
    if ft.get("date") != today:
        return FREE_TIER_DAILY_LIMIT  # fresh day
    used = int(ft.get("count", 0))
    return max(0, FREE_TIER_DAILY_LIMIT - used)


def _free_tier_consume(user: dict) -> int:
    """Increment usage. Returns remaining after this call (>=0)."""
    ft = user.setdefault("free_tier", {"date": "", "count": 0})
    today = _today_utc()
    if ft.get("date") != today:
        ft["date"] = today
        ft["count"] = 0
    ft["count"] = int(ft.get("count", 0)) + 1
    return max(0, FREE_TIER_DAILY_LIMIT - ft["count"])


def _err_msg(lang: str, provider: str, detail: str) -> str:
    # Provider error strings can contain <, >, & — escape so HTML parsers
    # downstream (we send these with parse_mode="HTML") don't blow up.
    safe = html.escape(str(detail))[:600]
    msgs = {
        "ru": f"❌ Ошибка API ({provider}): {safe}",
        "en": f"❌ API error ({provider}): {safe}",
        "it": f"❌ Errore API ({provider}): {safe}",
    }
    return msgs.get(lang, msgs["en"])


class AIHandler:
    def _get_model(self, user_id: int, provider: str) -> str:
        user = storage.get_user(user_id)
        user_model = user.get("ai_model")
        if user_model and user_model != "default":
            return user_model
        return DEFAULT_MODELS.get(provider, "default")

    def _get_history(self, user_id: int) -> List[Dict[str, str]]:
        user = storage.get_user(user_id)
        return user.get("chat_history", [])

    def _push_history(self, user_id: int, role: str, content: str):
        user = storage.get_user(user_id)
        hist = user.setdefault("chat_history", [])
        # Truncate each stored message at 1500 chars — keeps storage bounded
        # (~60KB max per user) while still useful as context.
        hist.append({"role": role, "content": (content or "")[:1500]})
        max_msgs = CHAT_HISTORY_LIMIT * 2
        if len(hist) > max_msgs:
            user["chat_history"] = hist[-max_msgs:]

    def clear_history(self, user_id: int):
        user = storage.get_user(user_id)
        user["chat_history"] = []

    async def generate_response(
        self,
        user_id: int,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_history: bool = True,
        image_b64: Optional[str] = None,
        image_mime: str = "image/jpeg",
    ) -> str:
        user = storage.get_user(user_id)
        lang = user.get("language", "ru")

        provider, api_key, source, is_free_tier = _resolve_key(user_id)
        if not api_key:
            return _no_key_msg(lang, user.get("ai_provider", "gemini"))

        # Enforce free-tier daily cap before making the request
        if is_free_tier and _free_tier_remaining(user) <= 0:
            return _free_tier_limit_msg(lang, FREE_TIER_DAILY_LIMIT)

        if image_b64 and provider not in VISION_PROVIDERS:
            return _err_msg(lang, provider, {
                "ru": "этот провайдер не поддерживает анализ изображений. Используйте openai, anthropic, gemini или openrouter.",
                "en": "this provider does not support image analysis. Use openai, anthropic, gemini, or openrouter.",
                "it": "questo provider non supporta l'analisi delle immagini. Usa openai, anthropic, gemini o openrouter.",
            }.get(lang, ""))

        model = self._get_model(user_id, provider)
        history = self._get_history(user_id) if use_history and not image_b64 else []

        try:
            if provider == "gemini":
                response = await self._call_gemini(api_key, model, prompt, system_prompt, history, image_b64, image_mime)
            elif provider == "anthropic":
                response = await self._call_anthropic(api_key, model, prompt, system_prompt, history, image_b64, image_mime)
            elif provider == "cohere":
                response = await self._call_cohere(api_key, model, prompt, system_prompt, history)
            elif provider in PROVIDER_CONFIGS:
                url, _ = PROVIDER_CONFIGS[provider]
                response = await self._call_openai_compat(url, api_key, model, prompt, system_prompt, history, image_b64, image_mime)
            else:
                return _err_msg(lang, provider, "not configured")

            if use_history and response and not response.startswith("❌"):
                self._push_history(user_id, "user", prompt)
                self._push_history(user_id, "assistant", response)
            # Debit free-tier counter only on successful (non-error) responses
            if is_free_tier and response and not response.startswith("❌"):
                _free_tier_consume(user)
            return response
        except aiohttp.ClientError as e:
            return _err_msg(lang, provider, f"network: {e}")
        except Exception as e:
            return _err_msg(lang, provider, str(e))

    async def _call_gemini(self, api_key, model, prompt, system_prompt, history, image_b64=None, image_mime="image/jpeg"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        contents = []
        for m in history:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        user_parts: List[Dict[str, Any]] = [{"text": prompt}]
        if image_b64:
            user_parts.append({"inline_data": {"mime_type": image_mime, "data": image_b64}})
        contents.append({"role": "user", "parts": user_parts})
        payload: Dict[str, Any] = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"].get("message", str(data["error"])))
                return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_anthropic(self, api_key, model, prompt, system_prompt, history, image_b64=None, image_mime="image/jpeg"):
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        messages = list(history)
        if image_b64:
            messages.append({"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": image_mime, "data": image_b64}},
                {"type": "text", "text": prompt},
            ]})
        else:
            messages.append({"role": "user", "content": prompt})
        payload: Dict[str, Any] = {"model": model, "max_tokens": 2048, "messages": messages}
        if system_prompt:
            payload["system"] = system_prompt
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"].get("message", str(data["error"])))
                return data["content"][0]["text"]

    async def _call_cohere(self, api_key, model, prompt, system_prompt, history):
        url = "https://api.cohere.ai/v2/chat"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages}
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(str(data["error"]))
                if "message" in data and "content" in data["message"]:
                    return data["message"]["content"][0]["text"]
                return str(data)

    # ============== STREAMING ==============

    async def stream_response(
        self,
        user_id: int,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_history: bool = True,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive from the provider. Caller is
        responsible for accumulating and persisting the final text to history."""
        user = storage.get_user(user_id)
        lang = user.get("language", "ru")

        provider, api_key, source, is_free_tier = _resolve_key(user_id)
        if not api_key:
            yield _no_key_msg(lang, user.get("ai_provider", "gemini"))
            return
        if is_free_tier and _free_tier_remaining(user) <= 0:
            yield _free_tier_limit_msg(lang, FREE_TIER_DAILY_LIMIT)
            return
        if provider not in STREAMING_PROVIDERS:
            # Fall back to a single-shot response (which also accounts for free-tier)
            text = await self.generate_response(user_id, prompt, system_prompt, use_history)
            yield text
            return

        model = self._get_model(user_id, provider)
        # If the active provider was switched to shared-key fallback, use that
        # provider's default model (user's chosen model probably belongs to a
        # different provider).
        if source == "shared" and provider != user.get("ai_provider"):
            model = DEFAULT_MODELS.get(provider, model)
        history = self._get_history(user_id) if use_history else []

        got_anything = False
        try:
            if provider == "gemini":
                async for chunk in self._stream_gemini(api_key, model, prompt, system_prompt, history):
                    got_anything = True
                    yield chunk
            elif provider == "anthropic":
                async for chunk in self._stream_anthropic(api_key, model, prompt, system_prompt, history):
                    got_anything = True
                    yield chunk
            elif provider in PROVIDER_CONFIGS:
                url, _ = PROVIDER_CONFIGS[provider]
                async for chunk in self._stream_openai_compat(url, api_key, model, prompt, system_prompt, history):
                    got_anything = True
                    yield chunk
        except Exception as e:
            yield _err_msg(lang, provider, str(e))
            return

        # Debit free-tier counter only if we actually got content from the provider
        if is_free_tier and got_anything:
            _free_tier_consume(user)

    def push_history(self, user_id: int, prompt: str, response: str):
        """Append a finished user+assistant turn to history (used after streaming)."""
        if not response or response.startswith("❌"):
            return
        self._push_history(user_id, "user", prompt)
        self._push_history(user_id, "assistant", response)

    async def _stream_openai_compat(self, url, api_key, model, prompt, system_prompt, history):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages, "max_tokens": 2048, "stream": True}
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    try:
                        err = json.loads(body)
                        msg = err.get("error", {}).get("message", body) if isinstance(err, dict) else body
                    except json.JSONDecodeError:
                        msg = body
                    raise Exception(str(msg)[:300])
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, IndexError, AttributeError):
                        continue

    async def _stream_anthropic(self, api_key, model, prompt, system_prompt, history):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        messages = list(history) + [{"role": "user", "content": prompt}]
        payload = {"model": model, "max_tokens": 2048, "messages": messages, "stream": True}
        if system_prompt:
            payload["system"] = system_prompt
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise Exception(body[:300])
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    try:
                        obj = json.loads(data)
                        if obj.get("type") == "content_block_delta":
                            delta = obj.get("delta", {}).get("text")
                            if delta:
                                yield delta
                        elif obj.get("type") == "message_stop":
                            break
                    except json.JSONDecodeError:
                        continue

    async def _stream_gemini(self, api_key, model, prompt, system_prompt, history):
        # Gemini stream endpoint uses ?alt=sse for line-based SSE
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:streamGenerateContent?alt=sse&key={api_key}")
        contents = []
        for m in history:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        payload: Dict[str, Any] = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise Exception(body[:300])
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    try:
                        obj = json.loads(data)
                        cand = obj.get("candidates", [{}])[0]
                        parts = cand.get("content", {}).get("parts", [])
                        for p in parts:
                            text = p.get("text")
                            if text:
                                yield text
                    except (json.JSONDecodeError, IndexError, AttributeError):
                        continue

    # ============== END STREAMING ==============

    async def _call_openai_compat(self, url, api_key, model, prompt, system_prompt, history, image_b64=None, image_mime="image/jpeg"):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
        if image_b64:
            messages.append({"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
            ]})
        else:
            messages.append({"role": "user", "content": prompt})
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, headers=headers, json={"model": model, "messages": messages, "max_tokens": 2048}) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    raise Exception(err.get("message", str(err)) if isinstance(err, dict) else str(err))
                return data["choices"][0]["message"]["content"]


ai_handler = AIHandler()
