from __future__ import annotations

import hashlib
from datetime import datetime, timezone


REMINDER_SPECS = (
    {
        "text": (
            "🐾 Ой, Тотошка еще ждет своего помощника!\n\n"
            "До конца осталось всего {remaining} вопросов.\n\n"
            "Продолжим? Скоро доберёмся до Minecraft! 🟩"
        ),
        "button": "Продолжить тест",
    },
    {
        "text": (
            "🐾 Тотошка ждёт своего помощника!\n\n"
            "Ваш ребенок уже прошёл большую часть приключения. Осталось {remaining} вопросов — "
            "и можно будет строить свой дом в Minecraft. 🏠"
        ),
        "button": "Продолжить",
    },
    {
        "text": (
            "🐾 Мы так и не закончили приключение!\n\n"
            "Осталось всего {remaining} вопросов. Результаты уже почти готовы, а в конце ребенка "
            "ждёт Minecraft, а вас — понимание того, что ребенок усвоил из школьной программы.\n\n"
            "Закончим тест? 💚"
        ),
        "button": "Закончить тест",
    },
)


def parse_utc(value):
    if not value:
        return None
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def due_reminder_index(session, now, delays):
    if session.get("stage") != "question":
        return None
    if session.get("completed") or not session.get("answers"):
        return None
    sent = int(session.get("reminders_sent", 0))
    if sent >= len(REMINDER_SPECS):
        return None
    last_activity = parse_utc(session.get("last_activity_at"))
    if last_activity is None:
        return None
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    elapsed = (now.astimezone(timezone.utc) - last_activity).total_seconds()
    return sent if elapsed >= delays[sent] else None


def render_reminder(index, remaining):
    spec = REMINDER_SPECS[index]
    return spec["text"].format(remaining=remaining), spec["button"]


def reminder_random_id(session_id, reminder_number):
    digest = hashlib.sha256(f"{session_id}:{reminder_number}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF or reminder_number
