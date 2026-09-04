from __future__ import annotations

import os
import csv
import random
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote

import vk_api
import requests
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from PIL import Image

from diagnostics import build_summary as diagnostic_build_summary
from question_sets import QUESTION_ASSET_SUBDIRS, QUESTION_SETS, questions_for_route
from reminders import due_reminder_index, reminder_random_id, render_reminder
from session_store import SessionStore
from shop import SHOP_CATEGORIES, SHOP_ITEMS, CATEGORY_TITLES, affordable_items, compose_shop_scene
from ai_report import generate_parent_report

BASE_DIR = Path(__file__).resolve().parent
QUESTION_ASSETS = BASE_DIR / "assets" / "questions"
SHOP_ASSETS = BASE_DIR / "assets" / "shop"
GENERATED_DIR = BASE_DIR / "generated"
TOTOSHKA_INTRO = BASE_DIR / "assets" / "TOTO.png"
SESSION_DB_PATH = Path(os.getenv("SESSION_DB_PATH", "").strip() or "data/sessions.sqlite3")
if not SESSION_DB_PATH.is_absolute():
    SESSION_DB_PATH = BASE_DIR / SESSION_DB_PATH


def reminder_delays_from_env():
    raw = os.getenv("REMINDER_DELAYS_SECONDS", "").strip()
    if not raw:
        return 20 * 60, 3 * 60 * 60, 24 * 60 * 60
    values = tuple(int(value.strip()) for value in raw.split(",") if value.strip())
    if len(values) != 3 or any(value < 0 for value in values):
        raise RuntimeError("REMINDER_DELAYS_SECONDS must contain exactly three non-negative integers")
    return values


REMINDER_DELAYS = reminder_delays_from_env()
REMINDER_POLL_SECONDS = max(1, int(os.getenv("REMINDER_POLL_SECONDS", "30")))
POST_TEST_REMINDER_DELAYS = (20 * 60, 3 * 60 * 60, 24 * 60 * 60)

POLICY_URL = "https://disk.yandex.ru/i/CmjPe-bGH87wsA"
PD_CONSENT_URL = "https://disk.yandex.ru/i/TORpX__fuJmnxQ"
MARKETING_CONSENT_URL = "https://disk.yandex.ru/i/_9vaNdyTI0nFRA"
SUBSCRIBERS_CSV_PATH = Path(os.getenv("SUBSCRIBERS_CSV_PATH", "").strip() or "data/subscribers.csv")
if not SUBSCRIBERS_CSV_PATH.is_absolute():
    SUBSCRIBERS_CSV_PATH = BASE_DIR / SUBSCRIBERS_CSV_PATH

SUBSCRIBER_FIELDS = [
    "vk_id", "pd_consent", "pd_consent_at", "marketing_consent",
    "marketing_consent_at", "marketing_revoked_at", "class", "emeralds",
    "completed_at", "policy_url", "pd_consent_url", "marketing_consent_url",
]
START_COMMANDS = {"начать", "начать тест", "тест", "старт", "/start"}
RESTART_COMMANDS = {"заново", "пройти тест заново", "🔄 пройти тест заново"}
ELLIE_SCREEN_NAME = "ellie_englie"

TEST_MENU_LABEL = "📝 ПРОЙТИ ТЕСТ"
TEST_START_LABEL = "ПРОЙТИ ТЕСТ"
GIFTS_LABEL = "🎁 ПОДАРКИ"
REVIEWS_LABEL = "⭐ ОТЗЫВЫ"
TRIAL_LABEL = "💚 ЗАПИСАТЬСЯ НА ПРОБНЫЙ УРОК"
FINAL_TRIAL_LABEL = "💚 ЗАПИСАТЬСЯ НА ПРОБНЫЙ УРОК К ЭЛЛИ"
RESTART_LABEL = "🔄 ПРОЙТИ ТЕСТ ЗАНОВО"
MAIN_MENU_LABEL = "🏠 ГЛАВНОЕ МЕНЮ"
CONTINUE_TEST_LABEL = "Продолжить тест"

REVIEWS_URL = "https://vk.ru/feed?w=narrative15117889_8960"
TRIAL_URL = "https://vk.me/ellie_englie"

POST_TEST_REMINDERS = (
    (
        "🐾 Тотошка тут подумал: подарок-то вы забрали? 🎁",
        "button",
        "Забрать подарок",
    ),
    (
        "🐾 Ну как вам результат? Если хотите, Элли сама посмотрит, что лучше делать дальше 💚",
        "openlink",
        "Записаться на пробный",
    ),
    (
        "🐾 Я ещё тут 🙂 Если захотите понять, как помочь ребёнку с английским — Элли рядом.\n\n"
        "А я побежал! Больше не буду напоминать 💚",
        "openlink",
        "Записаться на пробный",
    ),
)

TEST_WELCOME_TEXT = (
    "Привет! Я Элли, и я помогаю школьникам полюбить английский и заговорить на нем.\n\n"
    "Заходите в мой бот «Тотошка» и проходите тест-квест по школьному английскому.\n"
    "После прохождения вы узнаете, что ваш ребенок помнит из учебной программы, что забыл или не понял, и что с этим теперь делать.\n\n"
    "Нажимайте на кнопку 👇\n\n"
    "Если кнопка не запускает тест — дайте мне знать:\n"
    "https://vk.me/ellie_englie\n\n"
    "Я сама позову Тотошку, и он все починит."
)

CLASS_SELECTION_TEXT = (
    "Выберите, в каком классе учится ребёнок.\n"
    "Если у вас языковая гимназия, выбирайте на уровень выше."
)

