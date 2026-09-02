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
            "Спасибо, что нашли время пройти тест. "
            f"Мы проверили, как ребёнок усвоил материал за {facts['route_range']}. "
            f"Диагностика рассчитана примерно на уровень {facts['target_level']}. Это предварительная оценка, "
            "а не официальный подтверждённый уровень. "
            f"Ребёнок правильно ответил на {facts['correct_total']} из {facts['total_questions']} вопросов.\n\n"
            f"{facts['level_conclusion']} {facts['overall_conclusion']} По результату видно: {facts['severity_label']}. "
            f"{facts['severity_explanation']}\n\n"
            f"{facts['grammar']['message']}\n\n"
            f"{facts['vocabulary']['message']} {facts['grammar_vocabulary_balance']}\n\n"
            f"Ребёнок пока ошибается в таких темах: {gaps}.\n\n"
            f"{foundation}\n\n"
            f"{facts['grade_context']}\n\n"
            f"{facts['readiness']['message']}\n\n"
            "Это короткий тест с готовыми вариантами ответа. Чтобы точнее определить уровень, "
            "я бы ещё посмотрела, как ребёнок говорит по-английски, понимает речь на слух "
            "и сам составляет предложения."
        )
        return FakeResponse(content)


def summary_for(route, wrong_question_ids=(), wrong_error_codes=None):
    wrong_question_ids = set(wrong_question_ids)
    wrong_error_codes = wrong_error_codes or {}
    answers = []
    emeralds = 0
    for question in QUESTION_SETS[route]:
        want_correct = question["id"] not in wrong_question_ids
        if want_correct:
            option = next(option for option in question["options"] if option.get("correct"))
        elif question["id"] in wrong_error_codes:
            option = next(
                option for option in question["options"]
                if option.get("error") == wrong_error_codes[question["id"]]
            )
        else:
            option = next(option for option in question["options"] if not option.get("correct"))
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
            "error": option.get("error") if not want_correct else None,
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
            "проверялся маршрут",
            "хорошо получились",
            "нестабильн",
            "фундамент сохран",
            "база сохран",
            "оценка серьёзности",
            "проверить речь",
            "проверила речь",
            "обычные действия",
            "темы мешают",
            "темы наслаиваются",
            "могла ещё не изучаться",
            "дальнейшее усложнение",
            "потребуют от ребёнка",
            "затрагивают значимую часть",
        ):
            self.assertNotIn(forbidden, lower)
        for markdown in ("**", "__", "`", "# "):
            self.assertNotIn(markdown, report)
        for unwanted_character in ("—", "«", "»", "“", "”", "„"):
            self.assertNotIn(unwanted_character, report)
        self.assertNotRegex(report, r"[^\n] {2,}[^\n]")
        self.assertLess(len(report), 4096)

    def assert_report_contract(self, route, wrong_ids, expected_severity, expected_term):
        summary = summary_for(route, wrong_ids)
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(expected_severity, facts["severity"])
        self.assertIn(self.ai_report.ROUTE_RANGES[route], report)
        self.assertIn(self.ai_report.SEVERITY_LABELS[expected_severity], report.lower())
        self.assertIn(expected_term, report)
        self.assertIn("Спасибо, что нашли время пройти тест", report)
        self.assertIn("Мы проверили, как ребёнок усвоил материал", report)
        self.assertIn(self.ai_report.ROUTE_LEVELS[route], report)
        self.assertIn("Диагностика рассчитана примерно на уровень", report)
        self.assertIn("не официальный подтверждённый уровень", report)
        self.assertIn("граммат", report.lower())
        self.assertTrue("лексик" in report.lower() or "словарн" in report.lower())
        self.assertIn("готов", facts["readiness"]["message"].lower()) if facts["readiness"]["severity"] in {"none", "small"} else None
        self.assertIn("Это короткий тест с готовыми вариантами ответа", report)
        self.assertIn("только часть словарного запаса", report)
        self.assertIn("понимает речь на слух", report)
        self.assertIn("сам составляет предложения", report)
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
                    self.assertIn("target_level", data["report_facts"])
                    self.assertIn("grammar", data["report_facts"])
                    self.assertIn("vocabulary", data["report_facts"])
                    self.assertIn("readiness", data["report_facts"])
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
        self.assertIn("усвоил материал за 1–2 класс", report)
        self.assertIn("учится в 3 классе", report)
        self.assertIn("Past Simple", report)
        self.assertIn("мог ещё не проходить", report)

        facts, report = self.assert_report_contract(
            "3-4", {1}, "noticeable", "притяжательные местоимения"
        )
        self.assertEqual([1], facts["foundation"]["mistake_question_ids"])
        self.assertIn("материал за 1–2 класс он в основном усвоил", report)

        facts, report = self.assert_report_contract(
            "3-4", set(range(1, 13)), "substantial", "притяжательные местоимения"
        )
        self.assertEqual(4, facts["foundation"]["mistakes"])
        self.assertIn("пройти тест за 1–2 класс", report)
        self.assertIn("Даже если ребёнок сейчас учится в 3 классе", report)

    def test_3_4_medium_score_is_interpreted_for_both_grades(self):
        facts, report = self.assert_report_contract(
            "3-4", set(range(9, 18)), "noticeable", "Past Simple"
        )
        self.assertEqual(11, facts["correct_total"])
        self.assertEqual(0, facts["foundation"]["mistakes"])
        self.assertIn("вполне хороший промежуточный результат", report)
        self.assertIn("заканчивает 4 класс", report)

    def test_5_6_distinguishes_previous_stage_foundation(self):
        facts, report = self.assert_report_contract(
            "5-6", {10, 11, 12, 13}, "noticeable", "превосходная степень наречий"
        )
        self.assertEqual(0, facts["foundation"]["mistakes"])
        self.assertIn("первых девяти заданиях", report)
        self.assertIn("усвоил материал за 3–4 класс", report)

        facts, report = self.assert_report_contract(
            "5-6", {1, 2}, "noticeable", "притяжательные местоимения"
        )
        self.assertEqual(2, facts["foundation"]["mistakes"])
        self.assertIn("с 7 класса", report.lower())
        self.assertIn("будет труднее", report)

        facts, report = self.assert_report_contract(
            "5-6", {1, 2, 3, 4, 5}, "substantial", "притяжательные местоимения"
        )
        self.assertEqual(5, facts["foundation"]["mistakes"])
        self.assertIn("ошибок много", report.lower())
        self.assertIn("пройти тест за 3–4 класс", report)
        self.assertIn("Даже если ребёнок сейчас учится в 5 классе", report)

        facts, _report = self.assert_report_contract(
            "5-6", {20}, "small", "will для решения"
        )
        self.assertEqual(19, facts["correct_total"])
        self.assertEqual(0, facts["foundation"]["mistakes"])

    def test_5_6_medium_score_is_good_intermediate_result_for_fifth_grader(self):
        facts, report = self.assert_report_contract(
            "5-6", set(range(10, 19)), "noticeable", "превосходная степень наречий"
        )
        self.assertEqual(11, facts["correct_total"])
        self.assertEqual(0, facts["foundation"]["mistakes"])
        self.assertIn("вполне хороший промежуточный результат", report)
        self.assertIn("часть тем за 6 класс он мог ещё не проходить", report)
        self.assertIn("заканчивает 6 класс", report)

    def test_route_level_is_an_orientation_and_never_promotes_5_6_to_a2(self):
        expected_levels = {"1-2": "Pre-A1", "3-4": "A1", "5-6": "A1+"}
        for route, level in expected_levels.items():
            facts = self.ai_report.build_report_facts(summary_for(route))
            report = self.ai_report.fallback_report(summary_for(route))
            with self.subTest(route=route):
                self.assertEqual(level, facts["target_level"])
                self.assertIn(f"уровень {level}", report)
                self.assertIn("предварительная оценка", report)
                self.assertIn(f"соответствуют ожидаемой базе уровня {level}", report)
                if route == "5-6":
                    self.assertNotRegex(report, r"\bA2\b")

    def test_3_4_reports_confirmed_lexical_errors_separately_from_grammar(self):
        lexical_choices = {
            1: "FAMILY_DAUGHTER_HUSBAND",
            2: "FEELINGS_APPEARANCE",
            3: "DOLL_LAMP",
            4: "ACTION_VOCABULARY",
        }
        summary = summary_for("3-4", lexical_choices, lexical_choices)
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(0, facts["grammar"]["error_count"])
        self.assertEqual(4, facts["vocabulary"]["error_count"])
        self.assertEqual("substantial", facts["vocabulary"]["severity"])
        self.assertIn("семья", facts["vocabulary"]["categories"])
        self.assertIn("одежда и повседневные действия", report)
        self.assertIn("В заданиях на грамматику ребёнок не допустил ошибок", report)
        self.assertIn("существенные пробелы в базовой лексике предыдущих лет", report)
        self.assertIn("Основную грамматическую базу ребёнок усвоил", report)

    def test_5_6_base_vocabulary_errors_block_readiness_for_seventh_grade(self):
        lexical_choices = {
            3: "TRAVEL_DRIVE_FLY",
            4: "BY_AIR_ON_FOOT",
            5: "CEREAL_SAUSAGES",
            6: "CLOTHES_EQUIPMENT",
            8: "TALLER_MEANING",
        }
        summary = summary_for("5-6", lexical_choices, lexical_choices)
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(5, facts["vocabulary"]["error_count"])
        self.assertEqual(5, facts["vocabulary"]["foundation_errors"])
        self.assertEqual("substantial", facts["vocabulary"]["severity"])
        self.assertIn("базы предыдущего уровня A1", facts["level_conclusion"])
        self.assertIn("грамматика, и лексика", facts["readiness"]["message"])
        self.assertIn("С 7 класса", report)
        self.assertIn("путешествия и транспорт", report)

    def test_grammar_errors_do_not_become_vocabulary_errors(self):
        summary = summary_for("5-6", {10, 11, 12, 13})
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(0, facts["vocabulary"]["error_count"])
        self.assertEqual([], facts["vocabulary"]["categories"])
        self.assertGreater(facts["grammar"]["error_count"], 0)
        self.assertIn("В проверенной лексике явных трудностей не видно", report)
        self.assertIn("не подтверждают весь словарный запас уровня A1+", report)

    def test_possible_lexical_cause_is_not_reported_as_confirmed(self):
        summary = summary_for("5-6", {1}, {1: "BE_HAVE_CONFUSION"})
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(0, facts["vocabulary"]["error_count"])
        self.assertEqual(["семья и аксессуары"], facts["vocabulary"]["possible_categories"])
        self.assertIn("могут указывать", report)
        self.assertIn("недостаточно, чтобы утверждать это уверенно", report)

    def test_teacher_stub_uses_new_parent_report_structure(self):
        report = self.ai_report.teacher_stub(summary_for("3-4", {1, 2, 9, 10, 11}))
        self.assertIn("3–4 класс", report)
        self.assertIn("ошибок много", report.lower())
        self.assertIn("материала за 1–2 класс", report)
        self.assertNotIn("Нужно повторить:", report)
        self.assert_parent_safe(report)

    def test_invalid_ai_advice_is_replaced_by_safe_fallback(self):
        facts = self.ai_report.build_report_facts(summary_for("1-2", {20}))
        bad_report = "Проверялся маршрут 1–2 класс. Есть отдельные ошибки. Попросите ребёнка повторять правила."
        self.assertFalse(self.ai_report.report_is_usable(bad_report, facts))
        cleaned = self.ai_report.clean_report_text("**«Притяжательные  слова» — тема**")
        self.assertEqual("притяжательные местоимения: тема", cleaned)

    def test_ai_report_validator_requires_level_grammar_and_vocabulary(self):
        facts = self.ai_report.build_report_facts(summary_for("5-6"))
        valid_report = self.ai_report.fallback_report(summary_for("5-6"))
        self.assertTrue(self.ai_report.report_is_usable(valid_report, facts))

        without_vocabulary = valid_report.replace(facts["vocabulary"]["message"], "")
        self.assertFalse(self.ai_report.report_is_usable(without_vocabulary, facts))

        with_a2 = valid_report + " Уровень A2 подтверждён."
        self.assertFalse(self.ai_report.report_is_usable(with_a2, facts))


if __name__ == "__main__":
    unittest.main()
