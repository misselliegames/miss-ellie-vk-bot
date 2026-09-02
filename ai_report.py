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
    "BE_HAVE_APPEARANCE": "to be и have got / has got: рассказ о состоянии и внешности",
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
    "FEW_LITTLE": "few / a few и little / a little: количество и достаточность",
    "REFLEXIVE_PRONOUNS": "возвратные местоимения himself / herself",
    "HAVE_TO_HAS_TO": "have to / has to: обязанность и выбор формы по подлежащему",
    "MUSTNT_DONT_HAVE_TO_NEEDNT": "mustn’t, don’t have to и needn’t: запрет и отсутствие необходимости",
    "SHOULD": "глагол should: совет и форма глагола без to",
    "WANT_TO_LET": "конструкции want to do и let somebody do",
    "FUTURE_ARRANGEMENT": "Present Continuous для договорённости на будущее",
    "FUTURE_PLANS": "be going to для заранее существующего плана",
    "FUTURE_DECISIONS": "will для решения, принятого в момент речи",
}

# Only errors whose distractor explicitly diagnoses a lexical difficulty are
# counted as vocabulary evidence. A normal grammar error must not be silently
# reinterpreted as a vocabulary gap.
LEXICAL_ERROR_INFO = {
    "NUM_RECOGNITION": ("числительные", False),
    "FAMILY_DAUGHTER_HUSBAND": ("семья", False),
    "FEELINGS_APPEARANCE": ("чувства и внешность", False),
    "DOLL_LAMP": ("игрушки и предметы дома", False),
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
}

# The selected distractor mentions vocabulary only as a possible cause, so it
# is reported carefully and never treated as a confirmed vocabulary failure.
POSSIBLE_LEXICAL_ERRORS = {
    ("5-6", 1, "BE_HAVE_CONFUSION"): "семья и аксессуары",
}

LEXICAL_QUESTION_IDS = {
    "1-2": {1, 2},
    "3-4": {1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20},
    "5-6": {1, 2, 3, 4, 5, 6, 8, 9, 10, 14, 16},
}