GIFT_OPTIONS = {
    "1-2": (
        (
            "Повторяем правила чтения в эпической битве с драконом:\n"
            "https://misselliegames.github.io/read-and-shoot/",
            "Открыть битву с драконом",
            "https://misselliegames.github.io/read-and-shoot/",
        ),
        (
            "Помочь капитану из Японии:\n"
            "https://misselliegames.github.io/ReadingLoadBoat/",
            "Помочь капитану",
            "https://misselliegames.github.io/ReadingLoadBoat/",
        ),
    ),
    "3-4": (
        (
            "Отправляемся в Подземелья и Драконы: бродим по лабиринтам, ищем тайные клады и тренируем грамматику:\n"
            "https://misselliegames.github.io/GrammarDungeon/",
            "Открыть Подземелья",
            "https://misselliegames.github.io/GrammarDungeon/",
        ),
        (
            "Поиграть с котиком:\n"
            "https://view.genially.com/68aacd3b7eb807e23b78c9f9",
            "Поиграть с котиком",
            "https://view.genially.com/68aacd3b7eb807e23b78c9f9",
        ),
    ),
    "5-6": (
        (
            "Раскроем тайну пропавшей экспедиции и повторим аж 72 неправильных глагола в большом квесте про Тинтина:\n"
            "https://misselliegames.github.io/TintinExpedition/",
            "Открыть квест про Тинтина",
            "https://misselliegames.github.io/TintinExpedition/",
        ),
        (
            "Поиграть с котиком:\n"
            "https://view.genially.com/6880daeca1dc1c756166020b",
            "Поиграть с котиком",
            "https://view.genially.com/6880daeca1dc1c756166020b",
        ),
    ),
}

QUESTION_STAGES = {"question", "sending_question", "question_retry", "question_transition"}
UNFINISHED_TEST_STAGES = QUESTION_STAGES | {
    "await_class", "await_handoff", "child_intro_retry", "await_go",
    "shop", "shop_finishing", "await_parent",
}
RESUMABLE_START_STAGES = UNFINISHED_TEST_STAGES | {"await_pd_consent", "await_marketing_consent"}
ROUTE_LABELS = {
    "1–2 класс": "1-2", "1-2 класс": "1-2",
    "3–4 класс": "3-4", "3-4 класс": "3-4",
    "5–6 класс": "5-6", "5-6 класс": "5-6",
}

