import aiohttp
import base64
import html
from typing import Optional, List, Dict, Any
from bot.storage import storage
from bot.config import CHAT_HISTORY_LIMIT

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
        provider = user.get("ai_provider", "gemini")
        api_key = user.get("api_keys", {}).get(provider)

        if not api_key:
            return _no_key_msg(lang, provider)

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
