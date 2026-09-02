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
    "none": "пробелов по заданиям не выявлено",
    "small": "небольшие пробелы",
    "noticeable": "заметные пробелы",
    "substantial": "существенные пробелы",
}

TOPIC_LABELS = {
    "NUMBERS": "числительные и вопросы о цене",
    "TO_BE": "глагол to be (am, is, are) — выбор формы по подлежащему",
    "HAVE_GOT": "конструкция have got / has got — описание того, что у кого-то есть",
    "PRESENT_SIMPLE": "Present Simple — обычные и регулярные действия",
    "CAN": "модальный глагол can — форма смыслового глагола без to и окончания -s",
    "THERE_IS_ARE": "there is / there are — описание того, что где-то находится",
    "PREPOSITIONS": "предлоги места (in, on, under)",
    "PRESENT_CONTINUOUS": "Present Continuous — действия, происходящие прямо сейчас",
    "PLURAL": "множественное число существительных",
    "DEMONSTRATIVES": "указательные местоимения this, that, these, those",
    "POSSESSIVE_FAMILY": "притяжательные местоимения (my, your, his, her) — выбор формы по владельцу",
    "BE_HAVE_APPEARANCE": "to be и have got / has got — описание состояния, внешности и принадлежности",
    "PRESENT_SIMPLE_CONTINUOUS": "Present Simple и Present Continuous — различение обычных действий и происходящего сейчас",
    "COMPARATIVE_ADJECTIVES": "сравнительная степень прилагательных",
    "SUPERLATIVE_ADJECTIVES": "превосходная степень прилагательных",
    "SOME_ANY": "some / any — количество в утверждениях, вопросах и отрицаниях",
    "PAST_SIMPLE": "Past Simple — неправильные глаголы и вопросы с did",
    "WAS_WERE": "формы was / were в прошедшем времени",
    "THERE_WAS_WERE": "there was / there were — описание предметов и мест в прошлом",
    "MUST_MUSTNT": "модальный глагол must / mustn’t — обязанность и запрет",
    "MUCH_MANY": "much / many — исчисляемые и неисчисляемые существительные",
    "QUANTIFIERS": "слова количества not much, not many, a lot of",
    "FUTURE_FORMS": "будущее время — различение will и be going to",
    "POSSESSIVE_BE_HAVE": "притяжательные местоимения, to be и have got / has got",
    "HOW_MUCH_NUMBERS": "вопрос How much...? и числительные 21–100",
    "PRESENT_SIMPLE_TRAVEL": "Present Simple — регулярные действия и окончание -s в 3-м лице",
    "PRESENT_CONTINUOUS_TRAVEL": "Present Continuous и Present Simple — действие сейчас и обычное действие",
    "PRESENT_SIMPLE_NEGATIVE": "вопросы и отрицания в Present Simple",
    "CAN_CLOTHES": "модальный глагол can — смысловой глагол в начальной форме",
    "THERE_IS_ARE_SOME_ANY": "there is / there are и some / any",
    "SUPERLATIVE_ADVERBS": "превосходная степень наречий",
    "ENJOY_GERUND_QUESTION": "порядок слов в вопросе и герундий после enjoy",
    "FEW_LITTLE": "few / a few и little / a little — количество и достаточность",
    "REFLEXIVE_PRONOUNS": "возвратные местоимения himself / herself",
    "HAVE_TO_HAS_TO": "have to / has to — обязанность и согласование с подлежащим",
    "MUSTNT_DONT_HAVE_TO_NEEDNT": "mustn’t, don’t have to и needn’t — запрет и отсутствие необходимости",
    "SHOULD": "модальный глагол should — совет и форма глагола без to",
    "WANT_TO_LET": "конструкции want to do и let somebody do",
    "FUTURE_ARRANGEMENT": "Present Continuous для договорённости на будущее",
    "FUTURE_PLANS": "be going to для заранее существующего плана",
    "FUTURE_DECISIONS": "will для решения, принятого в момент речи",
}