SYSTEM_PROMPT = """Ты Miss Ellie, опытный преподаватель английского языка для школьников. Напиши родителю индивидуальный отчёт по короткому тесту. На входе переданы diagnostic_summary и report_facts. Эти данные вычислены программно и обязательны: не меняй диапазон классов, количество правильных ответов, оценку ошибок, ориентир по уровню, выводы о грамматике, лексике и материале предыдущего этапа.

Пиши по-человечески, как учитель разговаривает с родителем. Перед отправкой найди канцеляризмы, страдательный залог и шаблонные фразы нейросетей, затем замени их простыми словами и действительным залогом. Главный герой каждого предложения ребёнок: ребёнок понимает, различает, правильно использует, прошёл тему, усвоил её или пока в ней ошибается.

Структура текста:
1. Начни с благодарности: Спасибо, что нашли время пройти тест.
2. Напиши, для какого диапазона рассчитан тест, и назови ориентир из report_facts.target_level: Pre-A1, A1 или A1+. Обязательно уточни, что это ориентировочный результат короткой диагностики, а не официальный подтверждённый уровень. Не используй техническое слово маршрут в тексте для родителя.
3. Укажи число правильных ответов и передай report_facts.level_conclusion. Не присваивай ребёнку уровень маршрута при слабом результате. Для 5–6 класса никогда не делай вывод об A2, даже при идеальном результате.
4. Передай общий вывод из report_facts.overall_conclusion и оценку из report_facts.severity_label.
5. Отдельным абзацем передай report_facts.grammar.message. Это вывод только о грамматике.
6. Отдельным абзацем передай report_facts.vocabulary.message. Это вывод только о проверенной лексике. Назови vocabulary.categories, если они есть. Не говори, что весь словарный запас проверен. Если vocabulary.possible_categories не пуст, скажи, что выбранные ответы могут указывать на эти трудности, но не доказывают их. Затем передай report_facts.grammar_vocabulary_balance.
7. Коротко скажи, что ребёнок понимает и правильно использует. Не пиши Хорошо получились темы.
8. Назови темы из report_facts.gaps и скажи, где ребёнок ошибается. Не называй темы нестабильными и не пиши, что темы чему-то мешают.
9. Если есть report_facts.foundation, обязательно передай foundation.message.
10. Обязательно передай report_facts.grade_context. Бот не знает точный класс ребёнка, поэтому нельзя одинаково оценивать третьеклассника и четвероклассника, а также пятиклассника и шестиклассника. Пиши только в действительном залоге: ребёнок мог ещё не проходить тему.
11. Заверши выводом из report_facts.readiness.message. Он отвечает на вопрос, потянет ли ребёнок программу дальше, и учитывает и грамматику, и проверенную лексику.
12. В конце напиши простыми словами: Это короткий тест с готовыми вариантами ответа. Чтобы точнее определить уровень, я бы ещё посмотрела, как ребёнок говорит по-английски, понимает речь на слух и сам составляет предложения.

Не давай родителю методических или домашних заданий. Не предлагай родителю заниматься с ребёнком по карточкам, просить его повторять правила, тренировать темы дома или делать упражнения. Родитель не должен становиться преподавателем. Допустимо сказать, что ребёнку стоит разобрать ошибки с преподавателем или пройти более подробную диагностику.

Запрещённые выражения: проверялся маршрут; хорошо получились; наиболее нестабильны; фундамент сохранён; база сохранена; оценка серьёзности; проверить речь; обычные действия; темы мешают; темы наслаиваются; могла быть не изучена; дальнейшее усложнение материала; потребуют больших усилий; затрагивают значимую часть. Не используй кавычки, длинное тире и двойные пробелы. Не нагнетай и не сглаживай результат.

Пиши естественным русским языком, 220–330 слов, обычными абзацами. Верни только чистый текст для VK без Markdown, заголовков, списков, ссылок и технических кодов."""


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
            "order": order,
        }
        if errors:
            gaps.append(item)
        elif maximum:
            strengths.append(item)
    gaps.sort(key=lambda item: (-item["error_rate"], -item["errors"], item["order"]))
    for item in strengths + gaps:
        item.pop("order", None)
    return strengths[:2], gaps[:4]


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
        message = (
            "В проверенной лексике явных трудностей не видно. Но задания затронули только часть "
            "словарного запаса, поэтому по этому тесту нельзя оценить его полностью."
        )
    elif severity == "small":
        message = (
            "В проверенной лексике ребёнок допустил отдельную ошибку. Она относится к теме: "
            + category_text
            + ". Тест проверяет только часть словарного запаса."
        )
    elif severity == "noticeable":
        message = (
            "В проверенной лексике есть заметные пробелы. Ребёнок ошибся в таких темах: "
            + category_text
            + ". При этом тест проверяет только часть словарного запаса."
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
            + ". Тест проверяет только часть словарного запаса, но эти ошибки важно учесть перед следующим этапом."
        )
    if possible_categories:
        message += (
            " Некоторые выбранные ответы также могут указывать на трудности в темах: "
            + possible_text
            + ", но одного теста недостаточно, чтобы утверждать это уверенно."
        )
    if key == "5-6":
        message += (
            " Вопросы 10–20 в основном проверяют грамматику, поэтому они не подтверждают весь "
            "словарный запас уровня A1+."
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


def conclusion_for(score_severity: str, effective_severity: str, route_range: str) -> str:
    if score_severity == "none":
        return "Ребёнок правильно выполнил все задания и показал, что понимает проверенные темы. По заданиям ошибок нет."
    if score_severity == "small" and effective_severity == "small":
        return "Ребёнок усвоил почти все проверенные темы. Есть отдельные ошибки."
    if score_severity == "small" and effective_severity != "small":
        return f"Ребёнок справился с большей частью теста, но ошибся в материале предыдущего этапа. {SEVERITY_LABELS[effective_severity].capitalize()}."
    if effective_severity == "noticeable":
        return "Ребёнок понимает многие проверенные темы, но пока ошибается в нескольких из них. Есть ошибки в нескольких темах."
    return "Ребёнок пока не усвоил часть проверенного материала. Ошибок много, в том числе в важных темах."


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
        return "Даже если ребёнок сейчас учится в 5 классе, эти ошибки относятся к материалу за 3–4 класс, который он уже проходил. Поэтому сначала стоит уточнить его знания за предыдущий этап."
    if percent >= 85:
        return "Для ребёнка, который учится в 5 классе, это особенно сильный результат: часть тем за 6 класс он мог ещё не проходить. Если ребёнок заканчивает 6 класс, результат показывает, что он усвоил материал этого этапа."
    if percent >= 50:
        return "Если ребёнок сейчас учится в 5 классе, это вполне хороший промежуточный результат: часть тем за 6 класс он мог ещё не проходить. Если ребёнок заканчивает 6 класс, ошибки уже стоит разобрать с преподавателем."
    return "Если ребёнок сейчас учится в 5 классе, часть ошибок может относиться к темам за 6 класс, которые он ещё не проходил. Если ребёнок заканчивает 6 класс, ему стоит вернуться к темам, в которых он ошибся."


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
        "overall_conclusion": conclusion_for(score_severity, effective_severity, ROUTE_RANGES[key]),
        "severity_explanation": severity_explanation(effective_severity),
        "strengths": strengths,
        "gaps": gaps,
        "foundation": foundation,
        "grammar": grammar,
        "vocabulary": vocabulary,
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


def fallback_report(summary: dict) -> str:
    facts = build_report_facts(summary)
    parts = [
        (
            "Спасибо, что нашли время пройти тест. "
            f"Мы проверили, как ребёнок усвоил материал за {facts['route_range']}. "
            f"Диагностика рассчитана примерно на уровень {facts['target_level']}. Это не официальный "
            "подтверждённый уровень, а предварительная оценка по короткой диагностике. "
            f"Ребёнок правильно ответил на {facts['correct_total']} из {facts['total_questions']} вопросов "
            f"({facts['score_percent']}%)."
        ),
        (
            f"{facts['level_conclusion']} {facts['overall_conclusion']} {facts['severity_explanation']}"
        ),
        facts["grammar"]["message"],
        facts["vocabulary"]["message"] + " " + facts["grammar_vocabulary_balance"],
    ]

    if facts["strengths"]:
        parts.append("Ребёнок понимает эти темы: " + format_topics(facts["strengths"]) + ".")
    else:
        parts.append("Ребёнок допустил хотя бы одну ошибку в каждой проверенной теме.")

    if facts["gaps"]:
        parts.append("Ребёнок пока ошибается в таких темах: " + format_topics(facts["gaps"]) + ".")
    elif not facts["mistakes_total"]:
        parts.append("В заданиях с выбором ответа ребёнок не допустил ошибок.")

    if facts["foundation"]:
        parts.append(facts["foundation"]["message"])

    parts.extend([
        facts["grade_context"],
        facts["readiness"]["message"],
        (
            "Это короткий тест с готовыми вариантами ответа. Чтобы точнее определить уровень, "
            "я бы ещё посмотрела, как ребёнок говорит по-английски, понимает речь на слух "
            "и сам составляет предложения."
        ),
    ])
    return clean_report_text("\n\n".join(parts))


def teacher_stub(summary: dict) -> str:
    return clean_report_text(
        "Это демонстрационный отчёт для владельца бота: платный AI-вызов отключён для вашего VK ID.\n\n"
        + fallback_report(summary)
    )


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
    )
    has_severity = any(
        label in lower
        for label in SEVERITY_LABELS.values()
    )
    gap_anchors = [
        item["label"].split(" —", 1)[0].lower()
        for item in facts["gaps"]
    ]
    has_gap = not gap_anchors or any(anchor in lower for anchor in gap_anchors)
    vocabulary_anchors = [
        category.lower() for category in facts["vocabulary"]["categories"]
    ]
    has_vocabulary_examples = (
        not vocabulary_anchors
        or any(anchor in lower for anchor in vocabulary_anchors)
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
        and ("ориентир" in lower or "предварительн" in lower)
        and "граммат" in lower
        and ("словарн" in lower or "лексик" in lower)
        and has_vocabulary_examples
        and has_severity
        and has_gap
        and has_foundation
        and "короткий тест с готовыми вариантами ответа" in lower
        and "часть словарного запаса" in lower
        and "понимает речь на слух" in lower
        and "сам составляет предложения" in lower
        and ("учится в 1 классе" in lower or "учится в 3 классе" in lower or "учится в 5 классе" in lower)
        and not (facts["route_key"] == "5-6" and re.search(r"\bA2\b", report, re.IGNORECASE))
        and not any(re.search(pattern, lower) for pattern in forbidden_patterns)
        and "—" not in report
        and not re.search(r"[«»“”„]", report)
        and not re.search(r"[^\n] {2,}[^\n]", report)
        and not re.search(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", report)
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
                    {"diagnostic_summary": summary, "report_facts": facts},
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
