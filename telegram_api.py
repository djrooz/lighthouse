"""
Минимальный клиент Telegram Bot API — только отправка сообщений.
Используется вебхуком (api/webhook.py), чтобы отвечать на команду /итоги.
"""
import requests

from config import TELEGRAM_BOT_TOKEN

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(chat_id, text: str, message_thread_id: int | None = None) -> None:
    """Отправляет сообщение (например, итоговый отчёт после обработки /итоги)."""
    payload = {"chat_id": chat_id, "text": text}
    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id
    resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
    resp.raise_for_status()
