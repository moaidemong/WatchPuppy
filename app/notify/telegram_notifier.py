from __future__ import annotations

import os
import requests
from app.notify.base import Notifier


class TelegramNotifier(Notifier):
    def __init__(self, bot_token_env: str, chat_id_env: str) -> None:
        self.bot_token = os.getenv(bot_token_env, "")
        self.chat_id = os.getenv(chat_id_env, "")

    def send(self, title: str, body: str) -> None:
        if not self.bot_token or not self.chat_id:
            raise RuntimeError("Telegram credentials are not configured")
        text = f"*{title}*\n{body}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        response.raise_for_status()