VK_TOKEN = (os.getenv("VK_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
VK_GROUP_ID = (os.getenv("VK_GROUP_ID") or os.getenv("GROUP_ID") or "").strip()

if not VK_TOKEN:
    raise RuntimeError("Set VK_TOKEN (or BOT_TOKEN on Bothost)")

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()

def resolve_group_id(explicit: str) -> int:
    if explicit:
        return int(explicit)
    # A community token can identify its own community via groups.getById().
    # Handle both historical list response and newer wrapped response shapes.
    info = vk.groups.getById()
    if isinstance(info, list) and info:
        return int(info[0]["id"])
    if isinstance(info, dict):
        for key in ("groups", "items", "response"):
            arr = info.get(key)
            if isinstance(arr, list) and arr:
                return int(arr[0]["id"])
    raise RuntimeError("Could not determine VK group id from the community token; set VK_GROUP_ID manually")

VK_GROUP_ID_INT = resolve_group_id(VK_GROUP_ID)
upload = vk_api.VkUpload(vk_session)
longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID_INT)

SESSION_STORE = SessionStore(SESSION_DB_PATH)
SESSION_LOCK = threading.RLock()
SESSIONS = SESSION_STORE.load_all()
PHOTO_CACHE = {}
ELLIE_VK_ID = None


def blank_session():
    return {
        "session_id": uuid.uuid4().hex,
        "stage": "welcome",
        "question_index": 0,
        "emeralds": 0,
        "answers": [],
        "option_orders": {},
        "world_intros_sent": set(),
        "class": "",
        "shop_index": 0,
        "shop_selected": {},
        "shop_balance": 0,
        "last_activity_at": None,
        "reminders_sent": 0,
        "completed": False,
        "post_test_completed_at": None,
        "post_test_reminders_sent": 0,
        "pd_consent": False,
        "marketing_consent": None,
    }


def persist_session(user_id):
    session = SESSIONS.get(user_id)
    if session is not None:
        SESSION_STORE.save(user_id, session)


def current_questions(session):
    return questions_for_route(session.get("class") or "1-2")


def question_asset_path(session, question):
    route = session.get("class") or "1-2"
    subdir = QUESTION_ASSET_SUBDIRS[route]
    return QUESTION_ASSETS / subdir / question["image"] if subdir else QUESTION_ASSETS / question["image"]


def retry_call(action, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
    raise last_error


def send(user_id, text, keyboard=None, attachment=None, random_id=None):
    params = {
        "user_id": user_id,
        "message": text,
        "random_id": random_id or random.randint(1, 2_147_483_647),
    }
    if keyboard:
        params["keyboard"] = keyboard.get_keyboard()
    if attachment:
        params["attachment"] = attachment
    return retry_call(lambda: vk.messages.send(**params))


def one_button(label, color=VkKeyboardColor.PRIMARY):
    kb = VkKeyboard(one_time=True)
    kb.add_button(label, color=color)
    return kb


def test_step_keyboard(label, color=VkKeyboardColor.PRIMARY):
    kb = VkKeyboard(one_time=True)
    kb.add_button(label, color=color)
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def two_buttons(first_label, second_label):
    kb = VkKeyboard(one_time=True)
    kb.add_button(first_label, color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button(second_label, color=VkKeyboardColor.SECONDARY)
    return kb


def post_test_reminder_keyboard(button_type, label):
    kb = VkKeyboard(one_time=False)
    if button_type == "button":
        kb.add_button(label, color=VkKeyboardColor.PRIMARY)
    else:
        kb.add_openlink_button(label, TRIAL_URL)
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def answer_keyboard():
    kb = VkKeyboard(one_time=True)
    kb.add_button("A", color=VkKeyboardColor.PRIMARY)
    kb.add_button("B", color=VkKeyboardColor.PRIMARY)
    kb.add_button("C", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def class_keyboard():
    kb = VkKeyboard(one_time=True)
    kb.add_button("1–2 класс", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("3–4 класс", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("5–6 класс", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def main_menu_keyboard(has_unfinished_test=False):
    kb = VkKeyboard(one_time=False)
    first_label = CONTINUE_TEST_LABEL if has_unfinished_test else TEST_MENU_LABEL
    kb.add_button(first_label, color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button(GIFTS_LABEL, color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_openlink_button(REVIEWS_LABEL, REVIEWS_URL)
    kb.add_line()
    kb.add_openlink_button(TRIAL_LABEL, TRIAL_URL)
    return kb


def final_menu_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button(FINAL_TRIAL_LABEL, color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button(GIFTS_LABEL, color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button(REVIEWS_LABEL, color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button(RESTART_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def gift_class_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button("1–2 класс", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("3–4 класс", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("5–6 класс", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def gift_links_keyboard(gifts):
    kb = VkKeyboard(one_time=False)
    for index, (_text, label, url) in enumerate(gifts):
        kb.add_openlink_button(label, url)
        if index != len(gifts) - 1:
            kb.add_line()
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def link_section_keyboard(label, url):
    kb = VkKeyboard(one_time=False)
    kb.add_openlink_button(label, url)
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def upload_photo(path: Path):
    key = str(path.resolve())
    if key in PHOTO_CACHE:
        return PHOTO_CACHE[key]
    photo = retry_call(lambda: upload.photo_messages(photos=str(path)))[0]
    attachment = f"photo{photo['owner_id']}_{photo['id']}"
    PHOTO_CACHE[key] = attachment
    return attachment


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def update_subscriber(user_id, **updates):
    path = SUBSCRIBERS_CSV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    records = {}
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("vk_id"):
                    records[row["vk_id"]] = {field: row.get(field, "") for field in SUBSCRIBER_FIELDS}

    key = str(user_id)
    record = records.get(key, {field: "" for field in SUBSCRIBER_FIELDS})
    record.update({
        "vk_id": key,
        "policy_url": POLICY_URL,
        "pd_consent_url": PD_CONSENT_URL,
        "marketing_consent_url": MARKETING_CONSENT_URL,
    })
    for field, value in updates.items():
        if field in SUBSCRIBER_FIELDS:
            if isinstance(value, bool):
                value = "true" if value else "false"
            record[field] = str(value)
    records[key] = record

    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=SUBSCRIBER_FIELDS)
            writer.writeheader()
            writer.writerows(records.values())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def read_subscriber(user_id):
    if not SUBSCRIBERS_CSV_PATH.exists():
        return {}
    try:
        with SUBSCRIBERS_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("vk_id") == str(user_id):
                    return row
    except Exception as exc:
        print(f"SUBSCRIBER_READ_FAILED: {type(exc).__name__}")
    return {}


def saved_consent_state(user_id):
    session = SESSIONS.get(user_id) or {}
    pd_consent = session.get("pd_consent") is True
    marketing_consent = session.get("marketing_consent")
    if pd_consent and marketing_consent is not None:
        return pd_consent, marketing_consent

    record = read_subscriber(user_id)
    if not pd_consent:
        pd_consent = str(record.get("pd_consent", "")).lower() == "true"
    if marketing_consent is None:
        stored_marketing = str(record.get("marketing_consent", "")).lower()
        if stored_marketing in {"true", "false"}:
            marketing_consent = stored_marketing == "true"
    return pd_consent, marketing_consent


def replace_with_clean_test_session(user_id):
    pd_consent, marketing_consent = saved_consent_state(user_id)
    session = blank_session()
    session["pd_consent"] = pd_consent
    session["marketing_consent"] = marketing_consent
    session["stage"] = "await_class"
    SESSIONS[user_id] = session
    persist_session(user_id)
    return session


def question_text(q, options, total_questions):
    letters = ["A", "B", "C"]
    opts = "\n".join(f"{letters[i]}. {opt['text']}" for i, opt in enumerate(options))
    hint = f"{q['scene_hint']}\n\n" if q.get("scene_hint") else ""
    translation = f"\n{q['translation']}" if q["id"] in (1, 2) and q.get("translation") else ""
    return f"Задание {q['id']}/{total_questions}\n\n{hint}{q['question']}{translation}\n\n{opts}"


def send_question(user_id):
    s = SESSIONS[user_id]
    questions = current_questions(s)
    if s["question_index"] >= len(questions):
        start_shop(user_id)
        return
    q = questions[s["question_index"]]
    if q["id"] not in s["option_orders"]:
        order = list(range(len(q["options"])))
        random.shuffle(order)
        s["option_orders"][q["id"]] = order
        persist_session(user_id)
    options = [q["options"][i] for i in s["option_orders"][q["id"]]]
    s["stage"] = "sending_question"
    try:
        if q.get("world_intro") and q["id"] not in s["world_intros_sent"]:
            send(user_id, q["world_intro"])
            s["world_intros_sent"].add(q["id"])
        img_path = question_asset_path(s, q)
        attachment = upload_photo(img_path) if img_path.exists() else None
        send(user_id, question_text(q, options, len(questions)), keyboard=answer_keyboard(), attachment=attachment)
        s["stage"] = "question"
        persist_session(user_id)
    except Exception as exc:
        print(f"QUESTION_SEND_RETRY: {type(exc).__name__}")
        s["stage"] = "question_retry"
        send(
            user_id,
            "🐾 Тотошка опять зацепил провод! Но изумруды на месте 😅 Нажми «Продолжить», и попробуем ещё раз.",
            keyboard=test_step_keyboard("Продолжить", VkKeyboardColor.PRIMARY),
        )


def handle_answer(user_id, text):
    s = SESSIONS[user_id]
    questions = current_questions(s)
    q = questions[s["question_index"]]
    mapping = {"A": 0, "B": 1, "C": 2}
    choice = mapping.get(text.strip().upper())
    if choice is None:
        send(user_id, "Выбери ответ кнопкой A, B или C 🙂", keyboard=answer_keyboard())
        return
    option_index = s["option_orders"][q["id"]][choice]
    opt = q["options"][option_index]
    correct_opt = next(item for item in q["options"] if item.get("correct"))
    correct = bool(opt.get("correct"))
    earned = 2 if correct else 1
    s["emeralds"] += earned
    s["answers"].append({
        "question_id": q["id"],
        "topic": q["topic"],
        "topic_ru": q["topic_ru"],
        "question": q["question"],
        "selected": choice,
        "selected_text": opt["text"],
        "correct_text": correct_opt["text"],
        "correct": correct,
        "emeralds": earned,
        "error": opt.get("error"),
        "meaning": opt.get("meaning"),
    })
    if correct:
        reply = random.choice([
            "🐾 Гав! Точно! +2 💎 в твою копилку!",
            "🐾 Ура! Правильно! Лови два изумруда 💎💎",
            "🐾 Отлично! Ещё +2 💎!",
        ])
    else:
        reply = random.choice([
            "🐾 Почти! За смелость всё равно получаешь +1 💎!",
            "🐾 Не угадали, но смелость считается! Держи 1 💎.",
            "🐾 Ничего страшного — один изумруд за храбрость твой! 💎",
        ])
    s["question_index"] += 1
    s["last_activity_at"] = utc_now()
    s["stage"] = "question_transition"
    persist_session(user_id)
    try:
        send(user_id, f"{reply}\nСейчас у тебя: {s['emeralds']} 💎")
    except Exception as exc:
        print(f"ANSWER_FEEDBACK_SEND_FAILED: {type(exc).__name__}")
    send_question(user_id)


def start_shop(user_id):
    s = SESSIONS[user_id]
    s["stage"] = "shop"
    s["shop_index"] = 0
    s["shop_balance"] = s["emeralds"]
    persist_session(user_id)
    send(user_id, f"🐾 Гав! Мы дошли! Ты собрал(а) {s['emeralds']} 💎!\n\nТеперь самое интересное: построим твой собственный участок. Ты сможешь купить дом, сад, питомца и сокровище.")
    send_shop_category(user_id)


def shop_keyboard(items):
    kb = VkKeyboard(one_time=True)
    for i, item in enumerate(items):
        kb.add_button(f"{i+1}. {item['title']} — {item['price']} 💎", color=VkKeyboardColor.POSITIVE)
        if i != len(items) - 1:
            kb.add_line()
    kb.add_line()
    kb.add_button(MAIN_MENU_LABEL, color=VkKeyboardColor.SECONDARY)
    return kb


def send_shop_category(user_id):
    s = SESSIONS[user_id]
    if s["shop_index"] >= len(SHOP_CATEGORIES):
        finish_shop(user_id)
        return
    category = SHOP_CATEGORIES[s["shop_index"]]
    items = affordable_items(s["shop_balance"], s["shop_index"])
    s["offered_shop_items"] = items
    text = f"{CATEGORY_TITLES[category]}\nУ тебя осталось {s['shop_balance']} 💎"
    send(user_id, text, keyboard=shop_keyboard(items))


def handle_shop_choice(user_id, text):
    s = SESSIONS[user_id]
    offered = s.get("offered_shop_items", [])
    try:
        idx = int(text.strip().split(".", 1)[0]) - 1
    except Exception:
        send_shop_category(user_id)
        return
    if idx < 0 or idx >= len(offered):
        send_shop_category(user_id)
        return
    item = offered[idx]
    category = SHOP_CATEGORIES[s["shop_index"]]
    s["shop_selected"][category] = item["id"]
    s["shop_balance"] -= item["price"]
    persist_session(user_id)
    send(user_id, f"✨ Куплено: {item['title']}!\nОсталось {s['shop_balance']} 💎")
    s["shop_index"] += 1
    send_shop_category(user_id)


def finish_shop(user_id):
    s = SESSIONS[user_id]
    s["stage"] = "shop_finishing"
    out = GENERATED_DIR / f"shop_{uuid.uuid4().hex}.png"
    try:
        compose_shop_scene(SHOP_ASSETS, s["shop_selected"], out)
        attachment = upload_photo(out)
        leftover = s["shop_balance"]
        tail = f"\nИ ещё {leftover} 💎 осталось в твоём сундуке!" if leftover else ""
        send(user_id, f"🏡 Готово! Вот что ты собрал(а).{tail}", attachment=attachment)
    except Exception:
        send(user_id, "🏡 Готово! Твой участок собран. Картинку магазина подключим после загрузки всех PNG.")
    finally:
        if out.exists():
            out.unlink()
    update_subscriber(
        user_id,
        **{
            "class": s.get("class", "1-2"),
            "emeralds": s["emeralds"],
            "completed_at": utc_now(),
        },
    )
    send(user_id, "🐾 А теперь позови маму или папу и передай телефон. Я подготовил результат диагностики.", keyboard=test_step_keyboard("Родитель здесь", VkKeyboardColor.PRIMARY))
    s["stage"] = "await_parent"
    persist_session(user_id)


def build_summary(s):
    return diagnostic_build_summary(s)


def send_parent_report(user_id):
    s = SESSIONS[user_id]
    summary = build_summary(s)
    send(user_id, "Здравствуйте! Это Элли. Сейчас я соберу результаты по всем 20 заданиям — это займёт несколько секунд.")
    report = generate_parent_report(user_id, summary)
    send(user_id, report)
    s["stage"] = "done"
    s["completed"] = True
    s["post_test_completed_at"] = utc_now()
    s["post_test_reminders_sent"] = 0
    persist_session(user_id)
    send_final_menu(user_id)


def decline_emeralds(number):
    last_two = number % 100
    if 11 <= last_two <= 14:
        return "изумрудов"
    last = number % 10
    if last == 1:
        return "изумруд"
    if 2 <= last <= 4:
        return "изумруда"
    return "изумрудов"


def resolve_ellie_vk_id():
    global ELLIE_VK_ID
    if ELLIE_VK_ID is not None:
        return ELLIE_VK_ID
    try:
        result = retry_call(lambda: vk.utils.resolveScreenName(screen_name=ELLIE_SCREEN_NAME))
        if isinstance(result, dict):
            profile = result
        elif isinstance(result, list) and result:
            profile = result[0]
        else:
            profile = {}
        if profile.get("type") in {"user", "profile"} and profile.get("object_id"):
            ELLIE_VK_ID = int(profile["object_id"])
            return ELLIE_VK_ID
    except Exception as exc:
        print(f"ELLIE_RESOLVE_SCREEN_NAME_FAILED: {type(exc).__name__}")

    result = retry_call(lambda: vk.users.get(user_ids=ELLIE_SCREEN_NAME))
    if not isinstance(result, list) or not result or not result[0].get("id"):
        raise RuntimeError("Could not resolve Ellie personal VK profile")
    ELLIE_VK_ID = int(result[0]["id"])
    return ELLIE_VK_ID


def build_trial_lesson_link(emeralds):
    emerald_word = decline_emeralds(emeralds)
    contact_text = (
        f"Здравствуйте! Мой ребёнок прошёл ваш тест и заработал {emeralds} {emerald_word} 😊 "
        "Хочу записать ребёнка к вам на пробный урок."
    )
    encoded_text = quote(contact_text, safe="")
    return f"https://vk.com/write{resolve_ellie_vk_id()}?text={encoded_text}"


def show_test_welcome(user_id):
    session = SESSIONS.get(user_id)
    if session is None:
        session = blank_session()
        SESSIONS[user_id] = session
    if session.get("stage") not in RESUMABLE_START_STAGES:
        session["stage"] = "welcome"
    session["navigation_section"] = "test_welcome"
    session["test_welcome_ready"] = True
    persist_session(user_id)
    send(
        user_id,
        TEST_WELCOME_TEXT,
        keyboard=one_button(TEST_START_LABEL, VkKeyboardColor.POSITIVE),
    )


def send_class_selection(user_id):
    send(user_id, CLASS_SELECTION_TEXT, keyboard=class_keyboard())
    SESSIONS[user_id]["stage"] = "await_class"
    persist_session(user_id)


def resume_unfinished_flow(user_id):
    session = SESSIONS[user_id]
    stage = session.get("stage")
    if stage == "await_pd_consent":
        start_flow(user_id)
    elif stage == "await_marketing_consent":
        send_marketing_consent(user_id)
    elif stage == "await_class":
        send_class_selection(user_id)
    elif stage == "await_handoff":
        send_handoff(user_id)
    elif stage in {"child_intro_retry", "await_go"}:
        child_intro(user_id)
    elif stage in QUESTION_STAGES:
        send_question(user_id)
    elif stage == "shop":
        send_shop_category(user_id)
    elif stage == "shop_finishing":
        finish_shop(user_id)
    elif stage == "await_parent":
        send(
            user_id,
            "🐾 Передайте телефон маме или папе и нажмите кнопку.",
            keyboard=test_step_keyboard("Родитель здесь", VkKeyboardColor.PRIMARY),
        )


def begin_test(user_id):
    session = SESSIONS.get(user_id)
    if session:
        session.pop("test_welcome_ready", None)
        session.pop("navigation_section", None)
        persist_session(user_id)
    if session and not session.get("completed") and session.get("stage") in RESUMABLE_START_STAGES:
        resume_unfinished_flow(user_id)
        return
    pd_consent, _marketing_consent = saved_consent_state(user_id)
    if pd_consent:
        replace_with_clean_test_session(user_id)
        send_class_selection(user_id)
    else:
        start_flow(user_id)


def restart_test(user_id):
    session = SESSIONS.get(user_id)
    if session and session.get("completed") and saved_consent_state(user_id)[0]:
        replace_with_clean_test_session(user_id)
        send_class_selection(user_id)
        return
    if session and not session.get("completed") and session.get("stage") in UNFINISHED_TEST_STAGES:
        send(
            user_id,
            "У вас уже есть незаконченный тест. Продолжим его, чтобы не потерять ответы.",
        )
        resume_unfinished_flow(user_id)
        return
    show_test_welcome(user_id)


def show_main_menu(user_id):
    session = SESSIONS.get(user_id)
    if session is None:
        session = blank_session()
        SESSIONS[user_id] = session
    if not (not session.get("completed") and session.get("stage") in RESUMABLE_START_STAGES):
        session["stage"] = "main_menu"
    session["navigation_section"] = "main_menu"
    persist_session(user_id)
    has_unfinished_test = (
        not session.get("completed")
        and session.get("stage") in UNFINISHED_TEST_STAGES
    )
    send(
        user_id,
        "Главное меню",
        keyboard=main_menu_keyboard(has_unfinished_test),
    )


def show_gift_class_menu(user_id):
    session = SESSIONS.get(user_id)
    if session is None:
        session = blank_session()
        SESSIONS[user_id] = session
    if not (not session.get("completed") and session.get("stage") in RESUMABLE_START_STAGES):
        session["stage"] = "gift_class"
    session["navigation_section"] = "gift_class"
    persist_session(user_id)
    send(user_id, "Для какого класса выбрать подарок?", keyboard=gift_class_keyboard())


def show_gifts(user_id, route):
    gifts = GIFT_OPTIONS[route]
    session = SESSIONS[user_id]
    if not (not session.get("completed") and session.get("stage") in RESUMABLE_START_STAGES):
        session["stage"] = "gift_done"
    session["navigation_section"] = "gift_done"
    persist_session(user_id)
    send(
        user_id,
        "\n\n".join(text for text, _label, _url in gifts),
        keyboard=gift_links_keyboard(gifts),
    )


def show_link_section(user_id, title, label, url):
    session = SESSIONS.get(user_id)
    if session is None:
        session = blank_session()
        SESSIONS[user_id] = session
    if session.get("stage") not in RESUMABLE_START_STAGES:
        session["stage"] = "link_section"
    session["navigation_section"] = "link_section"
    persist_session(user_id)
    send(user_id, f"{title}:\n{url}", keyboard=link_section_keyboard(label, url))


def send_final_menu(user_id):
    send(
        user_id,
        "Что хотите сделать дальше? Здесь можно выбрать подарки, посмотреть отзывы, записаться на пробный урок или пройти тест заново.",
        keyboard=final_menu_keyboard(),
    )


def start_flow(user_id):
    SESSIONS[user_id] = blank_session()
    s = SESSIONS[user_id]
    send(user_id,
         "Ура! Вы добрались до ворот Изумрудного Города 💚 Элли хлопает в ладоши и очень рада вас видеть.\n\n"
         "Но даже здесь есть пара волшебных бумажек — обычная бюрократия.\n\n"
         "Перед началом теста нужно ваше согласие на обработку данных, необходимых для работы диагностики и подготовки результата.\n\n"
         f"📄 Политика обработки персональных данных:\n{POLICY_URL}\n\n"
         f"📄 Согласие на обработку персональных данных:\n{PD_CONSENT_URL}\n\n"
         "Если всё хорошо — идём дальше 👇",
         keyboard=two_buttons("Согласен(на), идём дальше", "Не согласен(на)"))
    s["stage"] = "await_pd_consent"
    persist_session(user_id)


def send_marketing_consent(user_id):
    send(
        user_id,
        "И ещё один вопрос от Стража ворот 😊\n\n"
        "Хотите иногда получать от Miss Ellie полезные материалы, новости о занятиях и специальные предложения?\n\n"
        "Это совершенно необязательно и никак не влияет на прохождение теста.\n\n"
        f"📄 Согласие на получение рекламных и информационных сообщений:\n{MARKETING_CONSENT_URL}",
        keyboard=two_buttons("Да, хочу получать", "Нет, спасибо"),
    )
    SESSIONS[user_id]["stage"] = "await_marketing_consent"
    persist_session(user_id)


def send_instruction(user_id):
    send(
        user_id,
        "ПРОЧИТАЙТЕ ВНИМАТЕЛЬНО ИНСТРУКЦИЮ:\n\n"
        "Вам нужно будет передать телефон ребёнку. Всего будет 20 вопросов. Сначала простые, потом чуть сложнее. "
        "Объясните ребёнку, что ошибаться можно, но лучше постараться вспомнить или угадать правильный ответ. "
        "Угадывать тоже можно — это наша языковая интуиция.\n\n"
        "За каждый правильный ответ ребёнок получает изумруды 💎, на которые в конце может построить себе маленький уютный мир в стиле Minecraft.\n\n"
        "После этого ребёнок вернёт вам телефон, и вы получите результаты теста.",
    )
    send_class_selection(user_id)


def send_handoff(user_id):
    send(
        user_id,
        "Отлично! Дальше отдайте телефон ребёнку. Не помогайте — он справится сам 😊\n\nПередали?",
        keyboard=test_step_keyboard("Да", VkKeyboardColor.POSITIVE),
    )
    SESSIONS[user_id]["stage"] = "await_handoff"
    persist_session(user_id)


def child_intro(user_id):
    s = SESSIONS[user_id]
    s["stage"] = "child_intro_retry"
    try:
        attachment = upload_photo(TOTOSHKA_INTRO)
    except Exception as exc:
        print(f"TOTOSHKA_PNG_UPLOAD_FAILED: {type(exc).__name__}")
        temp_jpg = GENERATED_DIR / f"totoshka_{uuid.uuid4().hex}.jpg"
        try:
            GENERATED_DIR.mkdir(parents=True, exist_ok=True)
            with Image.open(TOTOSHKA_INTRO) as source:
                source.load()
                if source.mode in {"RGBA", "LA"} or "transparency" in source.info:
                    rgba = source.convert("RGBA")
                    rgb = Image.new("RGB", rgba.size, "white")
                    rgb.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    rgb = source.convert("RGB")
                rgb.save(temp_jpg, "JPEG", quality=92, optimize=True)
            attachment = upload_photo(temp_jpg)
        except Exception as fallback_exc:
            print(f"TOTOSHKA_JPG_UPLOAD_FAILED: {type(fallback_exc).__name__}")
            send(
                user_id,
                "🐾 Тотошка на секунду потерялся! Нажми «Попробовать ещё раз».",
                keyboard=test_step_keyboard("Попробовать ещё раз", VkKeyboardColor.PRIMARY),
            )
            return
        finally:
            if temp_jpg.exists():
                temp_jpg.unlink()
    send(user_id,
         "Привет! 🐾\n\n"
         "Злая колдунья заколдовала дорогу из жёлтых кирпичей, и Тотошка не может найти дорогу в Изумрудный Город к Элли.\n\n"
         "Но английский язык открывает дверь в любой мир, и сейчас ты сможешь помочь Тотошке!\n\n"
         "Правильно отвечай на вопросы, копи изумрудики 💎, и в конце доберёшься до Изумрудного Города в мире Minecraft.\n\n"
         "Вперёд!",
         keyboard=test_step_keyboard("Вперёд!", VkKeyboardColor.POSITIVE), attachment=attachment)
    s["stage"] = "await_go"
    persist_session(user_id)


def on_message(user_id, text):
    lowered = text.strip().lower()
    if lowered == "стоп":
        update_subscriber(
            user_id,
            marketing_consent=False,
            marketing_revoked_at=utc_now(),
        )
        send(user_id, "Готово! Рекламные сообщения отключены 💚")
        return

    session = SESSIONS.get(user_id)
    stage = session.get("stage") if session else None

    if lowered in {"главное меню", MAIN_MENU_LABEL.lower()}:
        show_main_menu(user_id)
        return

    if lowered == TEST_MENU_LABEL.lower():
        show_test_welcome(user_id)
        return

    if lowered == TEST_START_LABEL.lower():
        if session and session.get("test_welcome_ready"):
            begin_test(user_id)
        else:
            show_test_welcome(user_id)
        return

    if lowered in START_COMMANDS:
        show_test_welcome(user_id)
        return

    if lowered in RESTART_COMMANDS:
        restart_test(user_id)
        return

    if lowered in {"подарки", "забрать подарок", GIFTS_LABEL.lower()}:
        show_gift_class_menu(user_id)
        return

    if lowered in {"отзывы", REVIEWS_LABEL.lower()}:
        show_link_section(user_id, "Отзывы", REVIEWS_LABEL, REVIEWS_URL)
        return

    if lowered in {
        "записаться на пробный урок",
        TRIAL_LABEL.lower(),
        FINAL_TRIAL_LABEL.lower(),
    }:
        show_link_section(user_id, "Записаться на пробный урок", TRIAL_LABEL, TRIAL_URL)
        return

    s = SESSIONS.get(user_id)
    if s is None:
        return

    stage = s["stage"]
    if lowered in {"продолжить тест", "продолжить", "закончить тест"} and stage in UNFINISHED_TEST_STAGES:
        s.pop("navigation_section", None)
        persist_session(user_id)
        resume_unfinished_flow(user_id)
        return
    if s.get("navigation_section") == "gift_class":
        route = ROUTE_LABELS.get(lowered)
        if route:
            show_gifts(user_id, route)
        else:
            show_gift_class_menu(user_id)
        return
    if stage == "await_pd_consent":
        if lowered == "согласен(на), идём дальше":
            now = utc_now()
            s["pd_consent"] = True
            persist_session(user_id)
            update_subscriber(user_id, pd_consent=True, pd_consent_at=now)
            send_marketing_consent(user_id)
        elif lowered == "не согласен(на)":
            s["pd_consent"] = False
            persist_session(user_id)
            update_subscriber(user_id, pd_consent=False, pd_consent_at="")
            send(
                user_id,
                "Понимаю 💚 Без согласия провести персональную диагностику не получится. Если передумаете, вернитесь в Главное меню.",
                keyboard=one_button(MAIN_MENU_LABEL, VkKeyboardColor.SECONDARY),
            )
            s["stage"] = "consent_declined"
            persist_session(user_id)
        else:
            start_flow(user_id)
    elif stage == "await_marketing_consent":
        if lowered == "да, хочу получать":
            s["marketing_consent"] = True
            persist_session(user_id)
            update_subscriber(
                user_id,
                marketing_consent=True,
                marketing_consent_at=utc_now(),
                marketing_revoked_at="",
            )
            send_instruction(user_id)
        elif lowered == "нет, спасибо":
            s["marketing_consent"] = False
            persist_session(user_id)
            update_subscriber(
                user_id,
                marketing_consent=False,
                marketing_consent_at="",
            )
            send_instruction(user_id)
        else:
            send_marketing_consent(user_id)
    elif stage == "await_class":
        route = ROUTE_LABELS.get(lowered)
        if route:
            s["class"] = route
            update_subscriber(user_id, **{"class": route})
            persist_session(user_id)
            send_handoff(user_id)
        else:
            send_class_selection(user_id)
    elif stage == "await_handoff":
        child_intro(user_id)
    elif stage == "child_intro_retry":
        child_intro(user_id)
    elif stage == "await_go":
        s["question_index"] = 0
        send_question(user_id)
    elif stage == "question":
        handle_answer(user_id, text)
    elif stage in {"sending_question", "question_retry", "question_transition"}:
        send_question(user_id)
    elif stage == "shop":
        handle_shop_choice(user_id, text)
    elif stage == "shop_finishing":
        finish_shop(user_id)
    elif stage == "await_parent":
        send_parent_report(user_id)
    elif stage == "done":
        send_final_menu(user_id)
    elif stage == "gift_class":
        route = ROUTE_LABELS.get(lowered)
        if route:
            show_gifts(user_id, route)
        else:
            show_gift_class_menu(user_id)
    elif stage in {"main_menu", "gift_done", "link_section", "welcome"}:
        show_main_menu(user_id)
    elif stage == "consent_declined":
        show_main_menu(user_id)


def run_due_reminders(now=None):
    now = now or datetime.now(timezone.utc)
    sent_count = 0
    for user_id in list(SESSIONS):
        with SESSION_LOCK:
            session = SESSIONS.get(user_id)
            if session is None:
                continue
            reminder_index = due_reminder_index(session, now, REMINDER_DELAYS)
            if reminder_index is None:
                continue
            questions = current_questions(session)
            if session["question_index"] >= len(questions):
                continue
            remaining = len(questions) - session["question_index"]
            text, button = render_reminder(reminder_index, remaining)
            session["reminders_sent"] = reminder_index + 1
            persist_session(user_id)
            random_id = reminder_random_id(session["session_id"], reminder_index + 1)
        try:
            send(
                user_id,
                text,
                keyboard=one_button(button, VkKeyboardColor.PRIMARY),
                random_id=random_id,
            )
            sent_count += 1
        except Exception as exc:
            # Release the claim so a genuine failure can be retried. Reusing the same
            # deterministic VK random_id prevents a duplicate if VK accepted the first
            # request but the client lost the response.
            with SESSION_LOCK:
                session = SESSIONS.get(user_id)
                if session and session.get("reminders_sent") == reminder_index + 1:
                    session["reminders_sent"] = reminder_index
                    persist_session(user_id)
            print(f"REMINDER_SEND_FAILED_{reminder_index + 1}: {type(exc).__name__}")
    return sent_count


def due_post_test_reminder_index(session, now):
    if not session.get("completed"):
        return None
    completed_at_raw = session.get("post_test_completed_at")
    if not completed_at_raw:
        return None
    sent = int(session.get("post_test_reminders_sent", 0))
    if sent < 0 or sent >= len(POST_TEST_REMINDERS):
        return None
    try:
        completed_at = datetime.fromisoformat(completed_at_raw)
    except (TypeError, ValueError):
        return None
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    elapsed_seconds = (now - completed_at).total_seconds()
    return sent if elapsed_seconds >= POST_TEST_REMINDER_DELAYS[sent] else None


def run_due_post_test_reminders(now=None):
    now = now or datetime.now(timezone.utc)
    sent_count = 0
    for user_id in list(SESSIONS):
        with SESSION_LOCK:
            session = SESSIONS.get(user_id)
            if session is None:
                continue
            reminder_index = due_post_test_reminder_index(session, now)
            if reminder_index is None:
                continue
            session["post_test_reminders_sent"] = reminder_index + 1
            persist_session(user_id)
            random_id = reminder_random_id(session["session_id"], 101 + reminder_index)
            text, button_type, button_label = POST_TEST_REMINDERS[reminder_index]
        try:
            keyboard = post_test_reminder_keyboard(button_type, button_label)
            send(user_id, text, keyboard=keyboard, random_id=random_id)
            sent_count += 1
        except Exception as exc:
            with SESSION_LOCK:
                session = SESSIONS.get(user_id)
                if session and session.get("post_test_reminders_sent") == reminder_index + 1:
                    session["post_test_reminders_sent"] = reminder_index
                    persist_session(user_id)
            print(f"POST_TEST_REMINDER_SEND_FAILED_{reminder_index + 1}: {type(exc).__name__}")
    return sent_count


def reminder_worker():
    while True:
        try:
            run_due_reminders()
        except Exception as exc:
            print(f"REMINDER_WORKER_ERROR: {type(exc).__name__}")
        time.sleep(REMINDER_POLL_SECONDS)


def post_test_reminder_worker():
    while True:
        try:
            run_due_post_test_reminders()
        except Exception as exc:
            print(f"POST_TEST_REMINDER_WORKER_ERROR: {type(exc).__name__}")
        time.sleep(REMINDER_POLL_SECONDS)


def validate_assets():
    missing = []
    invalid = []
    for route, questions in QUESTION_SETS.items():
        for question in questions:
            session = {"class": route}
            path = question_asset_path(session, question)
            if not path.exists():
                missing.append(str(path.relative_to(BASE_DIR)))
                continue
            try:
                with Image.open(path) as image:
                    image.verify()
            except Exception:
                invalid.append(str(path.relative_to(BASE_DIR)))
    required_shop = ["shop_background.jpg"]
    for category in SHOP_CATEGORIES:
        required_shop.extend(item["file"] for item in SHOP_ITEMS[category])
    for name in required_shop:
        path = SHOP_ASSETS / name
        if not path.exists():
            missing.append(str(path.relative_to(BASE_DIR)))
    if not TOTOSHKA_INTRO.exists():
        missing.append(str(TOTOSHKA_INTRO.relative_to(BASE_DIR)))
    if missing:
        raise RuntimeError("Missing asset files: " + ", ".join(missing))
    if invalid:
        raise RuntimeError("Invalid asset files: " + ", ".join(invalid))
    try:
        with Image.open(TOTOSHKA_INTRO) as image:
            image.verify()
    except Exception as exc:
        raise RuntimeError("Invalid asset file: assets/TOTO.png") from exc


def main():
    validate_assets()
    threading.Thread(target=reminder_worker, name="unfinished-test-reminders", daemon=True).start()
    threading.Thread(target=post_test_reminder_worker, name="post-test-reminders", daemon=True).start()
    print("Miss Ellie VK bot started; all route assets OK; reminders active")
    while True:
        try:
            for event in longpoll.listen():
                if event.type != VkBotEventType.MESSAGE_NEW:
                    continue
                obj = event.object.message
                if obj.get("out"):
                    continue
                user_id = obj["from_id"]
                text = obj.get("text", "")
                try:
                    on_message(user_id, text)
                except Exception as exc:
                    print(f"ERROR: {type(exc).__name__}")
                    s = SESSIONS.get(user_id)
                    try:
                        if s and s.get("stage") in {"question", "sending_question", "question_retry", "question_transition"}:
                            s["stage"] = "question_retry"
                            send(
                                user_id,
                                "🐾 Тотошка опять зацепил провод! Но изумруды на месте 😅 Нажми «Продолжить», и попробуем ещё раз.",
                                keyboard=one_button("Продолжить", VkKeyboardColor.PRIMARY),
                            )
                        else:
                            send(user_id, "Произошла временная ошибка. Пожалуйста, нажмите последнюю кнопку ещё раз.")
                    except Exception as send_exc:
                        print(f"ERROR_NOTICE_FAILED: {type(send_exc).__name__}")
                finally:
                    persist_session(user_id)
        except requests.exceptions.ReadTimeout:
            print("VK_LONGPOLL_TIMEOUT: reconnecting")
            time.sleep(2)
        except requests.exceptions.ConnectionError:
            print("VK_LONGPOLL_CONNECTION_ERROR: reconnecting")
            time.sleep(3)


if __name__ == "__main__":
    main()
