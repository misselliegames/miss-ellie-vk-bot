from questions import QUESTIONS as STARTERS_QUESTIONS
from questions_3_4 import QUESTIONS_3_4
from questions_5_6 import QUESTIONS_5_6


QUESTION_SETS = {
    "1-2": STARTERS_QUESTIONS,
    "3-4": QUESTIONS_3_4,
    "5-6": QUESTIONS_5_6,
}

ROUTE_NAMES = {
    "1-2": "Pre-A1 / Starters / 1–2 класс",
    "3-4": "A1 / Movers / 3–4 класс",
    "5-6": "A1+ / 5–6 класс",
}

QUESTION_ASSET_SUBDIRS = {
    "1-2": "",
    "3-4": "3-4",
    "5-6": "5-6",
}


def questions_for_route(route):
    return QUESTION_SETS.get(route, STARTERS_QUESTIONS)


def topic_order_for_route(route):
    return list(dict.fromkeys(q["topic"] for q in questions_for_route(route)))
