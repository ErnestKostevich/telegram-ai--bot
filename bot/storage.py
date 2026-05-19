import base64
import json
import logging
from typing import Dict, Any
import aiohttp
from bot.config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_FILE_PATH

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self):
        self.data: Dict[str, Any] = {
            "users": {},
            "groups": {},
            "notes": {},
            "reminders": [],
            "stats": {}
        }
        self.sha = None
        self.headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"

    async def load(self):
        if not GITHUB_TOKEN or not GITHUB_REPO:
            logger.warning("GitHub credentials not set. Using in-memory storage.")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url, headers=self.headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.sha = data.get("sha")
                    content = base64.b64decode(data.get("content", "")).decode("utf-8")
                    try:
                        self.data = json.loads(content)
                        logger.info("Data loaded from GitHub.")
                    except json.JSONDecodeError:
                        logger.error("Failed to parse JSON from GitHub.")
                elif resp.status == 404:
                    logger.info("Data file not found on GitHub. Will create on first save.")
                else:
                    logger.error(f"Failed to load data from GitHub: {resp.status} {await resp.text()}")

    async def save(self):
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return

        content_str = json.dumps(self.data, indent=2)
        content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
        
        payload = {
            "message": "Update bot data",
            "content": content_b64
        }
        if self.sha:
            payload["sha"] = self.sha

        async with aiohttp.ClientSession() as session:
            async with session.put(self.api_url, headers=self.headers, json=payload) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    self.sha = data.get("content", {}).get("sha")
                    logger.info("Data saved to GitHub.")
                else:
                    logger.error(f"Failed to save data to GitHub: {resp.status} {await resp.text()}")

    def get_user(self, user_id: int) -> dict:
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "id": user_id,
                "ai_provider": "gemini",
                "api_keys": {},
                "vip": False,
                "memory": {},
                "notes": [],
                "chat_history": [],
                "stats": {"msgs": 0, "commands": 0}
            }
        else:
            self.data["users"][uid].setdefault("chat_history", [])
            self.data["users"][uid].setdefault("memory", {})
            self.data["users"][uid].setdefault("notes", [])
            self.data["users"][uid].setdefault("api_keys", {})
            self.data["users"][uid].setdefault("stats", {"msgs": 0, "commands": 0})
        return self.data["users"][uid]

    def get_group(self, chat_id: int) -> dict:
        cid = str(chat_id)
        if cid not in self.data["groups"]:
            self.data["groups"][cid] = {
                "id": chat_id,
                "vip": False,
                "welcome_enabled": False,
                "welcome_msg": "",
                "goodbye_enabled": False,
                "goodbye_msg": "",
                "rules": "",
                "warns": {},
                "ai_enabled": True,
                "antilink": False,
                "antispam": False,
                "stats": {"msgs": 0, "users": {}},
                "memory": {},
                "messages": [],
            }
        else:
            self.data["groups"][cid].setdefault("messages", [])
            self.data["groups"][cid].setdefault("warns", {})
            self.data["groups"][cid].setdefault("stats", {"msgs": 0, "users": {}})
        return self.data["groups"][cid]

storage = Storage()
