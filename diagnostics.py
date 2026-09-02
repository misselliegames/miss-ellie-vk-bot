from __future__ import annotations

from collections import defaultdict

from question_sets import ROUTE_NAMES, questions_for_route, topic_order_for_route


def build_summary(session):
    route = session.get("class") or "1-2"
    questions = questions_for_route(route)
    by_topic = defaultdict(list)
    for answer in session["answers"]:
        by_topic[answer["topic"]].append(answer)

    question_counts = defaultdict(int)
    topic_names = {}
    for question in questions:
        question_counts[question["topic"]] += 1
        topic_names.setdefault(question["topic"], question["topic_ru"])

    topics = []
    for topic in topic_order_for_route(route):
        answers = by_topic.get(topic, [])
        score = sum(1 for answer in answers if answer["correct"])
        maximum = question_counts[topic]
        topics.append({
            "topic": topic,
            "topic_ru": topic_names.get(topic, topic),
            "score": score,
            "max": maximum,
            "status": "mastered" if score == maximum else "partial" if score else "needs_work",
        })

    answers = [
        {
            "question_id": answer["question_id"],
            "topic": answer["topic"],
            "topic_ru": answer["topic_ru"],
            "question": answer["question"],
            "selected_text": answer["selected_text"],
            "correct_text": answer["correct_text"],
            "correct": answer["correct"],
            "error": answer.get("error") if not answer["correct"] else None,
            "meaning": answer.get("meaning") if not answer["correct"] else None,
        }
        for answer in session["answers"]
    ]
    return {
        "route": ROUTE_NAMES[route],
        "correct_total": sum(1 for answer in session["answers"] if answer["correct"]),
        "total_questions": len(questions),
        "emeralds": session["emeralds"],
        "topics": topics,
        "answers": answers,
        "limitations": "Выбор ответа; не проверялись полноценно устная речь, понимание речи на слух и самостоятельное построение фраз.",
    }
