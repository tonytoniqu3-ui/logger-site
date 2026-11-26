"""Alertes Telegram. Si Telegram n'est pas configuré ou ne répond pas, le bot continue sans rien dire."""
from __future__ import annotations

import logging
import os

log = logging.getLogger("botcrypto")
API = "https://api.telegram.org"


class Telegram:
    def __init__(self, token: str | None = None, chat_id: str | None = None, session=None):
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        self.session = session

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def _http(self):
        if self.session is None:
            import requests
            self.session = requests.Session()
        return self.session

    def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            r = self._http().post(f"{API}/bot{self.token}/sendMessage",
                                  data={"chat_id": self.chat_id, "text": text[:4000]}, timeout=15)
            return r.status_code == 200
        except Exception as e:  # une alerte ratée ne doit jamais arrêter le bot
            log.warning("Telegram indisponible : %s", e)
            return False

    def find_chat_ids(self) -> list[tuple[str, str]]:
        """Liste les conversations qui ont écrit au bot Telegram (pour trouver TELEGRAM_CHAT_ID)."""
        r = self._http().get(f"{API}/bot{self.token}/getUpdates", timeout=15)
        r.raise_for_status()
        seen = {}
        for u in r.json().get("result", []):
            chat = (u.get("message") or u.get("channel_post") or {}).get("chat") or {}
            if "id" in chat:
                seen[str(chat["id"])] = chat.get("first_name") or chat.get("title") or ""
        return list(seen.items())
