import aiohttp
import json
import logging

logger = logging.getLogger(__name__)

class AIProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, messages: list) -> str:
        raise NotImplementedError

class OpenAIProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model or "gpt-4o-mini",
            "messages": messages
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    error = await resp.text()
                    return f"Error OpenAI: {resp.status} - {error}"

class AnthropicProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        # Convert messages to Anthropic format
        system_prompt = ""
        formatted_messages = []
        for m in messages:
            if m['role'] == 'system':
                system_prompt = m['content']
            else:
                formatted_messages.append(m)
        
        payload = {
            "model": self.model or "claude-3-5-sonnet-20240620",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": formatted_messages
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['content'][0]['text']
                else:
                    return f"Error Anthropic: {resp.status}"

class GoogleProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model or 'gemini-1.5-flash'}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        # Simple conversion for Gemini
        contents = []
        for m in messages:
            role = "user" if m['role'] in ['user', 'system'] else "model"
            contents.append({"role": role, "parts": [{"text": m['content']}]})
            
        payload = {"contents": contents}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['candidates'][0]['content']['parts'][0]['text']
                else:
                    return f"Error Gemini: {resp.status}"

class OpenRouterProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model or "google/gemini-flash-1.5",
            "messages": messages
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    return f"Error OpenRouter: {resp.status}"

class GroqProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model or "llama3-8b-8192",
            "messages": messages
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    return f"Error Groq: {resp.status}"

class DeepSeekProvider(AIProvider):
    async def generate(self, messages: list) -> str:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model or "deepseek-chat",
            "messages": messages
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    return f"Error DeepSeek: {resp.status}"

def get_provider(provider_name: str, api_key: str, model: str = None) -> AIProvider:
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GoogleProvider,
        "openrouter": OpenRouterProvider,
        "groq": GroqProvider,
        "deepseek": DeepSeekProvider,
        "mistral": OpenAIProvider, # Mistral uses OpenAI compatible API
        "perplexity": OpenAIProvider, # Perplexity uses OpenAI compatible API
        "together": OpenAIProvider, # Together uses OpenAI compatible API
        "xai": OpenAIProvider # X.AI uses OpenAI compatible API
    }
    
    # Special base URLs for OpenAI-compatible providers
    base_urls = {
        "mistral": "https://api.mistral.ai/v1/chat/completions",
        "perplexity": "https://api.perplexity.ai/chat/completions",
        "together": "https://api.together.xyz/v1/chat/completions",
        "xai": "https://api.x.ai/v1/chat/completions"
    }
    
    provider_class = providers.get(provider_name.lower(), OpenAIProvider)
    
    # If it's a compatible provider, we might need to override the generate method or use a custom class
    # For simplicity in this version, we'll just return the class
    return provider_class(api_key, model)
