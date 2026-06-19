"""
Конфигурация бота. Все секреты берутся из переменных окружения (.env).
"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ID чата, который бот должен обслуживать (можно оставить пустым — тогда бот
# реагирует в любом чате, куда его добавили). Узнать chat_id можно командой /chatid
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "")

# ID темы (topic/thread) внутри форум-группы, где сотрудники отмечают приход/уход.
# Узнать: написать /topicid прямо в этой теме. Если оставить пустым — бот
# обработает сообщения в любой теме этого чата (не рекомендуется).
TARGET_TOPIC_ID = os.getenv("TARGET_TOPIC_ID", "")

# Telegram user_id админов (через запятую) — только они могут вызывать /итоги
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
}

# Часовой пояс компании (по умолчанию Бишкек, GMT+6)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Bishkek")

# Google Sheets — куда пишутся закрытые смены
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
# Альтернатива файлу — весь JSON-ключ целиком в одной переменной (удобно для Railway/Render)
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SHEET_WORKSHEET = os.getenv("GOOGLE_SHEET_WORKSHEET", "Daily")
GOOGLE_PERSONNEL_WORKSHEET = os.getenv("GOOGLE_PERSONNEL_WORKSHEET", "Персонал")