SYSTEM_PROMPT = """Ты — Miss Ellie, опытный преподаватель английского языка для школьников. Напиши родителю индивидуальный отчёт по экспресс-диагностике. На входе переданы diagnostic_summary и report_facts. report_facts вычислены программно и являются обязательными: не меняй маршрут, количество ошибок, оценку серьёзности или вывод о фундаменте.

Родитель должен ясно понять четыре вещи: насколько усвоена программа именно указанного диапазона классов; насколько серьёзны пробелы; какие конкретные темы западают; что результат означает для дальнейшего обучения.

Структура текста:
1. Прямо назови маршрут: 1–2 класс, 3–4 класс или 5–6 класс, и укажи результат.
2. Дай общий вывод из report_facts.overall_conclusion.
3. Используй точную оценку report_facts.severity_label: небольшие, заметные или существенные пробелы — и объясни их влияние на следующую часть школьной программы.
4. Коротко назови сильные стороны.
5. Назови конкретные просевшие темы из report_facts.gaps нормальными терминами: Present Simple, Present Continuous, Past Simple, неправильные глаголы, степени сравнения, модальные глаголы, предлоги, множественное число, притяжательные местоимения и т.д. После термина кратко объясни смысл трудности.
6. Если report_facts.foundation применим, обязательно передай foundation.message. Для 5–6 класса при проблемах в вопросах 1–9 ясно объясни риск скачка сложности с 7 класса. Для 3–4 класса ошибки в вопросах 1–4 нельзя представлять как случайную мелочь.
7. Заверши практическим выводом из report_facts.progression_outlook.
8. В конце сохрани мысль: «Это экспресс-диагностика. Чтобы понять уровень точнее, я бы ещё проверила речь, понимание на слух и то, как ребёнок строит фразы без вариантов ответа.»

Не давай родителю методических или домашних заданий. Не пиши «позанимайтесь карточками», «попросите ребёнка повторять», «тренируйте дома», «делайте упражнения» и подобные советы. Родитель не должен становиться преподавателем. Допустимо сказать, что пробелы важно закрыть с преподавателем или уточнить на профессиональной диагностике.

Не используй расплывчатые эвфемизмы «притяжательные слова», «способы построения фразы» без пояснения, «есть путаница по числу». Не нагнетай и не сглаживай факты. Это не медицинское заключение.

Пиши естественным русским языком, 180–260 слов, обычными абзацами. Верни только чистый текст для VK без Markdown, заголовков, списков, ссылок и технических кодов."""


