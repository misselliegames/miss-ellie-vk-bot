from __future__ import annotations

import os
import csv
import random
import time
import uuid
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote

import vk_api
import requests
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from PIL import Image

from questions import QUESTIONS, TOPIC_ORDER
from shop import SHOP_CATEGORIES, SHOP_ITEMS, CATEGORY_TITLES, affordable_items, compose_shop_scene
from ai_report import generate_parent_report

BASE_DIR = Path(__file__).resolve().parent
QUESTION_ASSETS = BASE_DIR / "assets" / "questions"
SHOP_ASSETS = BASE_DIR / "assets" / "shop"
GENERATED_DIR = BASE_DIR / "generated"
TOTOSHKA_INTRO = BASE_DIR / "assets" / "TOTO.png"

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
START_COMMANDS = {"начать", "начать тест", "тест", "пройти тест", "старт", "/start", "заново"}
ELLIE_SCREEN_NAME = "ellie_englie"

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

SESSIONS = {}
PHOTO_CACHE = {}
ELLIE_VK_ID = None

TOPIC_NAMES = {q["topic"]: q["topic_ru"] for q in QUESTIONS}


def blank_session():
    return {
        "stage": "await_pd_consent",
        "question_index": 0,
        "emeralds": 0,
        "answers": [],
        "option_orders": {},
        "world_intros_sent": set(),
        "class": "",
        "shop_index": 0,
        "shop_selected": {},
        "shop_balance": 0,
    }


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


