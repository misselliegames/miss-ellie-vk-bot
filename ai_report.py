from __future__ import annotations

import json
import os
import re

import requests


TEACHER_VK_ID = int(os.getenv("TEACHER_VK_ID", "2840329"))
MAX_REPORT_CHARS = 3500

ROUTE_RANGES = {
    "1-2": "1–2 класс",
    "3-4": "3–4 класс",
    "5-6": "5–6 класс",
}

ROUTE_LEVELS = {
    "1-2": "Pre-A1",
    "3-4": "A1",
    "5-6": "A1+",
}

# These blocks contain material that should already be secure before the child
# starts the main part of the selected route.
FOUNDATION_QUESTION_IDS = {
    "3-4": tuple(range(1, 5)),
    "5-6": tuple(range(1, 10)),
}

SEVERITY_ORDER = {"none": 0, "small": 1, "noticeable": 2, "substantial": 3}
SEVERITY_LABELS = {
    "none": "по заданиям ошибок нет",
    "small": "есть отдельные ошибки",
    "noticeable": "есть ошибки в нескольких темах",
    "substantial": "ошибок много, в том числе в важных темах",
}

TOPIC_LABELS = {
    "NUMBERS": "числительные и вопросы о цене",
    "TO_BE": "глагол to be (am, is, are): выбор формы по подлежащему",
    "HAVE_GOT": "have got / has got: рассказ о том, что у кого-то есть",
    "PRESENT_SIMPLE": "Present Simple: действия, которые повторяются регулярно",
    "CAN": "глагол can: смысловой глагол без to и окончания -s",
    "THERE_IS_ARE": "there is / there are: рассказ о том, что где-то находится",
    "PREPOSITIONS": "предлоги места (in, on, under)",
    "PRESENT_CONTINUOUS": "Present Continuous — действия, происходящие прямо сейчас",
    "PLURAL": "множественное число существительных",
    "DEMONSTRATIVES": "указательные местоимения this, that, these, those",
    "POSSESSIVE_FAMILY": "притяжательные местоимения my, your, his, her: выбор слова по владельцу",
    "BE_HAVE_APPEARANCE": "to be и have got / has got: описание эмоций и внешности",
    "PRESENT_SIMPLE_CONTINUOUS": "Present Simple и Present Continuous: что происходит регулярно, а что прямо сейчас",
    "COMPARATIVE_ADJECTIVES": "сравнительная степень прилагательных",
    "SUPERLATIVE_ADJECTIVES": "превосходная степень прилагательных",
    "SOME_ANY": "some / any в утверждениях, вопросах и отрицаниях",
    "PAST_SIMPLE": "Past Simple: неправильные глаголы и вопросы с did",
    "WAS_WERE": "формы was / were в прошедшем времени",
    "THERE_WAS_WERE": "there was / there were: рассказ о предметах и местах в прошлом",
    "MUST_MUSTNT": "must / mustn’t: обязанность и запрет",
    "MUCH_MANY": "much / many с исчисляемыми и неисчисляемыми существительными",
    "QUANTIFIERS": "слова количества not much, not many, a lot of",
    "FUTURE_FORMS": "будущее время: will и be going to",
    "POSSESSIVE_BE_HAVE": "притяжательные местоимения, to be и have got / has got",
    "HOW_MUCH_NUMBERS": "вопрос How much...? и числительные 21–100",
    "PRESENT_SIMPLE_TRAVEL": "Present Simple: действия, которые повторяются регулярно, и окончание -s в 3-м лице",
    "PRESENT_CONTINUOUS_TRAVEL": "Present Continuous и Present Simple: что происходит сейчас, а что повторяется регулярно",
    "PRESENT_SIMPLE_NEGATIVE": "вопросы и отрицания в Present Simple",
    "CAN_CLOTHES": "глагол can: смысловой глагол в начальной форме",
    "THERE_IS_ARE_SOME_ANY": "there is / there are и some / any",
    "SUPERLATIVE_ADVERBS": "превосходная степень наречий",
    "ENJOY_GERUND_QUESTION": "порядок слов в вопросе и герундий после enjoy",
    "ENJOY_GERUND": "герундий после enjoy",
    "FEW_LITTLE": "few / a few и little / a little: количество и достаточность",
    "REFLEXIVE_PRONOUNS": "возвратные местоимения himself / herself",
    "HAVE_TO_HAS_TO": "have to / has to: обязанность и выбор формы по подлежащему",
    "MUSTNT_DONT_HAVE_TO_NEEDNT": "mustn’t, don’t have to и needn’t: запрет и отсутствие необходимости",
    "SHOULD": "глагол should: совет и форма глагола без to",
    "WANT_TO_LET": "конструкции want to do и let somebody do",
    "IMPERATIVE_ROAD_SAFETY": "повелительное наклонение и дорожные инструкции",
    "FUTURE_ARRANGEMENT": "Present Continuous для договорённости на будущее",
    "FUTURE_PLANS": "be going to для заранее существующего плана",
    "FUTURE_DECISIONS": "will для решения, принятого в момент речи",
}

TOPIC_SKILLS = {
    "NUMBERS": "читает числа и отвечает на вопросы о цене",
    "TO_BE": "выбирает нужную форму глагола to be в простых предложениях",
    "HAVE_GOT": "правильно говорит о том, что у кого-то есть, с помощью have got и has got",
    "PRESENT_SIMPLE": "использует Present Simple, когда говорит о регулярных действиях",
    "CAN": "правильно ставит смысловой глагол после can",
    "THERE_IS_ARE": "описывает, что и где находится, с помощью there is и there are",
    "PREPOSITIONS": "различает основные предлоги места in, on и under",
    "PRESENT_CONTINUOUS": "говорит о том, что происходит прямо сейчас, в Present Continuous",
    "PLURAL": "образует множественное число существительных",
    "DEMONSTRATIVES": "различает this, that, these и those",
    "POSSESSIVE_FAMILY": "выбирает притяжательные местоимения по тому, кому что принадлежит",
    "BE_HAVE_APPEARANCE": "описывает эмоции и внешность с помощью to be и have got",
    "PRESENT_SIMPLE_CONTINUOUS": "различает регулярные действия и то, что происходит прямо сейчас",
    "COMPARATIVE_ADJECTIVES": "сравнивает признаки с помощью сравнительной степени прилагательных",
    "SUPERLATIVE_ADJECTIVES": "правильно использует превосходную степень прилагательных",
    "SOME_ANY": "различает some и any в утверждениях и вопросах",
    "PAST_SIMPLE": "использует неправильные глаголы и задаёт вопросы с did в Past Simple",
    "WAS_WERE": "выбирает между was и were",
    "THERE_WAS_WERE": "описывает предметы и места в прошлом с помощью there was и there were",
    "MUST_MUSTNT": "различает обязанность и запрет с must и mustn't",
    "MUCH_MANY": "различает much и many",
    "QUANTIFIERS": "понимает разницу между not much, not many и a lot of",
    "FUTURE_FORMS": "различает will и be going to в рассказе о будущем",
    "POSSESSIVE_BE_HAVE": "связывает притяжательные местоимения с формами to be и have got",
    "HOW_MUCH_NUMBERS": "понимает вопрос How much и читает числа до ста",
    "PRESENT_SIMPLE_TRAVEL": "правильно использует Present Simple и окончание -s в третьем лице",
    "PRESENT_CONTINUOUS_TRAVEL": "различает то, что происходит сейчас, и регулярные действия",
    "PRESENT_SIMPLE_NEGATIVE": "строит вопросы и отрицания в Present Simple",
    "CAN_CLOTHES": "правильно ставит смысловой глагол после can",
    "THERE_IS_ARE_SOME_ANY": "сочетает there is и there are с some и any",
    "SUPERLATIVE_ADVERBS": "образует превосходную степень наречий",
    "ENJOY_GERUND_QUESTION": "строит вопросы и использует форму с -ing после enjoy",
    "ENJOY_GERUND": "использует форму с -ing после enjoy",
    "FEW_LITTLE": "различает few, a few, little и a little по смыслу",
    "REFLEXIVE_PRONOUNS": "правильно использует возвратные местоимения himself и herself",
    "HAVE_TO_HAS_TO": "выбирает между have to и has to",
    "MUSTNT_DONT_HAVE_TO_NEEDNT": "различает запрет и отсутствие необходимости",
    "SHOULD": "даёт совет с should и ставит после него начальную форму глагола",
    "WANT_TO_LET": "правильно использует конструкции want to do и let somebody do",
    "IMPERATIVE_ROAD_SAFETY": "понимает дорожные инструкции в повелительном наклонении",
    "FUTURE_ARRANGEMENT": "использует Present Continuous для договорённости на будущее",
    "FUTURE_PLANS": "использует be going to для заранее намеченного плана",
    "FUTURE_DECISIONS": "использует will для решения, принятого в момент речи",
}