def clean_report_text(text: str) -> str:
    text = re.sub(r"\\+(?=[`*_#\[\]()])", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(
        r"притяжательн(?:ые|ых|ыми)\s+слова",
        "притяжательные местоимения",
        text,
        flags=re.IGNORECASE,
    )
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
    return strengths[:4], gaps[:5]


def conclusion_for(score_severity: str, effective_severity: str, route_range: str) -> str:
    if score_severity == "none":
        return f"По заданиям за {route_range} школьная программа усвоена уверенно."
    if score_severity == "small" and effective_severity == "small":
        return f"По заданиям за {route_range} школьная программа в целом усвоена."
    if score_severity == "small" and effective_severity != "small":
        return f"По заданиям за {route_range} общий результат сильный, но ошибки в базовом блоке не позволяют считать фундамент полностью устойчивым."
    if effective_severity == "noticeable":
        return f"По заданиям за {route_range} школьная программа усвоена неравномерно."
    return f"По заданиям за {route_range} в школьной программе есть существенные пробелы."


def severity_explanation(severity: str) -> str:
    if severity == "none":
        return "По заданиям теста пробелов не видно; это хороший показатель готовности продолжать программу."
    if severity == "small":
        return "Они локальны и, скорее всего, не помешают продолжать школьную программу."
    if severity == "noticeable":
        return "Они уже могут мешать темам, которые опираются на эти конструкции, поэтому дальше ошибки могут накапливаться."
    return "Они затрагивают значимую часть проверенной программы; перед дальнейшим усложнением материала их важно закрыть с преподавателем."


def progression_outlook(severity: str) -> str:
    if severity in {"none", "small"}:
        return "С такой базой ребёнок, скорее всего, сможет продолжать школьную программу без серьёзных трудностей."
    if severity == "noticeable":
        return "Продолжать школьную программу возможно, но без закрытия этих пробелов новые темы будут наслаиваться на старые ошибки и потребуют от ребёнка заметно больше усилий."
    return "Перед переходом к следующему уровню школьной программы эти пробелы лучше закрыть с преподавателем, иначе ребёнку будет трудно понимать новые грамматические конструкции и лексику."


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
            message = "Вопросы 1–4 проверяли фундамент первого этапа обучения. Он сохранён уверенно, поэтому новые темы маршрута 3–4 класса опираются на достаточно прочную базу."
        elif severity == "noticeable":
            message = "Ошибка появилась уже в вопросах 1–4 на фундамент первого этапа обучения. Это не системный провал, но база закреплена не полностью; пробел важно уточнить с преподавателем до дальнейшего усложнения программы 3–4 класса."
        else:
            message = "Ошибки появились уже в вопросах 1–4 на фундамент первого этапа обучения. Это важный сигнал: прежде чем идти дальше по программе 3–4 класса, этот фундамент лучше закрыть с преподавателем."
    else:
        if not mistakes:
            message = "Первые 9 заданий проверяли базу предыдущего этапа, и она сохранена хорошо. Это заметно облегчает дальнейшее обучение и переход к более сложному материалу."
        elif severity == "small":
            message = "В первых 9 заданиях на базу предыдущего этапа есть одна локальная ошибка. В целом фундамент сохранён, но этот участок стоит уточнить с преподавателем до перехода к более сложным конструкциям."
        elif severity == "noticeable":
            message = "В первых 9 заданиях на базу предыдущего этапа есть заметные пробелы. Это важно, потому что с 7 класса грамматика и лексика усложняются скачкообразно: без укрепления базы новые темы будут наслаиваться на старые ошибки."
        else:
            message = "В первых 9 заданиях на базу предыдущего этапа есть существенные пробелы. С 7 класса грамматика и лексика усложняются скачкообразно, поэтому без закрытия этого фундамента ребёнку станет значительно труднее понимать объяснения и задания."

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
            f"Проверялся маршрут {facts['route_range']}{route_suffix}. "
            f"Ребёнок ответил верно на {facts['correct_total']} из {facts['total_questions']} вопросов "
            f"({facts['score_percent']}%)."
        ),
        (
            f"Общий вывод: {facts['overall_conclusion']} "
            f"Оценка серьёзности — {facts['severity_label']}. {facts['severity_explanation']}"
        ),
    ]

    if facts["strengths"]:
        parts.append("Хорошо получились темы: " + format_topics(facts["strengths"]) + ".")
    else:
        parts.append("Пока ни одна из проверенных тем не показала устойчивого результата во всех заданиях.")

    if facts["gaps"]:
        parts.append("Наиболее нестабильны: " + format_topics(facts["gaps"]) + ".")
    else:
        parts.append("По заданиям с выбором ответа конкретных просевших тем не выявлено.")

    if facts["foundation"]:
        parts.append(facts["foundation"]["message"])

    parts.extend([
        facts["progression_outlook"],
        (
            "Это экспресс-диагностика. Чтобы понять уровень точнее, я бы ещё проверила речь, "
            "понимание на слух и то, как ребёнок строит фразы без вариантов ответа."
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
    )
    has_severity = any(
        label in lower
        for label in (
            "пробелов по заданиям не выявлено",
            "небольшие пробелы",
            "заметные пробелы",
            "существенные пробелы",
        )
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
        has_foundation = "1–4" in report and ("фундамент" in lower or "баз" in lower)
    else:
        has_foundation = "первые 9" in lower or "первых 9" in lower
    return (
        bool(report)
        and len(report) <= MAX_REPORT_CHARS
        and facts["route_range"] in report
        and has_severity
        and has_gap
        and has_foundation
        and "экспресс-диагностик" in lower
        and "понимание на слух" in lower
        and ("программ" in lower or "новые тем" in lower)
        and not any(re.search(pattern, lower) for pattern in forbidden_patterns)
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
