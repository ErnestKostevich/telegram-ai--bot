import aiohttp
import json
import logging

logger = logging.getLogger(__name__)

class AIProvider:
    def __init__(self, api_key: str, model: str = None, base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def generate(self, messages: list) -> str:
        raise NotImplementedError

class OpenAICompatibleProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error_text = await resp.text()
                        return f"❌ Ошибка API ({resp.status}): {error_text[:200]}"
            except Exception as e:
                return f"❌ Ошибка соединения: {str(e)}"

class AnthropicProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "You are a helpful assistant.")
        user_messages = [m for m in messages if m['role'] != 'system']
        
        payload = {
            "model": self.model or "claude-3-5-sonnet-20240620",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": user_messages
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['content'][0]['text']
                else:
                    return f"❌ Ошибка Anthropic: {resp.status}"

class GoogleProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        model_name = self.model or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        contents = []
        for m in messages:
            role = "user" if m['role'] in ['user', 'system'] else "model"
            contents.append({"role": role, "parts": [{"text": m['content']}]})
            
        payload = {"contents": contents}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    try:
                        return data['candidates'][0]['content']['parts'][0]['text']
                    except:
                        return "❌ Ошибка парсинга ответа Gemini."
                else:
                    return f"❌ Ошибка Gemini: {resp.status}"

def get_provider(provider_id: str, api_key: str, model: str = None) -> AIProvider:
    config = {
        "openai": {"class": OpenAICompatibleProvider, "url": "https://api.openai.com/v1/chat/completions", "default_model": "gpt-4o-mini"},
        "anthropic": {"class": AnthropicProvider, "url": None, "default_model": "claude-3-5-sonnet-20240620"},
        "gemini": {"class": GoogleProvider, "url": None, "default_model": "gemini-1.5-flash"},
        "groq": {"class": OpenAICompatibleProvider, "url": "https://api.groq.com/openai/v1/chat/completions", "default_model": "llama3-8b-8192"},
        "openrouter": {"class": OpenAICompatibleProvider, "url": "https://openrouter.ai/api/v1/chat/completions", "default_model": "google/gemini-flash-1.5"},
        "deepseek": {"class": OpenAICompatibleProvider, "url": "https://api.deepseek.com/chat/completions", "default_model": "deepseek-chat"},
        "mistral": {"class": OpenAICompatibleProvider, "url": "https://api.mistral.ai/v1/chat/completions", "default_model": "mistral-tiny"},
        "perplexity": {"class": OpenAICompatibleProvider, "url": "https://api.perplexity.ai/chat/completions", "default_model": "llama-3-sonar-small-32k-online"},
        "together": {"class": OpenAICompatibleProvider, "url": "https://api.together.xyz/v1/chat/completions", "default_model": "mistralai/Mixtral-8x7B-Instruct-v0.1"},
        "xai": {"class": OpenAICompatibleProvider, "url": "https://api.x.ai/v1/chat/completions", "default_model": "grok-beta"}
    }
    
    prov_cfg = config.get(provider_id.lower())
    if not prov_cfg:
        return None
        
    return prov_cfg['class'](api_key, model or prov_cfg['default_model'], prov_cfg['url'])

PROVIDERS_LIST = [
    ("OpenAI", "openai"),
    ("Anthropic", "anthropic"),
    ("Google Gemini", "gemini"),
    ("Groq", "groq"),
    ("OpenRouter", "openrouter"),
    ("DeepSeek", "deepseek"),
    ("Mistral AI", "mistral"),
    ("Perplexity", "perplexity"),
    ("Together AI", "together"),
    ("X.AI (Grok)", "xai")
]
