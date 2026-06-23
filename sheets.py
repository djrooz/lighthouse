"""
Работа с Google Sheets: поиск сотрудника по Telegram в листе "Персонал"
и запись закрытых смен в лист "Daily".

Лист "Персонал": Имя | Telegram | Позиция | Ставка
Лист "Daily":    Дата | Имя | Время прихода | Время ухода | Смена | Ставка | Аванс | Штраф | Касса | Итог

Дату, Имя, Время прихода/ухода, Смену и Ставку бот пишет сам (Ставку —
подтянув из "Персонал" по Telegram-аккаунту). Аванс/Штраф/Касса заполняет
админ вручную. Итог — формула, зависит от позиции сотрудника и
пересчитывается сама при любом изменении ячеек в строке:

  админ     : Итог = Ставка * Смена + 1% * Касса - Штраф - Аванс
  официант  : Итог = ЕСЛИ(Касса < 35000; Ставка * Смена + 5% * Касса; 6% * Касса) - Штраф - Аванс
  остальные : Итог = Ставка * Смена - Штраф - Аванс   (повар, бариста, шеф повар,
              су шеф, посудамойка, тех. персонал, уборщица — пока все по умолчанию)

Примечание: в формулах используется ";" как разделитель аргументов внутри
IF() и "," как десятичный разделитель — это нужно для русской локали
Google Sheets (иначе синтаксическая ошибка).
"""
import json
import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SHEET_ID,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEET_WORKSHEET,
    GOOGLE_PERSONNEL_WORKSHEET,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DAILY_HEADER = ["Дата", "Имя", "Время прихода", "Время ухода", "Смена",
                 "Ставка", "Аванс", "Штраф", "Касса", "Итог"]

# Колонки листа Daily:
# A Дата | B Имя | C Время прихода | D Время ухода | E Смена |
# F Ставка | G Аванс | H Штраф | I Касса | J Итог
SPECIAL_FORMULAS = {
    "админ":    "=F{r}*E{r}+0,01*I{r}-H{r}-G{r}",
    "официант": "=IF(I{r}<35000;F{r}*E{r}+0,05*I{r};0,06*I{r})-H{r}-G{r}",
}
DEFAULT_FORMULA = "=F{r}*E{r}-H{r}-G{r}"  # ставка × смена — для всех остальных позиций

_client = None
_spreadsheet = None
_daily_ws = None
_personnel_ws = None


def _get_spreadsheet():
    global _client, _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet

    if GOOGLE_SERVICE_ACCOUNT_JSON:
        # Деплой на Railway/Render: ключ передан целиком как переменная окружения
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # Обычный запуск: ключ лежит файлом рядом с ботом
        creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    _client = gspread.authorize(creds)
    _spreadsheet = _client.open_by_key(GOOGLE_SHEET_ID)
    return _spreadsheet


def _get_daily_ws():
    global _daily_ws
    if _daily_ws is not None:
        return _daily_ws
    sh = _get_spreadsheet()
    try:
        _daily_ws = sh.worksheet(GOOGLE_SHEET_WORKSHEET)
    except gspread.WorksheetNotFound:
        _daily_ws = sh.add_worksheet(title=GOOGLE_SHEET_WORKSHEET, rows=2000, cols=10)

    first_row = _daily_ws.row_values(1)
    if first_row[:10] != DAILY_HEADER:
        _daily_ws.update("A1:J1", [DAILY_HEADER])
    return _daily_ws


def _get_personnel_ws():
    global _personnel_ws
    if _personnel_ws is not None:
        return _personnel_ws
    sh = _get_spreadsheet()
    _personnel_ws = sh.worksheet(GOOGLE_PERSONNEL_WORKSHEET)
    return _personnel_ws


def _normalize_username(value: str) -> str:
    return (value or "").strip().lstrip("@").lower()


def lookup_employee(username: str | None, tg_id: int | None = None):
    """
    Ищет сотрудника в листе "Персонал" по Telegram-аккаунту. В колонке
    "Telegram" может быть указан либо ник (@nick или nick), либо числовой
    Telegram ID — бот сам определяет, что сравнивать.
    Возвращает (full_name, position, rate) или None, если не найден.
    """
    if not username and not tg_id:
        return None

    ws = _get_personnel_ws()
    rows = ws.get_all_values()[1:]  # пропускаем заголовок
    target_username = _normalize_username(username) if username else ""
    target_id = str(tg_id) if tg_id else ""

    for row in rows:
        if len(row) < 2:
            continue
        name = row[0] if len(row) > 0 else ""
        telegram = (row[1] if len(row) > 1 else "").strip()
        position = row[2] if len(row) > 2 else ""
        rate_str = row[3] if len(row) > 3 else ""

        if not telegram:
            continue

        matched = False
        if telegram.lstrip("-").isdigit():
            # в колонке числовой Telegram ID
            matched = target_id and telegram == target_id
        else:
            # в колонке ник
            matched = target_username and _normalize_username(telegram) == target_username

        if matched:
            try:
                rate = float(rate_str.replace(",", ".")) if rate_str.strip() else 0.0
            except ValueError:
                rate = 0.0
            return name or username or str(tg_id), position.strip(), rate

    return None


