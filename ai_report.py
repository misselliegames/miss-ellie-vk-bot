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


SYSTEM_PROMPT = """Ты Miss Ellie, опытный преподаватель английского языка для школьников. Напиши родителю индивидуальный отчёт по короткому тесту. На входе переданы diagnostic_summary и report_facts. Эти данные вычислены программно и обязательны: не меняй диапазон классов, количество правильных ответов, оценку ошибок и вывод о материале предыдущего этапа.

Пиши по-человечески, как учитель разговаривает с родителем. Перед отправкой найди канцеляризмы, страдательный залог и шаблонные фразы нейросетей, затем замени их простыми словами и действительным залогом. Главный герой каждого предложения ребёнок: ребёнок понимает, различает, правильно использует, прошёл тему, усвоил её или пока в ней ошибается.

Структура текста:
1. Начни с благодарности: Спасибо, что нашли время пройти тест.
2. Напиши: Мы проверили, как ребёнок усвоил материал за 1–2, 3–4 или 5–6 класс. Затем укажи число правильных ответов.
3. Передай общий вывод из report_facts.overall_conclusion и оценку из report_facts.severity_label.
4. Скажи, что ребёнок понимает и правильно использует. Не пиши Хорошо получились темы.
5. Назови темы из report_facts.gaps и скажи, где ребёнок ошибается. Не называй темы нестабильными и не пиши, что темы чему-то мешают.
6. Если есть report_facts.foundation, обязательно передай foundation.message.
7. Обязательно передай report_facts.grade_context. Бот не знает точный класс ребёнка, поэтому нельзя одинаково оценивать третьеклассника и четвероклассника, а также пятиклассника и шестиклассника. Пиши только в действительном залоге: ребёнок мог ещё не проходить тему.
8. Заверши выводом из report_facts.progression_outlook.
9. В конце напиши простыми словами: Это короткий тест с готовыми вариантами ответа. Чтобы точнее определить уровень, я бы ещё посмотрела, как ребёнок говорит по-английски, понимает речь на слух и сам составляет предложения.

Не давай родителю методических или домашних заданий. Не предлагай родителю заниматься с ребёнком по карточкам, просить его повторять правила, тренировать темы дома или делать упражнения. Родитель не должен становиться преподавателем. Допустимо сказать, что ребёнку стоит разобрать ошибки с преподавателем или пройти более подробную диагностику.

Запрещённые выражения: проверялся маршрут; хорошо получились; наиболее нестабильны; фундамент сохранён; база сохранена; оценка серьёзности; проверить речь; обычные действия; темы мешают; темы наслаиваются; могла быть не изучена; дальнейшее усложнение материала; потребуют больших усилий; затрагивают значимую часть. Не используй кавычки, длинное тире и двойные пробелы. Не нагнетай и не сглаживай результат.

Пиши естественным русским языком, 170–250 слов, обычными абзацами. Верни только чистый текст для VK без Markdown, заголовков, списков, ссылок и технических кодов."""


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


def topic_analysis(summary: dict) -> tuple[list[dict], list[dict]]:
    strengths = []
    gaps = []
    for order, topic in enumerate(summary.get("topics", [])):
        maximum = int(topic.get("max", 0))
        score = int(topic.get("score", 0))
        errors = max(0, maximum - score)
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
    return strengths[:3], gaps[:4]


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
        return "Ребёнок ошибается в нескольких темах, на которых строится дальнейшая грамматика. Если их не разобрать, дальше ему будет труднее."
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
    strengths, gaps = topic_analysis(summary)
    return {
        "route_key": key,
        "route_range": ROUTE_RANGES[key],
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
        "grade_context": grade_context(
            key,
            correct,
            total,
            foundation["mistakes"] if foundation else 0,
        ),
        "progression_outlook": progression_outlook(effective_severity),
    }


def format_topics(items: list[dict]) -> str:
    return "; ".join(item["label"] for item in items)


def fallback_report(summary: dict) -> str:
    facts = build_report_facts(summary)
    route_name = str(facts["route_name"])
    route_detail = route_name.replace(facts["route_range"], "").strip(" /-")
    route_suffix = f" ({route_detail})" if route_detail else ""
    parts = [
        (
            "Спасибо, что нашли время пройти тест. "
            f"Мы проверили, как ребёнок усвоил материал за {facts['route_range']}{route_suffix}. "
            f"Ребёнок правильно ответил на {facts['correct_total']} из {facts['total_questions']} вопросов "
            f"({facts['score_percent']}%)."
        ),
        (
            f"{facts['overall_conclusion']} {facts['severity_explanation']}"
        ),
    ]

    if facts["strengths"]:
        parts.append("Ребёнок понимает эти темы: " + format_topics(facts["strengths"]) + ".")
    else:
        parts.append("Ребёнок допустил хотя бы одну ошибку в каждой проверенной теме.")

    if facts["gaps"]:
        parts.append("Ребёнок пока ошибается в таких темах: " + format_topics(facts["gaps"]) + ".")
    else:
        parts.append("В заданиях с выбором ответа ребёнок не допустил ошибок.")

    if facts["foundation"]:
        parts.append(facts["foundation"]["message"])

    parts.extend([
        facts["grade_context"],
        facts["progression_outlook"],
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
        and has_severity
        and has_gap
        and has_foundation
        and "короткий тест с готовыми вариантами ответа" in lower
        and "понимает речь на слух" in lower
        and "сам составляет предложения" in lower
        and ("учится в 1 классе" in lower or "учится в 3 классе" in lower or "учится в 5 классе" in lower)
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
