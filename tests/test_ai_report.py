from __future__ import annotations

import importlib
import json as jsonlib
import os
import sys
import types
import unittest

from diagnostics import build_summary
from question_sets import QUESTION_SETS


class FakeResponse:
    def __init__(self, content):
        self.content = content

    @staticmethod
    def raise_for_status():
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


class FakeRequests(types.ModuleType):
    class HTTPError(Exception):
        pass

    def __init__(self):
        super().__init__("requests")
        self.payload = None

    def post(self, _url, headers=None, json=None, timeout=None):
        self.payload = json
        data = jsonlib.loads(json["messages"][1]["content"])
        facts = data["report_facts"]
        gaps = "; ".join(item["label"] for item in facts["gaps"])
        foundation = facts["foundation"]["message"] if facts["foundation"] else ""
        content = (
            f"Проверялся маршрут {facts['route_range']}. "
            f"Результат: {facts['correct_total']} из {facts['total_questions']}.\n\n"
            f"{facts['overall_conclusion']} Оценка — {facts['severity_label']}. "
            f"{facts['severity_explanation']}\n\n"
            f"Наиболее нестабильны: {gaps}.\n\n"
            f"{foundation}\n\n"
            f"{facts['progression_outlook']}\n\n"
            "Это экспресс-диагностика. Чтобы понять уровень точнее, я бы ещё проверила речь, "
            "понимание на слух и то, как ребёнок строит фразы без вариантов ответа."
        )
        return FakeResponse(content)


def summary_for(route, wrong_question_ids=()):
    wrong_question_ids = set(wrong_question_ids)
    answers = []
    emeralds = 0
    for question in QUESTION_SETS[route]:
        want_correct = question["id"] not in wrong_question_ids
        option = next(
            option for option in question["options"]
            if bool(option.get("correct")) is want_correct
        )
        answers.append({
            "question_id": question["id"],
            "topic": question["topic"],
            "topic_ru": question["topic_ru"],
            "question": question["question"],
            "selected_text": option["text"],
            "correct_text": next(
                candidate["text"] for candidate in question["options"]
                if candidate.get("correct")
            ),
            "correct": want_correct,
            "meaning": option.get("meaning") if not want_correct else None,
        })
        emeralds += 2 if want_correct else 1
    return build_summary({"class": route, "answers": answers, "emeralds": emeralds})


