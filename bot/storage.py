import asyncio
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
            "stats": {},
        }
        self.sha = None
        self._save_lock = asyncio.Lock()
        # True only after a successful load() OR confirmed-404. False means we have no
        # safe baseline — saving would risk wiping real data on GitHub.
        self.loaded = False
        # When False, save() is a no-op (e.g. running locally without GitHub).
        self.persistent = bool(GITHUB_TOKEN and GITHUB_REPO)
        self.headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"

    async def load(self):
        if not self.persistent:
            logger.warning("GitHub credentials not set. Using in-memory storage.")
            self.loaded = True
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url, headers=self.headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.sha = data.get("sha")
                    content = base64.b64decode(data.get("content", "")).decode("utf-8")
                    try:
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, dict):
                            # Merge defaults so missing top-level keys are added
                            for key, default in (("users", {}), ("groups", {}), ("notes", {}),
                                                 ("reminders", []), ("stats", {})):
                                loaded_data.setdefault(key, default)
                            self.data = loaded_data
                            self.loaded = True
                            logger.info(f"Data loaded from GitHub: {len(self.data.get('users', {}))} users, "
                                        f"{len(self.data.get('groups', {}))} groups.")
                        else:
                            logger.error("Loaded data is not a dict; refusing to overwrite.")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from GitHub: {e} — refusing to overwrite.")
                elif resp.status == 404:
                    logger.info("Data file not found on GitHub. Will create on first save.")
                    # 404 is a SAFE baseline — file genuinely doesn't exist yet
                    self.loaded = True
                else:
                    logger.error(f"Failed to load data from GitHub: {resp.status} {await resp.text()}")
                    # self.loaded stays False → save() will refuse

    async def _put(self, session, payload):
        async with session.put(self.api_url, headers=self.headers, json=payload) as resp:
            return resp.status, await resp.json() if resp.content_type == "application/json" else await resp.text()

    async def save(self):
        if not self.persistent:
            return
        if not self.loaded:
            # CRITICAL safety: never overwrite GitHub data we never managed to read.
            # Otherwise a transient 5xx during startup would wipe production data.
            logger.error("Refusing to save: storage was never loaded successfully.")
            return

        async with self._save_lock:
            content_str = json.dumps(self.data, indent=2, ensure_ascii=False)
            content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                for attempt in (1, 2):
                    payload = {"message": "Update bot data", "content": content_b64}
                    if self.sha:
                        payload["sha"] = self.sha

                    try:
                        status, body = await self._put(session, payload)
                    except aiohttp.ClientError as e:
                        logger.error(f"Save network error (attempt {attempt}): {e}")
                        await asyncio.sleep(1)
                        continue

                    if status in (200, 201):
                        if isinstance(body, dict):
                            self.sha = body.get("content", {}).get("sha")
                        logger.info("Data saved to GitHub.")
                        return

                    # Conflict (stale sha) — refresh sha and retry once
                    if status == 409 and attempt == 1:
                        logger.warning("Save 409 (stale sha). Refreshing and retrying.")
                        try:
                            async with session.get(self.api_url, headers=self.headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    self.sha = data.get("sha")
                                    continue
                        except aiohttp.ClientError as e:
                            logger.error(f"SHA refresh failed: {e}")
                        return

                    logger.error(f"Failed to save data to GitHub (attempt {attempt}): {status} {body}")
                    if attempt == 1:
                        await asyncio.sleep(0.5)
                        continue
                    return

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
                "stats": {"msgs": 0, "commands": 0},
                "referrals": 0,
            }
        else:
            u = self.data["users"][uid]
            u.setdefault("chat_history", [])
            u.setdefault("memory", {})
            u.setdefault("notes", [])
            u.setdefault("api_keys", {})
            u.setdefault("stats", {"msgs": 0, "commands": 0})
            u.setdefault("referrals", 0)
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
            g = self.data["groups"][cid]
            g.setdefault("messages", [])
            g.setdefault("warns", {})
            g.setdefault("stats", {"msgs": 0, "users": {}})
        return self.data["groups"][cid]


storage = Storage()
