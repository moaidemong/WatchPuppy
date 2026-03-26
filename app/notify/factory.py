from __future__ import annotations

from app.core.config import NotifierSettings
from app.notify.base import Notifier
from app.notify.stdout_notifier import StdoutNotifier
from app.notify.telegram_notifier import TelegramNotifier


def build_notifier(settings: NotifierSettings) -> Notifier:
    if settings.backend == "telegram":
        return TelegramNotifier(
            bot_token_env=settings.telegram.bot_token_env,
            chat_id_env=settings.telegram.chat_id_env,
        )
    return StdoutNotifier()
