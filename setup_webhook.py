"""
Одноразовый скрипт: говорит Telegram, куда присылать сообщения (на вебхук
Vercel). Запускается один раз после деплоя, и каждый раз, если меняется
адрес деплоя.

Использование:
    python setup_webhook.py https://твой-проект.vercel.app/api/webhook
"""
import sys
import requests

from config import TELEGRAM_BOT_TOKEN


def main():
    if len(sys.argv) != 2:
        print("Использование: python setup_webhook.py https://твой-проект.vercel.app/api/webhook")
        sys.exit(1)

    webhook_url = sys.argv[1]
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
        params={"url": webhook_url},
        timeout=15,
    )
    print(resp.json())


if __name__ == "__main__":
    main()