# Only errors whose distractor explicitly diagnoses a lexical difficulty are
# counted as vocabulary evidence. A normal grammar error must not be silently
# reinterpreted as a vocabulary gap.
LEXICAL_ERROR_INFO = {
    "NUM_RECOGNITION": ("числительные", False),
    "FAMILY_DAUGHTER_HUSBAND": ("семья", False),
    "FEELINGS_APPEARANCE": ("чувства и внешность", False),
    "DOLL_BALL": ("игрушки и чтение слов", False),
    "ACTION_VOCABULARY": ("одежда и повседневные действия", False),
    "TALL_SHORT": ("внешность и описание предметов", False),
    "FAST_LONG": ("описание движения", False),
    "FOOD_ICE_CREAM_CHEESE": ("еда", False),
    "CITY_FOREST": ("места и путешествия", False),
    "CLIMB_SWIM": ("действия и путешествия", False),
    "PAST_PRESENT_ROOMS": ("дом и комнаты", True),
    "THERE_WORD_ORDER_FURNITURE": ("дом и предметы дома", True),
    "TAKE_FEED": ("повседневные действия", False),
    "HOUSEWORK_VOCABULARY": ("домашние обязанности", False),
    "TSHIRT_JACKET": ("одежда", False),
    "HAVE_DO_LUNCH": ("еда и повседневные действия", False),
    "CHEESE_EGGS": ("еда", False),
    "FUTURE_HOUSE_GARDEN": ("дом и окружающие предметы", True),
    "HURT_FALL_DOWN": ("действия и самочувствие", False),
    "TRAVEL_DRIVE_FLY": ("путешествия и транспорт", False),
    "HOW_MUCH_VS_WHERE": ("покупки и вопрос о цене", False),
    "HOW_MUCH_FUNCTION": ("покупки и вопрос о цене", False),
    "BY_AIR_ON_FOOT": ("транспорт и способы передвижения", False),
    "CEREAL_SAUSAGES": ("еда", False),
    "CLOTHES_EQUIPMENT": ("одежда и экипировка", False),
    "TALLER_MEANING": ("внешность и описание предметов", False),
    "FAST_SLOW": ("движение и транспорт", False),
    "HIGH_LOUD": ("действия и их описание", False),
    "CONTROL_FIGHT": ("действия и управление механизмами", False),
    "SHOULD_AND_HOUSEWORK": ("домашние обязанности", True),
    "FREE_TIME_ACTIVITY": ("свободное время", False),
    "REFLEXIVE_CRIME_ACTIONS": ("действия и опасные ситуации", True),
    "SHOULD_HOUSEWORK": ("домашние обязанности", True),
    "WANTS_TO_HOUSEWORK_EMOTIONS": ("домашние обязанности и эмоции", True),
    "ROAD_SAFETY_ROUTE": ("безопасность на дороге и направления", False),
    "IMPERATIVE_ROAD_SAFETY": ("безопасность на дороге и направления", True),
    "PLAN_VS_WILL_GARDEN": ("дом и сад", True),
    "DECISION_VS_ARRANGEMENT_ACTIONS": ("действия и опасные ситуации", True),
}

# The selected distractor mentions vocabulary only as a possible cause, so it
# is reported carefully and never treated as a confirmed vocabulary failure.
POSSIBLE_LEXICAL_ERRORS = {
    ("5-6", 1, "BE_HAVE_CONFUSION"): "семья и аксессуары",
}

LEXICAL_QUESTION_IDS = {
    "1-2": {1, 2},
    "3-4": {1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20},
    "5-6": {1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14, 16, 17, 19, 20},
}

# These forms let the fallback report make a natural, bounded inference from
# concrete word errors. Categories that combine several possible causes stay
# out of this mapping and are described only through the exact distractor
# meaning.
LEXICAL_THEME_PHRASES = {
    "еда": "по теме еды",
    "семья": "по теме семьи",
    "одежда": "по теме одежды",
    "дом и предметы дома": "по теме дома и предметов дома",
    "домашние обязанности": "по теме домашних обязанностей",
    "путешествия и транспорт": "по теме путешествий и транспорта",
    "свободное время": "по теме свободного времени",
    "безопасность на дороге и направления": "по теме безопасности на дороге и направлений",
}


