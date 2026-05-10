import aiohttp
from typing import Optional
from bot.storage import storage

PROVIDERS = [
    "gemini", "openai", "anthropic", "groq", "together", 
    "openrouter", "mistral", "cohere", "xai", "deepseek"
]

class AIHandler:
    async def generate_response(self, user_id: int, prompt: str, system_prompt: Optional[str] = None) -> str:
        user = storage.get_user(user_id)
        provider = user.get("ai_provider", "gemini")
        api_key = user.get("api_keys", {}).get(provider)
        
        if not api_key:
            return f"❌ Ключ API для {provider} не установлен.\nИспользуйте /setkey {provider} <КЛЮЧ> для установки ключа.\nДля выбора другого провайдера используйте /setprovider"
        
        try:
            if provider == "gemini":
                return await self._call_gemini(api_key, prompt, system_prompt)
            elif provider == "openai":
                return await self._call_openai(api_key, prompt, system_prompt)
            elif provider == "anthropic":
                return await self._call_anthropic(api_key, prompt, system_prompt)
            elif provider == "groq":
                return await self._call_groq(api_key, prompt, system_prompt)
            elif provider == "openrouter":
                return await self._call_openrouter(api_key, prompt, system_prompt)
            elif provider == "deepseek":
                return await self._call_deepseek(api_key, prompt, system_prompt)
            else:
                return await self._call_generic_openai_compatible(provider, api_key, prompt, system_prompt)
        except Exception as e:
            return f"❌ Ошибка API ({provider}): {str(e)}"

    async def _call_gemini(self, api_key, prompt, system_prompt):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        async with aiohttp.ClientSession() as session:
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_openai(self, api_key, prompt, system_prompt):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"model": "gpt-4o-mini", "messages": messages}) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["choices"][0]["message"]["content"]
                
    async def _call_anthropic(self, api_key, prompt, system_prompt):
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": "claude-3-5-sonnet-20240620", "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
        if system_prompt:
            payload["system"] = system_prompt
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["content"][0]["text"]

    async def _call_groq(self, api_key, prompt, system_prompt):
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"model": "llama-3.1-70b-versatile", "messages": messages}) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["choices"][0]["message"]["content"]

    async def _call_openrouter(self, api_key, prompt, system_prompt):
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"model": "nousresearch/hermes-3-llama-3.1-405b", "messages": messages}) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["choices"][0]["message"]["content"]
                
    async def _call_deepseek(self, api_key, prompt, system_prompt):
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"model": "deepseek-chat", "messages": messages}) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                return data["choices"][0]["message"]["content"]

    async def _call_generic_openai_compatible(self, provider, api_key, prompt, system_prompt):
        configs = {
            "mistral": ("https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
            "together": ("https://api.together.xyz/v1/chat/completions", "meta-llama/Llama-3-70b-chat-hf"),
            "xai": ("https://api.x.ai/v1/chat/completions", "grok-beta"),
            "cohere": ("https://api.cohere.ai/v1/chat/completions", "command-r-plus")
        }
        if provider not in configs:
            raise Exception("Unsupported provider configuration for: " + provider)
            
        url, model = configs[provider]
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"model": model, "messages": messages}) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(data["error"]["message"])
                if provider == "cohere" and "text" in data:
                    return data["text"]
                return data["choices"][0]["message"]["content"]

ai_handler = AIHandler()