def send(user_id, text, keyboard=None, attachment=None):
    params = {
        "user_id": user_id,
        "message": text,
        "random_id": random.randint(1, 2_147_483_647),
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


def two_buttons(first_label, second_label):
    kb = VkKeyboard(one_time=True)
    kb.add_button(first_label, color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button(second_label, color=VkKeyboardColor.SECONDARY)
    return kb


def openlink_button(label, link):
    kb = VkKeyboard(one_time=False)
    kb.add_openlink_button(label, link)
    return kb


def answer_keyboard():
    kb = VkKeyboard(one_time=True)
    kb.add_button("A", color=VkKeyboardColor.PRIMARY)
    kb.add_button("B", color=VkKeyboardColor.PRIMARY)
    kb.add_button("C", color=VkKeyboardColor.PRIMARY)
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


def question_text(q, options):
    letters = ["A", "B", "C"]
    opts = "\n".join(f"{letters[i]}. {opt['text']}" for i, opt in enumerate(options))
    hint = f"{q['scene_hint']}\n\n" if q.get("scene_hint") else ""
    translation = f"\n{q['translation']}" if q["id"] in (1, 2) and q.get("translation") else ""
    return f"Задание {q['id']}/20\n\n{hint}{q['question']}{translation}\n\n{opts}"


def send_question(user_id):
    s = SESSIONS[user_id]
    if s["question_index"] >= len(QUESTIONS):
        start_shop(user_id)
        return
    q = QUESTIONS[s["question_index"]]
    if q["id"] not in s["option_orders"]:
        order = list(range(len(q["options"])))
        random.shuffle(order)
        s["option_orders"][q["id"]] = order
    options = [q["options"][i] for i in s["option_orders"][q["id"]]]
    s["stage"] = "sending_question"
    try:
        if q.get("world_intro") and q["id"] not in s["world_intros_sent"]:
            send(user_id, q["world_intro"])
            s["world_intros_sent"].add(q["id"])
        img_path = QUESTION_ASSETS / q["image"]
        attachment = upload_photo(img_path) if img_path.exists() else None
        send(user_id, question_text(q, options), keyboard=answer_keyboard(), attachment=attachment)
        s["stage"] = "question"
    except Exception as exc:
        print(f"QUESTION_SEND_RETRY: {type(exc).__name__}")
        s["stage"] = "question_retry"
        send(
            user_id,
            "🐾 Тотошка опять зацепил провод! Но изумруды на месте 😅 Нажми «Продолжить», и попробуем ещё раз.",
            keyboard=one_button("Продолжить", VkKeyboardColor.PRIMARY),
        )


def handle_answer(user_id, text):
    s = SESSIONS[user_id]
    q = QUESTIONS[s["question_index"]]
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
    s["stage"] = "question_transition"
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
    send(user_id, f"🐾 Гав! Мы дошли! Ты собрал(а) {s['emeralds']} 💎!\n\nТеперь самое интересное: построим твой собственный участок. Ты сможешь купить дом, сад, питомца и сокровище.")
    send_shop_category(user_id)


def shop_keyboard(items):
    kb = VkKeyboard(one_time=True)
    for i, item in enumerate(items):
        kb.add_button(f"{i+1}. {item['title']} — {item['price']} 💎", color=VkKeyboardColor.POSITIVE)
        if i != len(items) - 1:
            kb.add_line()
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
    send(user_id, "🐾 А теперь позови маму или папу и передай телефон. Я подготовил результат диагностики.", keyboard=one_button("Родитель здесь", VkKeyboardColor.PRIMARY))
    s["stage"] = "await_parent"


def build_summary(s):
    by_topic = defaultdict(list)
    for a in s["answers"]:
        by_topic[a["topic"]].append(a)
    topics = []
    for topic in TOPIC_ORDER:
        arr = by_topic.get(topic, [])
        score = sum(1 for x in arr if x["correct"])
        topics.append({
            "topic": topic,
            "topic_ru": TOPIC_NAMES.get(topic, topic),
            "score": score,
            "max": 2,
            "status": "mastered" if score == 2 else "partial" if score == 1 else "needs_work",
        })
    answers = [
        {
            "question_id": a["question_id"],
            "topic": a["topic"],
            "topic_ru": a["topic_ru"],
            "question": a["question"],
            "selected_text": a["selected_text"],
            "correct_text": a["correct_text"],
            "correct": a["correct"],
            "meaning": a.get("meaning") if not a["correct"] else None,
        }
        for a in s["answers"]
    ]
    return {
        "route": "Pre-A1 / Starters / 1–2 класс",
        "correct_total": sum(1 for a in s["answers"] if a["correct"]),
        "total_questions": 20,
        "emeralds": s["emeralds"],
        "topics": topics,
        "answers": answers,
        "limitations": "Выбор ответа; не проверялись полноценно устная речь, понимание речи на слух и самостоятельное построение фраз.",
    }


def send_parent_report(user_id):
    s = SESSIONS[user_id]
    summary = build_summary(s)
    send(user_id, "Здравствуйте! Это Элли. Сейчас я соберу результаты по всем 20 заданиям — это займёт несколько секунд.")
    report = generate_parent_report(user_id, summary)
    try:
        trial_link = build_trial_lesson_link(s["emeralds"])
    except Exception as exc:
        print(f"TRIAL_LINK_BUILD_FAILED: {type(exc).__name__}")
        raise
    try:
        send(
            user_id,
            report,
            keyboard=openlink_button("Записаться на пробный урок", trial_link),
        )
    except Exception as exc:
        print(f"PARENT_REPORT_SEND_FAILED: {type(exc).__name__}")
        raise
    s["stage"] = "done"


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


def start_flow(user_id):
    SESSIONS[user_id] = blank_session()
    s = SESSIONS[user_id]
    send(user_id,
         "Ура, вы добрались до ворот Изумрудного Города! 💚\n"
         "Но даже здесь есть пара волшебных бумажек — обычная бюрократия, примерно как зелёные очки от Дин Гиора 😄\n\n"
         "Перед началом теста нужно ваше согласие на обработку данных, необходимых для работы диагностики и подготовки результата.\n\n"
         f"📄 Политика обработки персональных данных:\n{POLICY_URL}\n\n"
         f"📄 Согласие на обработку персональных данных:\n{PD_CONSENT_URL}\n\n"
         "Если всё хорошо — идём дальше 👇",
         keyboard=two_buttons("Согласен(на), идём дальше", "Не согласен(на)"))
    s["stage"] = "await_pd_consent"


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


def send_instruction(user_id):
    send(
        user_id,
        "ПРОЧИТАЙТЕ ВНИМАТЕЛЬНО ИНСТРУКЦИЮ:\n\n"
        "Вам нужно будет передать телефон ребёнку. Всего будет 20 вопросов. Сначала простые, потом чуть сложнее. "
        "Объясните ребёнку, что ошибаться можно, но лучше постараться вспомнить или угадать правильный ответ. "
        "Угадывать тоже можно — это наша языковая интуиция.\n\n"
        "За каждый правильный ответ ребёнок получает изумруды 💎, на которые в конце может построить себе маленький уютный мир в стиле Minecraft.\n\n"
        "После этого ребёнок вернёт вам телефон, и вы получите результаты теста.\n\n"
        "Итак, выберите, в каком классе учится ребёнок.",
        keyboard=one_button("1–2 класс", VkKeyboardColor.POSITIVE),
    )
    SESSIONS[user_id]["stage"] = "await_class"


def send_handoff(user_id):
    send(
        user_id,
        "Отлично! Дальше отдайте телефон ребёнку. Не помогайте — он справится сам 😊\n\nПередали?",
        keyboard=one_button("Да", VkKeyboardColor.POSITIVE),
    )
    SESSIONS[user_id]["stage"] = "await_handoff"


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
                keyboard=one_button("Попробовать ещё раз", VkKeyboardColor.PRIMARY),
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
         keyboard=one_button("Вперёд!", VkKeyboardColor.POSITIVE), attachment=attachment)
    s["stage"] = "await_go"


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

    if lowered in START_COMMANDS:
        start_flow(user_id)
        return

    s = SESSIONS.get(user_id)
    if s is None:
        return

    stage = s["stage"]
    if stage == "await_pd_consent":
        if lowered == "согласен(на), идём дальше":
            now = utc_now()
            update_subscriber(user_id, pd_consent=True, pd_consent_at=now)
            send_marketing_consent(user_id)
        elif lowered == "не согласен(на)":
            update_subscriber(user_id, pd_consent=False, pd_consent_at="")
            send(user_id, "Понимаю 💚 Без согласия провести персональную диагностику не получится. Если передумаете, напишите «Начать».")
            s["stage"] = "consent_declined"
        else:
            start_flow(user_id)
    elif stage == "await_marketing_consent":
        if lowered == "да, хочу получать":
            update_subscriber(
                user_id,
                marketing_consent=True,
                marketing_consent_at=utc_now(),
                marketing_revoked_at="",
            )
            send_instruction(user_id)
        elif lowered == "нет, спасибо":
            update_subscriber(
                user_id,
                marketing_consent=False,
                marketing_consent_at="",
            )
            send_instruction(user_id)
        else:
            send_marketing_consent(user_id)
    elif stage == "await_class":
        if lowered == "1–2 класс" or lowered == "1-2 класс":
            s["class"] = "1-2"
            update_subscriber(user_id, **{"class": "1-2"})
            send_handoff(user_id)
        else:
            send_instruction(user_id)
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
        send(user_id, "Диагностика завершена. Чтобы пройти её заново, напишите «Заново».")
    elif stage == "consent_declined":
        send(user_id, "Чтобы вернуться к диагностике, напишите «Начать».")


def validate_assets():
    missing = []
    for q in QUESTIONS:
        path = QUESTION_ASSETS / q["image"]
        if not path.exists():
            missing.append(str(path.relative_to(BASE_DIR)))
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
    try:
        with Image.open(TOTOSHKA_INTRO) as image:
            image.verify()
    except Exception as exc:
        raise RuntimeError("Invalid asset file: assets/TOTO.png") from exc


def main():
    validate_assets()
    print("Miss Ellie VK bot started; assets OK")
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
        except requests.exceptions.ReadTimeout:
            print("VK_LONGPOLL_TIMEOUT: reconnecting")
            time.sleep(2)
        except requests.exceptions.ConnectionError:
            print("VK_LONGPOLL_CONNECTION_ERROR: reconnecting")
            time.sleep(3)


if __name__ == "__main__":
    main()