class AiReportTests(unittest.TestCase):
    def setUp(self):
        self.previous_requests = sys.modules.get("requests")
        self.fake_requests = FakeRequests()
        sys.modules["requests"] = self.fake_requests
        sys.modules.pop("ai_report", None)
        self.ai_report = importlib.import_module("ai_report")

    def tearDown(self):
        sys.modules.pop("ai_report", None)
        if self.previous_requests is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = self.previous_requests

    def assert_parent_safe(self, report):
        lower = report.lower()
        for forbidden in (
            "позанимайтесь",
            "попросите ребёнка",
            "попросите ребенка",
            "тренируйте дома",
            "занимайтесь карточками",
            "делайте упражнения",
            "притяжательные слова",
        ):
            self.assertNotIn(forbidden, lower)
        for markdown in ("**", "__", "`", "# "):
            self.assertNotIn(markdown, report)
        self.assertLess(len(report), 4096)

    def assert_report_contract(self, route, wrong_ids, expected_severity, expected_term):
        summary = summary_for(route, wrong_ids)
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(expected_severity, facts["severity"])
        self.assertIn(self.ai_report.ROUTE_RANGES[route], report)
        self.assertIn(self.ai_report.SEVERITY_LABELS[expected_severity], report)
        self.assertIn(expected_term, report)
        self.assertIn("школьн", report)
        self.assertIn("программ", report)
        self.assertIn("Это экспресс-диагностика", report)
        self.assertIn("понимание на слух", report)
        self.assert_parent_safe(report)
        return facts, report

    def test_ai_payload_contains_deidentified_programmatic_facts(self):
        previous_env = {name: os.environ.get(name) for name in ("AI_API_URL", "AI_API_KEY", "AI_MODEL")}
        os.environ.update({
            "AI_API_URL": "https://example.invalid/chat/completions",
            "AI_API_KEY": "test-key",
            "AI_MODEL": "test-model",
        })
        try:
            for route in QUESTION_SETS:
                summary = summary_for(route, {20})
                report = self.ai_report.generate_parent_report(999999, summary)
                with self.subTest(route=route):
                    self.assertIn(self.ai_report.ROUTE_RANGES[route], report)
                    serialized = str(self.fake_requests.payload)
                    self.assertNotIn("vk_id", serialized)
                    self.assertNotIn("phone", serialized.lower())
                    self.assertNotIn("email", serialized.lower())
                    data = jsonlib.loads(self.fake_requests.payload["messages"][1]["content"])
                    self.assertEqual(route, data["report_facts"]["route_key"])
                    self.assertIn("severity_label", data["report_facts"])
                    self.assertIn("progression_outlook", data["report_facts"])
                    self.assert_parent_safe(report)
        finally:
            for name, value in previous_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_1_2_strong_medium_and_problematic_results(self):
        scenarios = (
            ({20}, "small", "указательные местоимения"),
            (set(range(13, 21)), "noticeable", "предлоги места"),
            (set(range(7, 21)), "substantial", "Present Simple"),
        )
        for wrong_ids, severity, term in scenarios:
            with self.subTest(wrong_ids=sorted(wrong_ids)):
                self.assert_report_contract("1-2", wrong_ids, severity, term)

    def test_3_4_distinguishes_new_topics_from_early_foundation(self):
        facts, report = self.assert_report_contract(
            "3-4", {5, 6, 7, 8}, "noticeable", "сравнительная степень"
        )
        self.assertEqual(0, facts["foundation"]["mistakes"])
        self.assertIn("фундамент первого этапа обучения", report)
        self.assertIn("сохранён уверенно", report)

        facts, report = self.assert_report_contract(
            "3-4", {1}, "noticeable", "притяжательные местоимения"
        )
        self.assertEqual([1], facts["foundation"]["mistake_question_ids"])
        self.assertIn("база закреплена не полностью", report)

        facts, report = self.assert_report_contract(
            "3-4", set(range(1, 13)), "substantial", "притяжательные местоимения"
        )
        self.assertEqual(4, facts["foundation"]["mistakes"])
        self.assertIn("важный сигнал", report)

    def test_5_6_distinguishes_previous_stage_foundation(self):
        facts, report = self.assert_report_contract(
            "5-6", {10, 11, 12, 13}, "noticeable", "превосходная степень наречий"
        )
        self.assertEqual(0, facts["foundation"]["mistakes"])
        self.assertIn("Первые 9 заданий", report)
        self.assertIn("сохранена хорошо", report)

        facts, report = self.assert_report_contract(
            "5-6", {1, 2}, "noticeable", "притяжательные местоимения"
        )
        self.assertEqual(2, facts["foundation"]["mistakes"])
        self.assertIn("с 7 класса", report.lower())
        self.assertIn("усложняются скачкообразно", report)

        facts, report = self.assert_report_contract(
            "5-6", {1, 2, 3, 4, 5}, "substantial", "притяжательные местоимения"
        )
        self.assertEqual(5, facts["foundation"]["mistakes"])
        self.assertIn("существенные пробелы", report)
        self.assertIn("с 7 класса", report.lower())

        facts, _report = self.assert_report_contract(
            "5-6", {20}, "small", "will для решения"
        )
        self.assertEqual(19, facts["correct_total"])
        self.assertEqual(0, facts["foundation"]["mistakes"])

    def test_teacher_stub_uses_new_parent_report_structure(self):
        report = self.ai_report.teacher_stub(summary_for("3-4", {1, 2, 9, 10, 11}))
        self.assertIn("3–4 класс", report)
        self.assertIn("существенные пробелы", report)
        self.assertIn("фундамент первого этапа", report)
        self.assertNotIn("Нужно повторить:", report)
        self.assert_parent_safe(report)

    def test_invalid_ai_advice_is_replaced_by_safe_fallback(self):
        facts = self.ai_report.build_report_facts(summary_for("1-2", {20}))
        bad_report = "Проверялся маршрут 1–2 класс. Небольшие пробелы. Попросите ребёнка повторять правила."
        self.assertFalse(self.ai_report.report_is_usable(bad_report, facts))
        cleaned = self.ai_report.clean_report_text("**Притяжательные слова**")
        self.assertEqual("притяжательные местоимения", cleaned)


if __name__ == "__main__":
    unittest.main()