SYSTEM_PROMPT = """Ты Miss Ellie, опытный преподаватель английского языка для школьников. Напиши родителю цельное и конкретное заключение по результатам теста. На входе переданы только проверенные программой report_facts. Не меняй диапазон классов, количество правильных ответов, процент, ориентир по уровню и диагностическое значение выбранных ребёнком ответов.

Самые важные данные находятся в selected_mistakes. Каждый элемент описывает именно тот неправильный вариант, который выбрал ребёнок. Поле meaning объясняет, о какой трудности говорит этот выбор. Строй выводы о пробелах прежде всего по meaning и kind. Не подменяй конкретную причину ошибки общей темой вопроса. Если kind равен vocabulary, не называй эту ошибку грамматической. Если kind равен grammar_and_vocabulary, отрази обе стороны ошибки. Возможную лексическую причину не выдавай за доказанный факт.

Отделяй установленный факт от педагогического обобщения. Сначала назови конкретные слова, которые ребёнок перепутал или не понял. Затем можно связать их с vocabulary_category, но только в пределах данных теста. Одна ошибка позволяет сказать осторожно: возможно, ребёнок не помнит часть слов по этой теме. Если в одной категории есть несколько независимых ошибок, можно увереннее сказать, что в словах по этой теме есть пробелы. Не утверждай по одной ошибке, что ребёнок не усвоил всю лексику темы, и не придумывай тему, которой нет в vocabulary_category.

Напиши связный текст без заголовков и списков:
- в первом абзаце поблагодари родителя, один раз назови школьный диапазон и ориентир Pre-A1, A1 или A1+, затем укажи результат из 20 и процент;
- после этого сформулируй один главный вывод: насколько ребёнок усвоил материал и что найденные ошибки означают для дальнейшего обучения;
- назови два-три конкретных навыка из strengths, с которыми ребёнок справился;
- конкретно объясни грамматические ошибки через meaning выбранных ответов;
- отдельно и только один раз оцени лексику. Если vocabulary.error_count равен нулю, достаточно фразы В проверенной лексике явных трудностей не видно. Если ошибки есть, назови конкретные слова или темы из meaning и vocabulary.categories;
- если есть foundation, коротко оцени задания предыдущего этапа. Затем один раз объясни значение результата с учётом класса по grade_context;
- закончи одним коротким абзацем: Это короткий тест с готовыми вариантами ответа. Чтобы точнее определить уровень, я бы ещё посмотрела, как ребёнок говорит по-английски, понимает речь на слух и сам составляет предложения. Для этого предлагаю встретиться на пробном занятии.

Не копируй каждое поле отдельным абзацем и не пересказывай один вывод разными словами. Перед отправкой перечитай весь текст: если два предложения сообщают по сути одно и то же, оставь более конкретное. Общий вывод, оценка лексики, рекомендация обратиться к преподавателю, готовность двигаться дальше и ограничение формата должны появиться только по одному разу.

Сохраняй удачные живые формулировки из данных, если они точны и не дублируются. Не унифицируй текст ради шаблона. Пиши по-человечески, как учитель разговаривает с родителем: ребёнок понимает, различает, правильно использует, усвоил или пока ошибается. Объясняй, что проверяемая конструкция позволяет сказать по-английски.

Не пиши, что уровень официальный или неофициальный, подтверждённый или неподтверждённый. Не оправдывай тест и не повторяй оговорки о словарном запасе. Для 5–6 класса не делай вывод об A2 даже при идеальном результате.

Не давай родителю домашних или методических заданий. Можно предложить разобрать ошибки с преподавателем или встретиться на пробном занятии. Запрещённые выражения: проверялся маршрут; хорошо получились; наиболее нестабильны; фундамент сохранён; база сохранена; оценка серьёзности; проверить речь; обычные действия; темы мешают; темы наслаиваются; могла быть не изучена; дальнейшее усложнение материала; потребуют больших усилий; затрагивают значимую часть; ошибки нельзя считать случайными; несколько важных правил или слов. Не используй кавычки, длинное тире и двойные пробелы.

Пиши ровно столько, сколько нужно для ясного вывода, обычно 170–300 слов. Верни только чистый текст для VK без Markdown, заголовков, списков, ссылок и технических кодов."""


