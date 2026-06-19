"""
Разбор сообщений сотрудников фиксированного формата: "Пришел 10:05",
"Ушла 18:30" и т.п. Поддерживаются формы слова в разных родах/числах
(пришел/пришёл/пришла/пришли, ушел/ушёл/ушла/ушли) и время через ':' или '.'.

Никаких внешних вызовов — чистый regex, бесплатно и мгновенно.
Сообщения, не подходящие под формат, не обрабатываются (возвращается None).
"""
import re

IN_WORDS = ["пришел", "пришёл", "пришла", "пришли"]
OUT_WORDS = ["ушел", "ушёл", "ушла", "ушли"]

_WORDS_PATTERN = "|".join(IN_WORDS + OUT_WORDS)
_TIME_PATTERN = r"([01]?\d|2[0-3])[:.]([0-5]\d)"

# слово + (необязательные символы, не цифры) + время HH:MM
_FULL_RE = re.compile(rf"(?i)\b({_WORDS_PATTERN})\b\D{{0,10}}{_TIME_PATTERN}")


def parse_message(text: str) -> dict | None:
    """
    Возвращает {"type": "in"|"out", "time": "HH:MM"}, если сообщение
    соответствует формату "Пришел/Ушел HH:MM" (в любой словоформе).
    Если формат не подходит — возвращает None (сообщение игнорируется).
    """
    if not text:
        return None

    match = _FULL_RE.search(text)
    if not match:
        return None

    word = match.group(1).lower().replace("ё", "е")
    hh, mm = match.group(2), match.group(3)

    in_words_normalized = [w.replace("ё", "е") for w in IN_WORDS]
    event_type = "in" if word in in_words_normalized else "out"

    return {"type": event_type, "time": f"{int(hh):02d}:{mm}"}
