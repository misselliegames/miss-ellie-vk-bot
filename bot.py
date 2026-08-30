from __future__ import annotations

import os
import random
from pathlib import Path
from collections import defaultdict

import vk_api
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

TOPIC_NAMES = {q["topic"]: q["topic_ru"] for q in QUESTIONS}


def blank_session():
    return {
        "stage": "await_parent_start",
        "question_index": 0,
        "emeralds": 0,
        "answers": [],
        "shop_index": 0,
        "shop_selected": {},
        "shop_balance": 0,
    }


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
    vk.messages.send(**params)


def one_button(label, color=VkKeyboardColor.PRIMARY):
    kb = VkKeyboard(one_time=True)
    kb.add_button(label, color=color)
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
    photo = upload.photo_messages(photos=str(path))[0]
    attachment = f"photo{photo['owner_id']}_{photo['id']}"
    PHOTO_CACHE[key] = attachment
    return attachment


def question_text(q):
    letters = ["A", "B", "C"]
    opts = "\n".join(f"{letters[i]}. {opt['text']}" for i, opt in enumerate(q["options"]))
    hint = f"{q['scene_hint']}\n\n" if q.get("scene_hint") else ""
    translation = f"\n{q['translation']}" if q.get("translation") else ""
    return f"Задание {q['id']}/20\n\n{hint}{q['question']}{translation}\n\n{opts}"


def send_question(user_id):
    s = SESSIONS[user_id]
    if s["question_index"] >= len(QUESTIONS):
        start_shop(user_id)
        return
    q = QUESTIONS[s["question_index"]]
    if q.get("world_intro"):
        send(user_id, q["world_intro"])
    img_path = QUESTION_ASSETS / q["image"]
    attachment = upload_photo(img_path) if img_path.exists() else None
    send(user_id, question_text(q), keyboard=answer_keyboard(), attachment=attachment)
    s["stage"] = "question"


def handle_answer(user_id, text):
    s = SESSIONS[user_id]
    q = QUESTIONS[s["question_index"]]
    mapping = {"A": 0, "B": 1, "C": 2}
    choice = mapping.get(text.strip().upper())
    if choice is None:
        send(user_id, "Выбери ответ кнопкой A, B или C 🙂", keyboard=answer_keyboard())
        return
    opt = q["options"][choice]
    correct = bool(opt.get("correct"))
    earned = 2 if correct else 1
    s["emeralds"] += earned
    s["answers"].append({
        "question_id": q["id"],
        "topic": q["topic"],
        "selected": choice,
        "selected_text": opt["text"],
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
    send(user_id, f"{reply}\nСейчас у тебя: {s['emeralds']} 💎")
    s["question_index"] += 1
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
    out = GENERATED_DIR / f"shop_{user_id}.png"
    try:
        compose_shop_scene(SHOP_ASSETS, s["shop_selected"], out)
        attachment = upload_photo(out)
        leftover = s["shop_balance"]
        tail = f"\nИ ещё {leftover} 💎 осталось в твоём сундуке!" if leftover else ""
        send(user_id, f"🏡 Готово! Вот что ты собрал(а).{tail}", attachment=attachment)
    except Exception:
        send(user_id, "🏡 Готово! Твой участок собран. Картинку магазина подключим после загрузки всех PNG.")
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
    errors = [
        {"question_id": a["question_id"], "topic": a["topic"], "meaning": a["meaning"]}
        for a in s["answers"] if not a["correct"] and a.get("meaning")
    ]
    return {
        "route": "Pre-A1 / Starters / 1–2 класс",
        "correct_total": sum(1 for a in s["answers"] if a["correct"]),
        "total_questions": 20,
        "emeralds": s["emeralds"],
        "topics": topics,
        "errors": errors,
        "limitations": "Выбор ответа; не проверялись полноценно speaking, listening и самостоятельное построение фраз.",
    }


def send_parent_report(user_id):
    s = SESSIONS[user_id]
    summary = build_summary(s)
    send(user_id, "Здравствуйте! Это Элли. Сейчас я соберу результаты по всем 20 заданиям — это займёт несколько секунд.")
    report = generate_parent_report(user_id, summary)
    send(user_id, report)
    send(user_id, "Если захотите, следующим шагом можно проверить эти же темы уже без готовых вариантов ответа — в речи и небольших игровых заданиях.")
    s["stage"] = "done"


def start_flow(user_id):
    SESSIONS[user_id] = blank_session()
    s = SESSIONS[user_id]
    send(user_id,
         "Здравствуйте! Это короткая игровая диагностика английского Pre-A1 / Starters для 1–2 класса.\n\n"
         "В ней 20 заданий. После детской части я покажу вам результат по 10 темам.\n\n"
         "Передайте, пожалуйста, телефон ребёнку и нажмите кнопку ниже.",
         keyboard=one_button("Телефон у ребёнка", VkKeyboardColor.POSITIVE))
    s["stage"] = "await_child"


def child_intro(user_id):
    s = SESSIONS[user_id]
    send(user_id,
         "🐾 Гав! Я Тотошка! Мы отправляемся в путешествие.\n\n"
         "Будет 20 коротких заданий. За правильный ответ ты получишь 2 💎, а если ошибёшься — всё равно 1 💎 за храбрость!\n\n"
         "В конце мы потратим изумруды и построим твой собственный участок. Готов(а)?",
         keyboard=one_button("Поехали!", VkKeyboardColor.POSITIVE))
    s["stage"] = "await_go"


def on_message(user_id, text):
    s = SESSIONS.get(user_id)
    lowered = text.strip().lower()
    if s is None or lowered in {"начать", "start", "старт", "заново"}:
        start_flow(user_id)
        return

    stage = s["stage"]
    if stage == "await_child":
        child_intro(user_id)
    elif stage == "await_go":
        s["question_index"] = 0
        send_question(user_id)
    elif stage == "question":
        handle_answer(user_id, text)
    elif stage == "shop":
        handle_shop_choice(user_id, text)
    elif stage == "await_parent":
        send_parent_report(user_id)
    elif stage == "done":
        send(user_id, "Диагностика завершена. Чтобы пройти её заново, напишите «Заново».")


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
    if missing:
        raise RuntimeError("Missing asset files: " + ", ".join(missing))


def main():
    validate_assets()
    print("Miss Ellie VK bot started; assets OK")
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
            print("ERROR", user_id, repr(exc))
            send(user_id, "Кажется, Тотошка споткнулся о провод 😅 Напиши «Заново», и мы начнём ещё раз.")


if __name__ == "__main__":
    main()