def clean_report_text(text: str) -> str:
    text = re.sub(r"\\+(?=[`*_#\[\]()])", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("—", ":")
    text = re.sub(r"[«»“”„]", "", text)
    text = re.sub(
        r"притяжательн(?:ые|ых|ыми)\s+слова",
        "притяжательные местоимения",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([:;,.!?])", r"\1", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def route_key(summary: dict) -> str:
    value = str(summary.get("route", "1-2")).replace("–", "-")
    for key in ROUTE_RANGES:
        if key in value:
            return key
    return "1-2"


def severity_for(error_count: int, total: int) -> str:
    if error_count <= 0 or total <= 0:
        return "none"
    error_rate = error_count / total
    if error_rate <= 0.15:
        return "small"
    if error_rate <= 0.40:
        return "noticeable"
    return "substantial"


def stronger_severity(first: str, second: str) -> str:
    return first if SEVERITY_ORDER[first] >= SEVERITY_ORDER[second] else second


def topic_label(topic: dict) -> str:
    return TOPIC_LABELS.get(topic["topic"], topic.get("topic_ru") or topic["topic"])


def topic_analysis(summary: dict, key: str) -> tuple[list[dict], list[dict]]:
    strengths = []
    gaps = []
    answers_by_topic = {}
    for answer in summary.get("answers", []):
        answers_by_topic.setdefault(answer.get("topic"), []).append(answer)
    for order, topic in enumerate(summary.get("topics", [])):
        maximum = int(topic.get("max", 0))
        grammar_errors = []
        for answer in answers_by_topic.get(topic["topic"], []):
            if answer.get("correct"):
                continue
            lexical = lexical_error_details(answer, key)
            if lexical and lexical["confirmed"] and not lexical["also_grammar"]:
                continue
            grammar_errors.append(answer)
        errors = len(grammar_errors)
        score = max(0, maximum - errors)
        item = {
            "topic": topic["topic"],
            "label": topic_label(topic),
            "score": score,
            "max": maximum,
            "errors": errors,
            "error_rate": errors / maximum if maximum else 0,
            "status": "mastered" if not errors else "partial" if score else "needs_work",
            "order": order,
        }
        if errors:
            gaps.append(item)
            if score:
                strengths.append(item.copy())
        elif maximum:
            strengths.append(item)
    gaps.sort(key=lambda item: (-item["error_rate"], -item["errors"], item["order"]))
    for item in strengths + gaps:
        item.pop("order", None)
    return strengths[:3], gaps[:6]


def lexical_error_details(answer: dict, key: str) -> dict | None:
    error_code = str(answer.get("error") or "")
    possible_category = POSSIBLE_LEXICAL_ERRORS.get(
        (key, int(answer.get("question_id", 0)), error_code)
    )
    if possible_category:
        return {
            "category": possible_category,
            "confirmed": False,
            "also_grammar": True,
        }
    info = LEXICAL_ERROR_INFO.get(error_code)
    if not info:
        return None
    category, also_grammar = info
    return {
        "category": category,
        "confirmed": True,
        "also_grammar": also_grammar,
    }


def selected_mistake_details(summary: dict, key: str) -> list[dict]:
    foundation_ids = set(FOUNDATION_QUESTION_IDS.get(key, ()))
    mistakes = []
    for answer in summary.get("answers", []):
        if answer.get("correct"):
            continue
        lexical = lexical_error_details(answer, key)
        if lexical and lexical["confirmed"]:
            kind = "grammar_and_vocabulary" if lexical["also_grammar"] else "vocabulary"
        elif lexical:
            kind = "grammar_with_possible_vocabulary"
        else:
            kind = "grammar"
        mistakes.append({
            "question_id": int(answer.get("question_id", 0)),
            "topic": answer.get("topic"),
            "topic_label": TOPIC_LABELS.get(
                answer.get("topic"),
                answer.get("topic_ru") or answer.get("topic"),
            ),
            "selected_text": answer.get("selected_text"),
            "correct_text": answer.get("correct_text"),
            "error": answer.get("error"),
            "meaning": answer.get("meaning"),
            "kind": kind,
            "vocabulary_category": lexical["category"] if lexical else None,
            "belongs_to_previous_stage": int(answer.get("question_id", 0)) in foundation_ids,
        })
    return mistakes


def vocabulary_analysis(summary: dict, key: str) -> dict:
    checked_ids = LEXICAL_QUESTION_IDS[key]
    answers = [
        answer for answer in summary.get("answers", [])
        if int(answer.get("question_id", 0)) in checked_ids
    ]
    confirmed = []
    possible = []
    for answer in answers:
        if answer.get("correct"):
            continue
        details = lexical_error_details(answer, key)
        if not details:
            continue
        item = {
            "question_id": int(answer.get("question_id", 0)),
            "error": answer.get("error"),
            "category": details["category"],
            "also_grammar": details["also_grammar"],
        }
        (confirmed if details["confirmed"] else possible).append(item)

    checked_count = len(answers)
    error_count = len(confirmed)
    severity = severity_for(error_count, checked_count)
    if key == "1-2" and error_count:
        severity = "small" if error_count == 1 else "noticeable"

    categories = list(dict.fromkeys(item["category"] for item in confirmed))
    possible_categories = list(dict.fromkeys(item["category"] for item in possible))
    category_examples = categories[:5]
    possible_examples = possible_categories[:3]
    category_text = ", ".join(category_examples)
    if len(categories) > len(category_examples):
        category_text += " и ещё в нескольких проверенных темах"
    possible_text = ", ".join(possible_examples)
    if len(possible_categories) > len(possible_examples):
        possible_text += " и, возможно, в других темах"
    foundation_ids = set(FOUNDATION_QUESTION_IDS.get(key, ()))
    foundation_errors = sum(item["question_id"] in foundation_ids for item in confirmed)
    foundation_checked = len(checked_ids & foundation_ids)
    foundation_severity = severity_for(foundation_errors, foundation_checked)
    severity = stronger_severity(severity, foundation_severity)

    if not confirmed and not possible:
        message = "В проверенной лексике явных трудностей не видно."
    elif severity == "small":
        message = (
            "В проверенной лексике ребёнок допустил отдельную ошибку. Она относится к теме: "
            + category_text
            + "."
        )
    elif severity == "noticeable":
        message = (
            "В проверенной лексике есть заметные пробелы. Ребёнок ошибся в таких темах: "
            + category_text
            + "."
        )
    else:
        if foundation_severity == "substantial" and key in {"3-4", "5-6"}:
            opening = "Есть существенные пробелы в базовой лексике предыдущих лет. "
        else:
            opening = "В проверенной лексике есть существенные пробелы. "
        message = (
            opening
            + "Ребёнок ошибся в таких темах: "
            + category_text
            + ". Эти ошибки важно учесть перед следующим этапом."
        )
    if possible_categories:
        message += (
            " Некоторые выбранные ответы также могут указывать на трудности в темах: "
            + possible_text
            + ", но этот вариант ответа может объясняться и грамматической ошибкой."
        )

    return {
        "checked_questions": checked_count,
        "confirmed_errors": confirmed,
        "possible_errors": possible,
        "error_count": error_count,
        "severity": severity,
        "categories": categories,
        "possible_categories": possible_categories,
        "foundation_errors": foundation_errors,
        "foundation_severity": foundation_severity,
        "message": message,
    }


def grammar_vocabulary_balance(grammar: dict, vocabulary: dict) -> str:
    grammar_order = SEVERITY_ORDER[grammar["severity"]]
    vocabulary_order = SEVERITY_ORDER[vocabulary["severity"]]
    if grammar_order <= SEVERITY_ORDER["small"] and vocabulary_order >= SEVERITY_ORDER["noticeable"]:
        return "Основную грамматическую базу ребёнок усвоил, но проверенная лексика заметно слабее ожидаемого."
    if grammar["severity"] == "substantial" and vocabulary["severity"] == "substantial":
        return "Есть существенные пробелы и в грамматике, и в базовой лексике."
    if grammar_order >= SEVERITY_ORDER["noticeable"] and vocabulary_order <= SEVERITY_ORDER["small"]:
        return "Основные трудности сейчас связаны с грамматикой. В проверенной лексике результат лучше, но весь словарный запас тест не оценивает."
    return "Грамматику и проверенную лексику ребёнок усвоил примерно на одном уровне."


def grammar_analysis(summary: dict, key: str) -> dict:
    mistakes = []
    for answer in summary.get("answers", []):
        if answer.get("correct"):
            continue
        lexical = lexical_error_details(answer, key)
        if lexical and lexical["confirmed"] and not lexical["also_grammar"]:
            continue
        mistakes.append(answer)
    total = int(summary.get("total_questions", 0))
    severity = severity_for(len(mistakes), total)
    foundation_ids = set(FOUNDATION_QUESTION_IDS.get(key, ()))
    foundation_errors = sum(
        int(answer.get("question_id", 0)) in foundation_ids for answer in mistakes
    )
    correct = int(summary.get("correct_total", 0))
    if (
        key in {"3-4", "5-6"}
        and total
        and correct / total >= 0.50
        and foundation_errors <= 1
        and severity == "substantial"
    ):
        severity = "noticeable"
    if not mistakes:
        message = "В заданиях на грамматику ребёнок не допустил ошибок."
    elif severity == "small":
        message = "Грамматическую основу ребёнок в целом усвоил. В отдельных конструкциях пока есть ошибки."
    elif severity == "noticeable":
        message = "Часть грамматики ребёнок понимает, но в нескольких конструкциях пока ошибается."
    else:
        message = "В грамматике есть существенные пробелы: ребёнок ошибается во многих проверенных конструкциях."
    return {
        "error_count": len(mistakes),
        "mistake_question_ids": [answer["question_id"] for answer in mistakes],
        "foundation_errors": foundation_errors,
        "severity": severity,
        "message": message,
    }


def level_conclusion(key: str, severity: str, foundation: dict | None) -> str:
    level = ROUTE_LEVELS[key]
    foundation_severity = foundation["severity"] if foundation else "none"
    if severity in {"none", "small"} and foundation_severity in {"none", "small"}:
        return f"По результатам этой короткой диагностики знания ребёнка в целом соответствуют ожидаемой базе уровня {level}."
    if severity == "noticeable" and foundation_severity != "substantial":
        return f"Ребёнок усвоил часть ожидаемой базы уровня {level}, но пока не все проверенные темы."
    if key == "5-6":
        if foundation_severity == "substantial":
            return "Задания были рассчитаны примерно на A1+, однако часть базы предыдущего уровня A1 пока не сформирована достаточно уверенно."
        return "Задания были рассчитаны примерно на A1+, но ребёнок пока не усвоил достаточно тем, чтобы уверенно говорить о достижении этого уровня."
    if key == "3-4":
        return "Диагностика была рассчитана на уровень A1, но базовые знания пока не позволяют уверенно говорить, что ребёнок достиг этого уровня."
    return "Диагностика была рассчитана на уровень Pre-A1, но базовые знания пока не позволяют уверенно говорить, что ребёнок достиг этого уровня."


def readiness_analysis(
    key: str,
    overall_severity: str,
    grammar: dict,
    vocabulary: dict,
    foundation: dict | None,
) -> dict:
    severity = stronger_severity(overall_severity, grammar["severity"])
    severity = stronger_severity(severity, vocabulary["severity"])
    if foundation:
        severity = stronger_severity(severity, foundation["severity"])

    if key == "5-6":
        if foundation and foundation["severity"] == "substantial":
            message = (
                "С 7 класса и грамматика, и лексика резко усложняются. Сейчас ребёнку будет трудно "
                "перейти к этому материалу, потому что в заданиях на базу 3–4 класса было много ошибок."
            )
        elif severity in {"noticeable", "substantial"}:
            message = (
                "С 7 класса и грамматика, и лексика резко усложняются. Ребёнок сможет двигаться "
                "дальше, но сначала ему лучше разобрать найденные ошибки с преподавателем."
            )
        else:
            message = (
                "По проверенной грамматике и лексике ребёнок готов двигаться дальше. При этом тест "
                "не проверяет весь словарный запас, который понадобится с 7 класса."
            )
    elif severity in {"none", "small"}:
        message = "По проверенной грамматике и лексике ребёнок готов переходить к следующим темам."
    elif severity == "noticeable":
        message = "Ребёнок сможет двигаться дальше, но сначала ему лучше разобрать найденные ошибки с преподавателем."
    else:
        message = "Переходить к следующему этапу пока будет трудно. Сначала ребёнку лучше разобрать найденные ошибки с преподавателем."
    return {"severity": severity, "message": message}


def conclusion_for(
    score_severity: str,
    effective_severity: str,
    route_range: str,
    grammar: dict | None = None,
    vocabulary: dict | None = None,
) -> str:
    if score_severity == "none":
        return "Ребёнок правильно выполнил все задания и уверенно владеет проверенным материалом."
    if score_severity == "small" and effective_severity == "small":
        return "Ребёнок усвоил почти весь проверенный материал. Отдельные ошибки не выглядят серьёзным пробелом."
    if score_severity == "small" and effective_severity != "small":
        return "Ребёнок справился с большей частью теста, но ошибки затронули материал предыдущего этапа. Поэтому общий высокий балл не отменяет этих пробелов."
    if effective_severity == "noticeable":
        has_grammar_errors = bool(grammar and grammar.get("error_count"))
        has_vocabulary_errors = bool(vocabulary and vocabulary.get("error_count"))
        if has_grammar_errors and has_vocabulary_errors:
            return "Основную часть материала ребёнок понимает. При этом в ответах видны ошибки и в грамматике, и в лексике: некоторые правила ребёнок применяет неверно, а отдельные слова пока путает."
        if has_grammar_errors:
            return "Основную часть материала ребёнок понимает, но в нескольких грамматических темах пока ошибается."
        if has_vocabulary_errors:
            return "Основную часть материала ребёнок понимает, но отдельные слова пока путает."
        return "Основную часть материала ребёнок понимает, но в нескольких заданиях пока ошибается."
    return "Похоже, значительную часть проверенного материала ребёнок пока не усвоил. Ошибки затронули базовые навыки, которые понадобятся на следующем этапе."


def severity_explanation(severity: str) -> str:
    if severity == "none":
        return "По ответам видно, что ребёнок готов переходить к следующим темам."
    if severity == "small":
        return "Ребёнок ошибся только в отдельных заданиях, поэтому сможет продолжать школьную программу без серьёзных трудностей."
    if severity == "noticeable":
        return "Ребёнок ошибается в нескольких темах. Эти знания понадобятся дальше, поэтому ошибки лучше разобрать с преподавателем."
    return "Ребёнок ошибается во многих проверенных темах. Ему будет трудно осваивать следующий материал, пока он не разберётся в этих темах."


def progression_outlook(severity: str) -> str:
    if severity in {"none", "small"}:
        return "Ребёнок может продолжать школьную программу без серьёзных трудностей."
    if severity == "noticeable":
        return "Эти темы лучше разобрать с преподавателем. Иначе в следующих заданиях ребёнок будет ошибаться чаще."
    return "Сначала ребёнку лучше разобрать эти темы с преподавателем. После этого ему будет проще понимать дальнейшую грамматику и лексику."


def grade_context(key: str, correct: int, total: int, foundation_mistakes: int = 0) -> str:
    percent = round((correct / total) * 100) if total else 0
    if key == "1-2":
        if percent >= 85:
            return "Для ребёнка, который учится в 1 классе, это особенно сильный результат: часть тем за 2 класс он мог ещё не проходить. Если ребёнок заканчивает 2 класс, результат показывает, что он усвоил материал этого этапа."
        if percent >= 50:
            return "Если ребёнок сейчас учится в 1 классе, это нормальный промежуточный результат: часть тем за 2 класс он мог ещё не проходить. Если ребёнок заканчивает 2 класс, ошибки уже стоит разобрать с преподавателем."
        return "Если ребёнок сейчас учится в 1 классе, часть ошибок может относиться к темам, которые он ещё не проходил. Если ребёнок заканчивает 2 класс, ему стоит вернуться к темам, в которых он ошибся."
    if key == "3-4":
        if foundation_mistakes >= 2:
            return "Даже если ребёнок сейчас учится в 3 классе, эти ошибки относятся к материалу за 1–2 класс, который он уже проходил. Поэтому сначала стоит уточнить его знания за предыдущий этап."
        if percent >= 85:
            return "Для ребёнка, который учится в 3 классе, это особенно сильный результат: Past Simple и часть тем за 4 класс он мог ещё не проходить. Если ребёнок заканчивает 4 класс, результат показывает, что он усвоил материал этого этапа."
        if percent >= 50:
            return "Если ребёнок сейчас учится в 3 классе, это вполне хороший промежуточный результат: Past Simple и часть тем за 4 класс он мог ещё не проходить. Если ребёнок заканчивает 4 класс, ошибки уже стоит разобрать с преподавателем."
        return "Если ребёнок сейчас учится в 3 классе, учитывайте, что Past Simple и часть тем за 4 класс он мог ещё не проходить. Если ребёнок заканчивает 4 класс, ему стоит вернуться к темам, в которых он ошибся."
    if foundation_mistakes >= 4:
        return "Даже если ребёнок сейчас учится в 5 классе, эти ошибки относятся к материалу за 3–4 класс, который он уже проходил. С 7 класса грамматика и лексика станут сложнее, поэтому сначала эти пробелы лучше разобрать с преподавателем."
    if foundation_mistakes >= 2:
        return "Даже если ребёнок учится в 5 классе, эти ошибки относятся к материалу за 3–4 класс, который он уже проходил. Если он заканчивает 6 класс, пробелы лучше разобрать с преподавателем до перехода в 7 класс, когда грамматика и лексика станут сложнее."
    if percent >= 85:
        return "Для ребёнка, который учится в 5 классе, это особенно сильный результат: часть тем за 6 класс он мог ещё не проходить. Если ребёнок заканчивает 6 класс, результат показывает, что он усвоил материал этого этапа."
    if percent >= 50:
        return "Если ребёнок сейчас учится в 5 классе, это вполне хороший промежуточный результат: часть тем за 6 класс он мог ещё не проходить. Если ребёнок заканчивает 6 класс, ошибки лучше разобрать с преподавателем до перехода в 7 класс, когда грамматика и лексика станут сложнее."
    return "Если ребёнок сейчас учится в 5 классе, часть ошибок может относиться к темам за 6 класс, которые он ещё не проходил. Если ребёнок заканчивает 6 класс, эти пробелы лучше разобрать с преподавателем до перехода в 7 класс."


def foundation_analysis(summary: dict, key: str) -> dict | None:
    question_ids = FOUNDATION_QUESTION_IDS.get(key)
    if not question_ids:
        return None
    relevant = [
        answer for answer in summary.get("answers", [])
        if int(answer.get("question_id", 0)) in question_ids
    ]
    mistakes = [answer for answer in relevant if not answer.get("correct")]
    severity = severity_for(len(mistakes), len(question_ids))
    gap_topics = []
    for answer in mistakes:
        label = TOPIC_LABELS.get(answer.get("topic"), answer.get("topic_ru") or answer.get("topic"))
        if label and label not in gap_topics:
            gap_topics.append(label)

    if key == "3-4":
        if not mistakes:
            message = "В первых четырёх заданиях ребёнок показал, что усвоил материал за 1–2 класс."
        elif severity == "noticeable":
            message = "В первых четырёх заданиях ребёнок допустил одну ошибку. Значит, материал за 1–2 класс он в основном усвоил, но в одной теме пока ошибается."
        else:
            message = "В первых четырёх заданиях ребёнок допустил несколько ошибок. Значит, часть материала за 1–2 класс он пока не усвоил. Полезно пройти тест за 1–2 класс, чтобы точнее увидеть, какие темы нужно разобрать с преподавателем."
    else:
        if not mistakes:
            message = "В первых девяти заданиях ребёнок показал, что усвоил материал за 3–4 класс."
        elif severity == "small":
            message = "В первых девяти заданиях ребёнок допустил одну ошибку. Значит, материал за 3–4 класс он в основном усвоил, но в одной теме пока ошибается."
        elif severity == "noticeable":
            message = "В первых девяти заданиях ребёнок допустил несколько ошибок. Значит, часть материала за 3–4 класс он пока не усвоил. С 7 класса ему будет труднее, если он не разберёт эти темы с преподавателем."
        else:
            message = "В первых девяти заданиях ребёнок допустил много ошибок. Значит, он пока не усвоил часть материала за 3–4 класс. Полезно пройти тест за 3–4 класс, чтобы точнее увидеть, какие темы нужно разобрать с преподавателем до 7 класса."

    return {
        "question_ids": list(question_ids),
        "questions_checked": len(question_ids),
        "mistakes": len(mistakes),
        "mistake_question_ids": [answer["question_id"] for answer in mistakes],
        "severity": severity,
        "severity_label": SEVERITY_LABELS[severity],
        "gap_topics": gap_topics,
        "message": message,
    }


def build_report_facts(summary: dict) -> dict:
    key = route_key(summary)
    total = int(summary.get("total_questions", 0))
    correct = int(summary.get("correct_total", 0))
    mistakes = max(0, total - correct)
    score_severity = severity_for(mistakes, total)
    foundation = foundation_analysis(summary, key)
    effective_severity = score_severity
    if foundation and foundation["mistakes"]:
        effective_severity = stronger_severity(effective_severity, foundation["severity"])
    # A 50–60% result can be a good intermediate result for a child in the
    # younger class of a two-year route. If the earlier material is secure,
    # do not describe unpassed upper-class topics as a serious failure.
    if (
        key in {"3-4", "5-6"}
        and total
        and correct / total >= 0.50
        and (not foundation or foundation["mistakes"] <= 1)
        and effective_severity == "substantial"
    ):
        effective_severity = "noticeable"
    grammar = grammar_analysis(summary, key)
    vocabulary = vocabulary_analysis(summary, key)
    strengths, gaps = topic_analysis(summary, key)
    selected_mistakes = selected_mistake_details(summary, key)
    readiness = readiness_analysis(
        key,
        effective_severity,
        grammar,
        vocabulary,
        foundation,
    )
    return {
        "route_key": key,
        "route_range": ROUTE_RANGES[key],
        "target_level": ROUTE_LEVELS[key],
        "route_name": summary.get("route", ROUTE_RANGES[key]),
        "correct_total": correct,
        "total_questions": total,
        "mistakes_total": mistakes,
        "score_percent": round((correct / total) * 100) if total else 0,
        "score_severity": score_severity,
        "severity": effective_severity,
        "severity_label": SEVERITY_LABELS[effective_severity],
        "overall_conclusion": conclusion_for(
            score_severity,
            effective_severity,
            ROUTE_RANGES[key],
            grammar,
            vocabulary,
        ),
        "severity_explanation": severity_explanation(effective_severity),
        "strengths": strengths,
        "gaps": gaps,
        "foundation": foundation,
        "grammar": grammar,
        "vocabulary": vocabulary,
        "selected_mistakes": selected_mistakes,
        "grammar_vocabulary_balance": grammar_vocabulary_balance(grammar, vocabulary),
        "level_conclusion": level_conclusion(key, readiness["severity"], foundation),
        "grade_context": grade_context(
            key,
            correct,
            total,
            foundation["mistakes"] if foundation else 0,
        ),
        "progression_outlook": progression_outlook(readiness["severity"]),
        "readiness": readiness,
    }


def format_topics(items: list[dict]) -> str:
    return "; ".join(item["label"] for item in items)


def format_count(number: int, one: str, few: str, many: str) -> str:
    if number % 10 == 1 and number % 100 != 11:
        return f"{number} {one}"
    if number % 10 in {2, 3, 4} and number % 100 not in {12, 13, 14}:
        return f"{number} {few}"
    return f"{number} {many}"


def meaning_clause(meaning: str | None) -> str:
    text = str(meaning or "").strip().rstrip(".;")
    exact_replacements = {
        "не образует сравнительную степень": "пока неправильно образует сравнительную степень прилагательных",
        "после did оставляет форму Past Simple": "после did оставляет глагол в прошедшей форме вместо начальной",
        "забывает -s в 3-м лице": "забывает окончание -s в 3-м лице Present Simple",
    }
    if text in exact_replacements:
        return exact_replacements[text]
    past_form = re.match(
        r"не знает неправильную форму\s+([a-z]+)\s*→\s*([a-z]+)",
        text,
        re.IGNORECASE,
    )
    if past_form:
        return f"не помнит, что в Past Simple глагол {past_form.group(1)} меняется на {past_form.group(2)}"
    text = text.replace("→", "/")
    text = re.sub(
        r"\b([a-z]+)\s*/\s*([a-z]+)\s*/\s*([a-z]+)\b",
        r"\1, \2 и \3",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s*/\s*", " и ", text)
    text = text.replace("не знает значение слов", "не помнит значения слов")
    lower = text.lower()
    replacements = (
        ("грамматика правильная, но ребёнок ", "правильно выбирает грамматическую форму, но "),
        ("грамматика правильная, но ", "правильно выбирает грамматическую форму, но "),
        ("грамматическую форму строит правильно, но ", "правильно строит грамматическую форму, но "),
        ("форму ответа знает, но ", "знает форму ответа, но "),
    )
    for source, replacement in replacements:
        if lower.startswith(source):
            return replacement + text[len(source):]
    match = re.match(r"грамматически\s+(.+?)\s+выбран[оа]\s+правильно,\s+но\s+(?:ребёнок\s+)?(.+)", text, re.IGNORECASE)
    if match:
        return f"правильно выбирает {match.group(1)}, но {match.group(2)}"
    if lower.startswith("после did ребёнок "):
        return "после did " + text[len("после did ребёнок "):]
    if lower.startswith("после did "):
        return "после did " + text[len("после did "):]
    return text[:1].lower() + text[1:] if text else "ошибается в этом задании"


def lexical_clause(detail: dict) -> str:
    clause = meaning_clause(detail.get("meaning"))
    if detail.get("kind") == "vocabulary" and ", но " in clause:
        opening, remainder = clause.split(", но ", 1)
        if any(word in opening for word in ("граммат", "форм", "конструкц")):
            clause = remainder
    return clause


def joined_clauses(clauses: list[str], limit: int = 6) -> str:
    unique = []
    seen = set()
    for clause in clauses:
        normalized = re.sub(r"\W+", " ", clause.lower()).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(clause)
    return "; ".join(unique[:limit])


def strengths_paragraph(facts: dict) -> str | None:
    skills = []
    for item in facts["strengths"]:
        skill = TOPIC_SKILLS.get(item["topic"])
        if skill and skill not in skills:
            skills.append(skill)
    if not skills:
        return None
    return "По правильным ответам видно, что ребёнок " + joined_clauses(skills, 3) + "."


def grammar_paragraph(facts: dict) -> str:
    grammar_details = [
        detail for detail in facts["selected_mistakes"]
        if detail["kind"] != "vocabulary"
    ]
    if not grammar_details:
        return "В грамматике ребёнок правильно выполнил все задания."
    clauses = [meaning_clause(detail.get("meaning")) for detail in grammar_details]
    return "В грамматике ребёнок " + joined_clauses(clauses) + "."


def vocabulary_paragraph(facts: dict) -> str:
    confirmed = [
        detail for detail in facts["selected_mistakes"]
        if detail["kind"] in {"vocabulary", "grammar_and_vocabulary"}
    ]
    possible = [
        detail for detail in facts["selected_mistakes"]
        if detail["kind"] == "grammar_with_possible_vocabulary"
    ]
    if not confirmed:
        if possible:
            categories = ", ".join(dict.fromkeys(
                detail["vocabulary_category"] for detail in possible
                if detail.get("vocabulary_category")
            ))
            return (
                "В проверенной лексике явных трудностей не видно. Один выбранный ответ может "
                f"указывать на трудность в теме {categories}, но он может объясняться и грамматической ошибкой."
            )
        return "В проверенной лексике явных трудностей не видно."

    pure_lexical = [detail for detail in confirmed if detail["kind"] == "vocabulary"]
    clauses = [lexical_clause(detail) for detail in pure_lexical]
    categories = list(dict.fromkeys(
        detail["vocabulary_category"] for detail in confirmed
        if detail.get("vocabulary_category")
    ))
    if clauses:
        paragraph = "В лексике ребёнок " + clauses[0] + "."
        if len(clauses) > 1:
            paragraph += " Кроме того, ребёнок " + joined_clauses(clauses[1:], 3) + "."
        mixed_categories = [
            detail["vocabulary_category"] for detail in confirmed
            if detail["kind"] == "grammar_and_vocabulary"
            and detail.get("vocabulary_category")
        ]
        mixed_categories = list(dict.fromkeys(mixed_categories))
        if mixed_categories:
            paragraph += " Кроме того, часть ошибок связана со словами по темам: " + ", ".join(mixed_categories) + "."
        category_counts = {}
        for detail in confirmed:
            category = detail.get("vocabulary_category")
            if category in LEXICAL_THEME_PHRASES:
                category_counts[category] = category_counts.get(category, 0) + 1
        for category, count in category_counts.items():
            theme = LEXICAL_THEME_PHRASES[category]
            if count == 1:
                paragraph += f" Возможно, ребёнок не помнит и другие слова {theme}."
            else:
                paragraph += f" Несколько ошибок показывают, что ребёнок не помнит часть слов {theme}."
        return paragraph
    return "В лексике трудности относятся к темам: " + ", ".join(categories) + "."


def foundation_paragraph(facts: dict) -> str | None:
    foundation = facts.get("foundation")
    if not foundation:
        return None
    first_questions = "первых четырёх" if facts["route_key"] == "3-4" else "первых девяти"
    previous_range = "1–2 класс" if facts["route_key"] == "3-4" else "3–4 класс"
    mistakes = foundation["mistakes"]
    if not mistakes:
        return (
            f"В {first_questions} заданиях, проверяющих базу за {previous_range}, ошибок не было. "
            "Материал предыдущего этапа ребёнок усвоил."
        )
    count = format_count(mistakes, "ошибка", "ошибки", "ошибок")
    if mistakes == 1:
        return (
            f"В {first_questions} заданиях, проверяющих базу за {previous_range}, была одна ошибка. "
            "В целом материал предыдущего этапа ребёнок усвоил."
        )
    return (
        f"В {first_questions} заданиях, проверяющих базу за {previous_range}, было {count}. "
        "Значит, часть материала предыдущего этапа ребёнок пока не усвоил."
    )


def report_facts_for_ai(facts: dict) -> dict:
    foundation = facts.get("foundation")
    return {
        "route_key": facts["route_key"],
        "route_range": facts["route_range"],
        "target_level": facts["target_level"],
        "correct_total": facts["correct_total"],
        "total_questions": facts["total_questions"],
        "score_percent": facts["score_percent"],
        "overall_assessment": facts["overall_conclusion"],
        "severity": facts["severity"],
        "strengths": facts["strengths"],
        "grammar": {
            "severity": facts["grammar"]["severity"],
            "error_count": facts["grammar"]["error_count"],
            "mistake_question_ids": facts["grammar"]["mistake_question_ids"],
        },
        "vocabulary": {
            "severity": facts["vocabulary"]["severity"],
            "error_count": facts["vocabulary"]["error_count"],
            "categories": facts["vocabulary"]["categories"],
            "possible_categories": facts["vocabulary"]["possible_categories"],
        },
        "foundation": None if not foundation else {
            "questions_checked": foundation["questions_checked"],
            "mistakes": foundation["mistakes"],
            "mistake_question_ids": foundation["mistake_question_ids"],
            "severity": foundation["severity"],
        },
        "grade_context": facts["grade_context"],
        "readiness": facts["readiness"]["severity"],
        "selected_mistakes": facts["selected_mistakes"],
    }


def fallback_report(summary: dict) -> str:
    facts = build_report_facts(summary)
    parts = [
        (
            "Спасибо, что нашли время пройти тест. "
            f"Мы проверили, как ребёнок усвоил материал за {facts['route_range']} "
            f"(ориентир: {facts['target_level']}). "
            f"Ребёнок правильно ответил на {facts['correct_total']} из {facts['total_questions']} вопросов "
            f"({facts['score_percent']}%)."
        ),
        facts["overall_conclusion"],
    ]

    strengths = strengths_paragraph(facts)
    if strengths:
        parts.append(strengths)
    parts.extend([grammar_paragraph(facts), vocabulary_paragraph(facts)])

    foundation = foundation_paragraph(facts)
    if foundation:
        parts.append(foundation)

    parts.extend([
        facts["grade_context"],
        (
            "Это короткий тест с готовыми вариантами ответа. Чтобы точнее определить уровень, "
            "я бы ещё посмотрела, как ребёнок говорит по-английски, понимает речь на слух "
            "и сам составляет предложения. Для этого предлагаю встретиться на пробном занятии."
        ),
    ])
    return clean_report_text("\n\n".join(parts))


def teacher_stub(summary: dict) -> str:
    return clean_report_text(
        "Это демонстрационный отчёт для владельца бота: платный AI-вызов отключён для вашего VK ID.\n\n"
        + fallback_report(summary)
    )


def semantic_tokens(sentence: str) -> set[str]:
    normalized = sentence.lower().replace("ё", "е")
    for pattern, replacement in (
        (r"ошиб\w*", "ошибка"),
        (r"тем\w*", "тема"),
        (r"усво\w*", "усвоить"),
        (r"понима\w*", "понимать"),
        (r"пробел\w*", "пробел"),
        (r"провер\w*", "проверка"),
    ):
        normalized = re.sub(pattern, replacement, normalized)
    stop_words = {
        "ребенок", "ребенка", "ребенку", "ребёнок", "ребёнка", "ребёнку",
        "это", "есть", "пока", "уже", "также", "только", "часть",
        "из", "по", "в", "на", "и", "но", "а", "что", "как", "он", "она",
    }
    return {
        word for word in re.findall(r"[a-zа-я0-9+-]+", normalized)
        if len(word) > 2 and word not in stop_words
    }


def has_semantic_repetition(report: str) -> bool:
    sentences = [
        sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", report.replace("\n", " "))
        if sentence.strip()
    ]
    token_sets = [semantic_tokens(sentence) for sentence in sentences]
    for index, first in enumerate(token_sets):
        if len(first) < 3:
            continue
        for second in token_sets[index + 1:]:
            if len(second) < 3:
                continue
            overlap = len(first & second)
            if first == second or (overlap >= 4 and overlap / min(len(first), len(second)) >= 0.85):
                return True
    return False


def report_is_usable(report: str, facts: dict) -> bool:
    lower = report.lower()
    forbidden_patterns = (
        r"\bпозанимайтесь\b",
        r"\bпопросите\s+(?:ребёнка|ребенка)\b",
        r"\bтренируйте\b",
        r"\bзанимайтесь\s+(?:дома|карточками)\b",
        r"\bповторяйте\s+дома\b",
        r"\bделайте\s+упражнения\b",
        r"\bпритяжательные\s+слова\b",
        r"\bпроверялся\s+маршрут\b",
        r"\bхорошо\s+получились\b",
        r"\bнаиболее\s+нестабильны\b",
        r"\bнестабильн",
        r"\bфундамент\s+сохран",
        r"\bбаза\s+сохран",
        r"\bоценка\s+серьёзности\b",
        r"\bпровер(?:ить|ила)\s+речь\b",
        r"\bобычные\s+действия\b",
        r"\bтемы\s+(?:мешают|наслаиваются)\b",
        r"\bмогла\s+(?:ещё\s+)?не\s+изучаться\b",
        r"\bдальнейшее\s+усложнение\b",
        r"\bпотребуют\s+.*\bусилий\b",
        r"\bзатрагивают\s+значимую\s+часть\b",
        r"\bошибки\s+(?:уже\s+)?нельзя\s+считать\s+случайными\b",
        r"\bнесколько\s+важных\s+правил\s+или\s+слов\b",
        r"\bне\s+официальн",
        r"\bофициальн(?:о|ый|ого|ым)?\s+подтверж",
    )
    gap_anchors = [
        re.split(r"\s*[:—]\s*", item["label"], maxsplit=1)[0].lower()
        for item in facts["gaps"]
    ]
    detail_matches = [
        len(semantic_tokens(str(detail.get("meaning") or "")) & semantic_tokens(report)) >= 2
        for detail in facts["selected_mistakes"]
    ]
    evidence_needed = min(len(detail_matches), 6)
    has_gap = (
        not facts["mistakes_total"]
        or sum(detail_matches) >= evidence_needed
        or (
            any(anchor in lower for anchor in gap_anchors)
            and sum(detail_matches) >= max(1, evidence_needed - 1)
        )
    )
    vocabulary_anchors = [
        category.lower() for category in facts["vocabulary"]["categories"]
    ]
    has_vocabulary_examples = (
        not vocabulary_anchors
        or any(anchor in lower for anchor in vocabulary_anchors)
        or any(
            len(semantic_tokens(str(detail.get("meaning") or "")) & semantic_tokens(report)) >= 2
            for detail in facts["selected_mistakes"]
            if detail["kind"] in {"vocabulary", "grammar_and_vocabulary"}
        )
    )
    foundation = facts.get("foundation")
    if not foundation:
        has_foundation = True
    elif facts["route_key"] == "3-4":
        has_foundation = "первых четырёх" in lower and "1–2 класс" in report
    else:
        has_foundation = "первых девяти" in lower and "3–4 класс" in report
    return (
        bool(report)
        and len(report) <= MAX_REPORT_CHARS
        and facts["route_range"] in report
        and "спасибо, что нашли время пройти тест" in lower
        and "мы проверили, как ребёнок усвоил материал" in lower
        and facts["target_level"].lower() in lower
        and "ориентир" in lower
        and f"{facts['correct_total']} из {facts['total_questions']}" in report
        and f"{facts['score_percent']}%" in report
        and "граммат" in lower
        and ("словарн" in lower or "лексик" in lower)
        and has_vocabulary_examples
        and has_gap
        and has_foundation
        and "короткий тест с готовыми вариантами ответа" in lower
        and "понимает речь на слух" in lower
        and "сам составляет предложения" in lower
        and "пробном занятии" in lower
        and lower.count("короткий тест с готовыми вариантами ответа") == 1
        and ("учится в 1 классе" in lower or "учится в 3 классе" in lower or "учится в 5 классе" in lower)
        and not (facts["route_key"] == "5-6" and re.search(r"\bA2\b", report, re.IGNORECASE))
        and not any(re.search(pattern, lower) for pattern in forbidden_patterns)
        and "—" not in report
        and not re.search(r"[«»“”„]", report)
        and not re.search(r"[^\n] {2,}[^\n]", report)
        and not re.search(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", report)
        and not has_semantic_repetition(report)
    )


def generate_parent_report(user_id: int, summary: dict) -> str:
    if user_id == TEACHER_VK_ID:
        return teacher_stub(summary)

    api_url = os.getenv("AI_API_URL", "").strip()
    api_key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "").strip()
    if not api_url or not api_key or not model:
        print("AI_REPORT_FALLBACK: configuration_missing")
        return fallback_report(summary)

    facts = build_report_facts(summary)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"report_facts": report_facts_for_ai(facts)},
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        report = clean_report_text(data["choices"][0]["message"]["content"])
        if not report_is_usable(report, facts):
            print("AI_REPORT_FALLBACK: response_validation")
            return fallback_report(summary)
        print("AI_REPORT_SUCCESS")
        return report
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"AI_REPORT_FALLBACK: HTTP_{status}")
        return fallback_report(summary)
    except Exception as exc:
        print(f"AI_REPORT_FALLBACK: {type(exc).__name__}")
        return fallback_report(summary)
