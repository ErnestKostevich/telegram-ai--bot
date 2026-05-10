import aiohttp
from typing import Optional
from bot.storage import storage

PROVIDERS = [
    "gemini", "openai", "anthropic", "groq", "together", 
    "openrouter", "mistral", "cohere", "xai", "deepseek"
]

# Default models per provider (used when user hasn't set a model)
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

# Models available for selection per provider
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

# API endpoint configs
PROVIDER_CONFIGS = {
    "openai":     ("https://api.openai.com/v1/chat/completions", "bearer"),
    "groq":       ("https://api.groq.com/openai/v1/chat/completions", "bearer"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "bearer"),
    "deepseek":   ("https://api.deepseek.com/v1/chat/completions", "bearer"),
    "mistral":    ("https://api.mistral.ai/v1/chat/completions", "bearer"),
    "together":   ("https://api.together.xyz/v1/chat/completions", "bearer"),
    "xai":        ("https://api.x.ai/v1/chat/completions", "bearer"),
}

class AIHandler:
    def _get_model(self, user_id: int, provider: str) -> str:
        """Get the model: user-selected or provider default"""
        user = storage.get_user(user_id)
        user_model = user.get("ai_model")
        if user_model and user_model != "default":
            return user_model
        return DEFAULT_MODELS.get(provider, "default")

    async def generate_response(self, user_id: int, prompt: str, system_prompt: Optional[str] = None) -> str:
        user = storage.get_user(user_id)
        provider = user.get("ai_provider", "gemini")
        api_key = user.get("api_keys", {}).get(provider)
        
        if not api_key:
            return f"❌ Ключ API для {provider} не установлен.\nИспользуйте /setkey {provider} <КЛЮЧ> для установки ключа.\nДля выбора другого провайдера используйте /setprovider"
        
        model = self._get_model(user_id, provider)
        
        try:
            if provider == "gemini":
                return await self._call_gemini(api_key, model, prompt, system_prompt)
            elif provider == "anthropic":
                return await self._call_anthropic(api_key, model, prompt, system_prompt)
            elif provider == "cohere":
                return await self._call_cohere(api_key, model, prompt, system_prompt)
            elif provider in PROVIDER_CONFIGS:
                url, _ = PROVIDER_CONFIGS[provider]
                return await self._call_openai_compat(url, api_key, model, prompt, system_prompt)
            else:
                return f"❌ Provider '{provider}' not configured."
        except Exception as e:
            return f"❌ Ошибка API ({provider}): {str(e)}"

    async def _call_gemini(self, api_key, model, prompt, system_prompt):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_anthropic(self, api_key, model, prompt, system_prompt):
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]}
        if system_prompt:
            payload["system"] = system_prompt
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["content"][0]["text"]

    async def _call_cohere(self, api_key, model, prompt, system_prompt):
        url = "https://api.cohere.ai/v2/chat"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(str(data["error"]))
                if "message" in data and "content" in data["message"]:
                    return data["message"]["content"][0]["text"]
                return str(data)

    async def _call_openai_compat(self, url, api_key, model, prompt, system_prompt):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"model": model, "messages": messages}) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    raise Exception(err.get("message", str(err)) if isinstance(err, dict) else str(err))
                return data["choices"][0]["message"]["content"]

ai_handler = AIHandler()
