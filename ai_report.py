from __future__ import annotations

import os
import json
import requests

TEACHER_VK_ID = int(os.getenv("TEACHER_VK_ID", "2840329"))

SYSTEM_PROMPT = """Ты — Miss Ellie, опытный онлайн-преподаватель английского языка для школьников.
Тебе передают обезличенные результаты короткой диагностики уровня Pre-A1 / Starters.
Напиши родителю индивидуальный отчёт на русском языке.

Правила:
- Опирайся ТОЛЬКО на переданные результаты и конкретные ошибки. Ничего не выдумывай.
- Не ставь диагнозов и не делай категоричных выводов по двум вопросам на тему.
- Формулируй профессионально, тепло и понятно без методической канцелярщины.
- Сначала общий вывод в 2–3 предложениях.
- Затем: что получается уверенно.
- Затем: что стоит повторить в первую очередь, с конкретными примерами ошибок.
- Если по теме 1/2, называй это частичным пониманием, а не незнанием.
- Если по теме 0/2, пиши «тема пока требует повторения / отработки».
- В конце обязательно скажи, что это экспресс-диагностика с выбором ответа: она не проверяет полноценно устную речь, аудирование и самостоятельное построение фраз.
- Заверши короткой рекомендацией следующего шага без навязчивой продажи.
- Не упоминай технические error_code.
- Объём: примерно 250–450 слов.
"""


def teacher_stub(summary: dict) -> str:
    mastered = [x["topic_ru"] for x in summary["topics"] if x["score"] == 2]
    partial = [x["topic_ru"] for x in summary["topics"] if x["score"] == 1]
    needs = [x["topic_ru"] for x in summary["topics"] if x["score"] == 0]
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
        return teacher_stub(summary)

    api_url = os.getenv("AI_API_URL", "").strip()
    api_key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "").strip()
    if not api_url or not api_key or not model:
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
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return fallback_report(summary)


def fallback_report(summary: dict) -> str:
    mastered = [x["topic_ru"] for x in summary["topics"] if x["score"] == 2]
    partial = [x["topic_ru"] for x in summary["topics"] if x["score"] == 1]
    needs = [x["topic_ru"] for x in summary["topics"] if x["score"] == 0]
    errors = [e["meaning"] for e in summary.get("errors", [])]
    parts = [
        "Здравствуйте! Я посмотрела результаты экспресс-диагностики.",
        f"Ребёнок ответил верно на {summary['correct_total']} из 20 вопросов.",
    ]
    if mastered:
        parts.append("Уверенно получились: " + ", ".join(mastered) + ".")
    if partial:
        parts.append("Частично усвоены: " + ", ".join(partial) + ". Здесь уже есть понимание, но нужны несколько точечных тренировок.")
    if needs:
        parts.append("В первую очередь стоит повторить: " + ", ".join(needs) + ".")
    if errors:
        parts.append("По ответам особенно заметны такие моменты: " + "; ".join(dict.fromkeys(errors)) + ".")
    parts.append("Важно: это короткая диагностика с выбором ответа. Она не проверяет полноценно устную речь, аудирование и способность самостоятельно строить фразы.")
    parts.append("Следующим шагом полезно точечно потренировать слабые места, а затем проверить их уже в речи и небольших заданиях без готовых вариантов ответа.")
    return "\n\n".join(parts)
