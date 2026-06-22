"""
Webhook-обработчик Telegram для Vercel (Python serverless function).

Каждое сообщение из темы "приход/уход" приходит сюда мгновенно (Telegram
сам присылает его, без постоянно работающего сервера). Если сообщение —
"Пришел/Ушел HH:MM", оно копится в буфере (лист "_state" в Google Sheets).
Когда админ пишет команду /итоги — все накопленные события сшиваются в
пары, считаются часы, и итог пишется в лист "Daily".
"""
import json
import logging
from http.server import BaseHTTPRequestHandler

import core
import sheets
import telegram_api
from config import ADMIN_IDS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("webhook")


def process_update(update: dict) -> None:
    message = update.get("message")
    if not message:
        return

    if not core.chat_allowed(message) or not core.in_target_topic(message):
        return

    sender_id = message.get("from", {}).get("id")

    # ---- команда /итоги от админа ----
    if core.is_command(message):
        if sender_id not in ADMIN_IDS:
            telegram_api.send_message(
                message["chat"]["id"],
                f"Команда доступна только администратору. Ваш ID: {sender_id}",
                message.get("message_thread_id"),
            )
            return

        events = sheets.read_buffer()
        today_events, old_events = core.split_by_today(events)

        if not today_events and not old_events:
            telegram_api.send_message(
                message["chat"]["id"], "Нет новых отметок для обработки.",
                message.get("message_thread_id"),
            )
            return

        sessions, leftover = core.pair_events(today_events)

        rows = [
            (s["in_dt"].strftime("%d.%m.%Y"), s["username"], s["full_name"],
             s["in_dt"].strftime("%H:%M"), s["out_dt"].strftime("%H:%M"), s["hours"])
            for s in sessions
        ]
        sheets.append_shift_rows(rows)
        sheets.write_buffer(leftover)  # old_events отбрасываются, не переносятся дальше

        reply = f"✅ Готово: записано смен — {len(sessions)}."
        if leftover:
            reply += f" Не закрыто (без пары): {len(leftover)} — останутся для следующего /итоги."
        if old_events:
            reply += f" Отброшено старых незакрытых отметок (за прошлые дни): {len(old_events)}."
        telegram_api.send_message(message["chat"]["id"], reply, message.get("message_thread_id"))
        return

    # ---- обычное сообщение "Пришел/Ушел HH:MM" ----
    event = core.message_to_event(message)
    if event is None:
        return  # не по формату — игнорируем

    sheets.append_to_buffer(event)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            update = json.loads(body) if body else {}

            process_update(update)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        except Exception:
            log.exception("Ошибка обработки вебхука")
            # Telegram должен получить 200 в любом случае, иначе начнёт ретраить
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": false}')

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Webhook is alive")