def append_shift_row(shift_date: str, telegram_username: str, fallback_name: str,
                      in_time: str, out_time: str, shift_hours: float,
                      tg_id: int | None = None) -> int:
    """
    Добавляет строку новой закрытой смены в лист Daily.
    Имя/Позиция/Ставка подтягиваются из листа "Персонал" по Telegram-аккаунту
    (нику или числовому ID — что указано в колонке "Telegram").
    Если сотрудник не найден там — пишет fallback_name и ставку 0 (админ
    донастроит лист "Персонал" и поправит строку вручную).
    """
    found = lookup_employee(telegram_username, tg_id)
    if found:
        full_name, position, rate = found
    else:
        full_name, position, rate = fallback_name, "", 0.0

    ws = _get_daily_ws()
    values = ws.get_all_values()
    row_num = len(values) + 1

    formula = SPECIAL_FORMULAS.get(position.lower(), DEFAULT_FORMULA).format(r=row_num)

    ws.append_row(
        [shift_date, full_name, in_time, out_time, round(shift_hours, 2),
         rate, 0, 0, 0, formula],
        value_input_option="USER_ENTERED",
    )
    return row_num


def append_shift_rows(rows: list[tuple]) -> None:
    """
    Пакетно добавляет несколько закрытых смен за раз: каждый элемент —
    (shift_date, telegram_username, fallback_name, in_time, out_time, shift_hours, tg_id).
    Гораздо быстрее, чем append_shift_row в цикле (один запрос к API вместо N).
    """
    if not rows:
        return

    ws = _get_daily_ws()
    values = ws.get_all_values()
    next_row = len(values) + 1

    batch = []
    for shift_date, telegram_username, fallback_name, in_time, out_time, shift_hours, tg_id in rows:
        found = lookup_employee(telegram_username, tg_id)
        if found:
            full_name, position, rate = found
        else:
            full_name, position, rate = fallback_name, "", 0.0

        formula = SPECIAL_FORMULAS.get(position.lower(), DEFAULT_FORMULA).format(r=next_row)
        batch.append([shift_date, full_name, in_time, out_time, round(shift_hours, 2),
                      rate, 0, 0, 0, formula])
        next_row += 1

    ws.append_rows(batch, value_input_option="USER_ENTERED")


# ---------------- буфер событий между сообщениями и командой /итоги ----------------

STATE_WORKSHEET = "_state"
BUFFER_HEADER = ["tg_id", "username", "full_name", "type", "dt", "text"]

_state_ws = None


def _get_state_ws():
    global _state_ws
    if _state_ws is not None:
        return _state_ws
    sh = _get_spreadsheet()
    try:
        _state_ws = sh.worksheet(STATE_WORKSHEET)
    except gspread.WorksheetNotFound:
        _state_ws = sh.add_worksheet(title=STATE_WORKSHEET, rows=500, cols=8)
        _state_ws.update("A1:F1", [BUFFER_HEADER])
    return _state_ws


def read_buffer() -> list[dict]:
    """Возвращает все накопленные с прошлого /итоги события "Пришел/Ушел"."""
    ws = _get_state_ws()
    values = ws.get_all_values()

    events = []
    for row in values[1:]:  # пропускаем заголовок
        if len(row) < 6 or not row[0]:
            continue
        events.append({
            "tg_id": int(row[0]),
            "username": row[1],
            "full_name": row[2],
            "type": row[3],
            "dt": row[4],  # ISO-строка, парсится вызывающим кодом при необходимости
            "text": row[5],
        })
    return events


def append_to_buffer(event: dict) -> None:
    """Добавляет одно событие в буфер (вызывается на каждое сообщение из вебхука)."""
    ws = _get_state_ws()
    ws.append_row(
        [str(event["tg_id"]), event.get("username") or "", event.get("full_name") or "",
         event["type"], event["dt"], event.get("text") or ""],
        value_input_option="RAW",
    )


def write_buffer(events: list[dict]) -> None:
    """Полностью перезаписывает буфер (после /итоги остаются только незакрытые события)."""
    ws = _get_state_ws()
    ws.clear()
    rows = [BUFFER_HEADER]
    for e in events:
        rows.append([str(e["tg_id"]), e.get("username") or "", e.get("full_name") or "",
                     e["type"], e["dt"], e.get("text") or ""])
    ws.update("A1", rows, value_input_option="RAW")
