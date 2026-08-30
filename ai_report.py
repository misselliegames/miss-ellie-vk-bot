from __future__ import annotations

import os
import json
import re
import requests

TEACHER_VK_ID = int(os.getenv("TEACHER_VK_ID", "2840329"))

REPORT_TOPIC_NAMES = {
    "NUMBERS": "числительные",
    "TO_BE": "построение фраз с глаголом-связкой",
    "HAVE_GOT": "выражение значения «у кого-то есть»",
    "PRESENT_SIMPLE": "обычные действия в настоящем времени",
    "CAN": "выражение умения и возможности",
    "THERE_IS_ARE": "описание того, что где-то находится",
    "PREPOSITIONS": "предлоги места",
    "PRESENT_CONTINUOUS": "действия, происходящие сейчас",
    "PLURAL": "множественное число существительных",
    "DEMONSTRATIVES": "указательные слова",
}

SYSTEM_PROMPT = """Ты — Miss Ellie, опытный преподаватель английского языка для школьников. На входе — только обезличенные результаты короткой диагностики Pre-A1 / Starters. Напиши родителю индивидуальный педагогический отчёт на естественном русском языке.

Опирайся только на переданные вопросы, выбранные и правильные ответы, диагностические пояснения и результаты. Ничего не выдумывай и не упоминай технические коды. Пиши профессионально, тепло и конкретно, без канцеляризмов и механического перечисления всех десяти тем.

Найди связи между ошибками и выдели одну-две главные закономерности. Различай устойчивое понимание, нестабильный навык и общую модель ошибки, проявившуюся в нескольких темах. Связанные ошибки объединяй. Например, несколько ошибок в заданиях с глаголами могут означать, что ребёнок пока смешивает разные способы построения фразы в настоящем времени; тогда предложи сначала наглядно развести эти способы. Для предлогов, указательных слов и других конкретных трудностей предложи понятный следующий педагогический шаг.

Пиши прежде всего обычным понятным русским языком. Не засоряй отчёт английскими названиями грамматических тем. Переданные технические названия и диагностические пояснения переводи в понятное родителю педагогическое описание. Английский пример можно привести только тогда, когда он действительно помогает объяснению.

Не используй штампы «есть путаница по числу», «тема требует повторения / отработки» по каждому пункту и «частично усвоены» как механический список. Не делай категоричных выводов по двум заданиям.

Структура: короткий общий вывод; что уже является хорошей базой; главная закономерность в ошибках; что делать в первую очередь; короткое ограничение диагностики. Объём 180–300 слов.

Обязательно напомни, что это экспресс-диагностика с выбором ответа и она не проверяет полноценно устную речь, понимание речи на слух и самостоятельное построение фраз.

Верни обычный чистый текст для VK. Не используй Markdown: никаких заголовков с #, выделения ** или __, markdown-ссылок и других конструкций разметки.
"""


def clean_report_text(text: str) -> str:
    text = re.sub(r"\\+(?=[`*_#\[\]()])", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    replacements = {
        "speaking": "устная речь",
        "listening": "понимание речи на слух",
        "Present Simple": "обычные действия в настоящем времени",
        "Present Continuous": "действия, происходящие сейчас",
        "Demonstratives": "указательные слова",
        "Prepositions of place": "предлоги места",
        "Plural nouns": "множественное число существительных",
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text.strip()


def report_topic_name(topic: dict) -> str:
    return REPORT_TOPIC_NAMES.get(topic["topic"], topic["topic_ru"])


def teacher_stub(summary: dict) -> str:
    mastered = [report_topic_name(x) for x in summary["topics"] if x["score"] == 2]
    partial = [report_topic_name(x) for x in summary["topics"] if x["score"] == 1]
    needs = [report_topic_name(x) for x in summary["topics"] if x["score"] == 0]
    return (
        "Здравствуйте! Это демонстрационный отчёт для проверки курса — для вашего VK ID вызов платного ИИ отключён.\n\n"
        f"Результат: {summary['correct_total']} из 20 ответов верные. Собрано {summary['emeralds']} изумрудов.\n\n"
        f"Уверенно: {', '.join(mastered) if mastered else 'пока нет тем с результатом 2/2'}.\n"
        f"Частично: {', '.join(partial) if partial else '—'}.\n"
        f"Нужно повторить: {', '.join(needs) if needs else '—'}.\n\n"
        "В обычном пользовательском прохождении в этом месте вызывается AI API, которому передаются только обезличенные результаты диагностики и конкретные типы ошибок."
    )


def generate_parent_report(user_id: int, summary: dict) -> str:
    if user_id == TEACHER_VK_ID:
        return clean_report_text(teacher_stub(summary))

    api_url = os.getenv("AI_API_URL", "").strip()
    api_key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "").strip()
    if not api_url or not api_key or not model:
        print("AI_REPORT_FALLBACK: configuration_missing")
        return fallback_report(summary)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(summary, ensure_ascii=False, indent=2)},
        ],
        "temperature": 0.4,
        "max_tokens": 900,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        report = clean_report_text(data["choices"][0]["message"]["content"])
        print("AI_REPORT_SUCCESS")
        return report
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"AI_REPORT_FALLBACK: HTTP_{status}")
        return fallback_report(summary)
    except Exception as exc:
        print(f"AI_REPORT_FALLBACK: {type(exc).__name__}")
        return fallback_report(summary)


def fallback_report(summary: dict) -> str:
    mastered = [report_topic_name(x) for x in summary["topics"] if x["score"] == 2]
    developing = [report_topic_name(x) for x in summary["topics"] if x["score"] < 2]
    strongest = ", ".join(mastered[:3]) if mastered else "отдельные знакомые слова и конструкции"
    priorities = ", ".join(developing[:2]) if developing else "перенос знакомых конструкций в самостоятельную речь"
    parts = [
        "Здравствуйте! Я посмотрела результаты экспресс-диагностики.",
        f"Ребёнок ответил верно на {summary['correct_total']} из 20 вопросов. Уже есть хорошая база, на которую можно опираться дальше.",
        f"Увереннее всего получились задания на: {strongest}.",
    ]
    if developing:
        parts.append("По ответам видно, что некоторые похожие способы построения фразы пока используются нестабильно. По короткому тесту это нельзя считать окончательным выводом: полезно проверить, понимает ли ребёнок разницу между моделями, а не запоминает ответ целиком.")
    parts.append(f"В первую очередь я бы взяла две ближайшие цели: {priorities}. Лучше тренировать их короткими контрастными примерами с картинками, а затем просить ребёнка выбрать и самостоятельно произнести подходящую фразу.")
    parts.append("Важно: это короткая диагностика с выбором ответа. Она не проверяет полноценно устную речь, понимание речи на слух и способность самостоятельно строить фразы.")
    return clean_report_text("\n\n".join(parts))
