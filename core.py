"""
Общая логика разбора сообщений и сшивки пар "Пришел/Ушел" в смены.
Используется вебхуком (api/webhook.py) на каждое сообщение и при команде /итоги.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import parser
from config import TARGET_CHAT_ID, TARGET_TOPIC_ID, TIMEZONE

TZ = ZoneInfo(TIMEZONE)

COMMAND_ALIASES = ("/итоги", "/sync", "/итог")


def chat_allowed(message: dict) -> bool:
    if not TARGET_CHAT_ID:
        return True
    return str(message.get("chat", {}).get("id")) == str(TARGET_CHAT_ID)


def in_target_topic(message: dict) -> bool:
    if not TARGET_TOPIC_ID:
        return True
    return str(message.get("message_thread_id")) == str(TARGET_TOPIC_ID)


def normalize_command(text: str) -> str:
    """'/итоги@lighthouse_bot' -> '/итоги'"""
    return text.strip().split("@")[0].split()[0].lower() if text else ""


def is_command(message: dict) -> bool:
    text = message.get("text", "")
    return normalize_command(text) in COMMAND_ALIASES


def resolve_event_dt(message: dict, time_str: str) -> datetime:
    """Привязывает время из текста к календарной дате сообщения (локальная TZ)."""
    msg_utc = datetime.fromtimestamp(message["date"], tz=timezone.utc)
    msg_local = msg_utc.astimezone(TZ)

    hh, mm = time_str.split(":")
    candidate = msg_local.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)

    if candidate > msg_local + timedelta(hours=6):
        candidate -= timedelta(days=1)

    return candidate


def message_to_event(message: dict) -> dict | None:
    """Если сообщение похоже на 'Пришел/Ушел HH:MM' — возвращает событие, иначе None."""
    text = message.get("text", "")
    result = parser.parse_message(text)
    if result is None:
        return None

    sender = message.get("from", {})
    dt = resolve_event_dt(message, result["time"])

    return {
        "tg_id": sender.get("id"),
        "username": sender.get("username"),
        "full_name": " ".join(
            filter(None, [sender.get("first_name"), sender.get("last_name")])
        ) or str(sender.get("id")),
        "type": result["type"],
        "dt": dt.isoformat(),
        "text": text,
    }


def split_by_today(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Делит события на 'today_events' (дата совпадает с сегодняшней по локальной
    таймзоне) и 'old_events' (всё, что осталось с прошлых дней — например,
    кто-то забыл написать "Ушел" вчера). old_events не обрабатываются и не
    переносятся дальше — они отбрасываются при вызове /итоги.
    """
    today = datetime.now(TZ).date()
    today_events, old_events = [], []
    for e in events:
        dt = datetime.fromisoformat(e["dt"]) if isinstance(e["dt"], str) else e["dt"]
        if dt.date() == today:
            today_events.append(e)
        else:
            old_events.append(e)
    return today_events, old_events


def pair_events(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    events — список словарей с полем 'dt' (ISO-строка). Возвращает
    (closed_sessions, leftover_events) — leftover — то, что не нашло пары
    и должно остаться в буфере для следующего /итоги.
    """
    parsed = [{**e, "dt": datetime.fromisoformat(e["dt"])} for e in events]
    parsed.sort(key=lambda x: x["dt"])

    open_ins: dict = {}
    sessions = []
    lost_orphans = []  # старые 'in', потерянные из-за повторного 'in' без 'out'

    for e in parsed:
        tg_id = e["tg_id"]
        if e["type"] == "in":
            if tg_id in open_ins:
                lost_orphans.append(open_ins[tg_id])
            open_ins[tg_id] = e
        else:  # out
            if tg_id in open_ins:
                in_e = open_ins.pop(tg_id)
                sessions.append({
                    "tg_id": tg_id,
                    "username": e.get("username") or in_e.get("username"),
                    "full_name": e.get("full_name") or in_e.get("full_name"),
                    "in_dt": in_e["dt"],
                    "out_dt": e["dt"],
                    "hours": max(0.0, (e["dt"] - in_e["dt"]).total_seconds() / 3600),
                })
            else:
                lost_orphans.append(e)

    leftover = list(open_ins.values()) + lost_orphans
    leftover_serialized = [{**e, "dt": e["dt"].isoformat()} for e in leftover]

    return sessions, leftover_serialized
