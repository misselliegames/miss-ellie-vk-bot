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
        return FakeResponse("Ответ без обязательных диагностических фактов")


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
            "нельзя считать случайными",
            "несколько важных правил или слов",
            "не официальный",
            "официально подтверждённый",
            "только часть словарного запаса",
            "весь словарный запас",
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
        self.assertIn(expected_term, report)
        self.assertIn("Спасибо, что нашли время пройти тест", report)
        self.assertIn("Мы проверили, как ребёнок усвоил материал", report)
        self.assertIn(self.ai_report.ROUTE_LEVELS[route], report)
        self.assertIn(f"ориентир: {self.ai_report.ROUTE_LEVELS[route]}", report)
        self.assertNotIn("официальн", report.lower())
        self.assertNotIn("подтверждённ", report.lower())
        self.assertIn("граммат", report.lower())
        self.assertTrue("лексик" in report.lower() or "словарн" in report.lower())
        self.assertIn("готов", facts["readiness"]["message"].lower()) if facts["readiness"]["severity"] in {"none", "small"} else None
        self.assertIn("Это короткий тест с готовыми вариантами ответа", report)
        self.assertIn("понимает речь на слух", report)
        self.assertIn("сам составляет предложения", report)
        self.assertIn("пробном занятии", report)
        self.assertEqual(1, report.count("Это короткий тест с готовыми вариантами ответа"))
        self.assertFalse(self.ai_report.has_semantic_repetition(report))
        self.assertTrue(self.ai_report.report_is_usable(report, facts))
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
                    self.assertNotIn("diagnostic_summary", data)
                    self.assertIn("target_level", data["report_facts"])
                    self.assertIn("grammar", data["report_facts"])
                    self.assertIn("vocabulary", data["report_facts"])
                    self.assertIn("readiness", data["report_facts"])
                    self.assertIn("selected_mistakes", data["report_facts"])
                    self.assertEqual(1, len(data["report_facts"]["selected_mistakes"]))
                    mistake = data["report_facts"]["selected_mistakes"][0]
                    self.assertEqual(20, mistake["question_id"])
                    self.assertTrue(mistake["error"])
                    self.assertTrue(mistake["meaning"])
                    self.assertTrue(mistake["selected_text"])
                    self.assertTrue(mistake["correct_text"])
                    self.assert_parent_safe(report)
        finally:
            for name, value in previous_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_1_2_strong_medium_and_problematic_results(self):
        scenarios = (
            ({20}, "small", "that и those"),
            (set(range(13, 21)), "noticeable", "on и under"),
            (set(range(7, 21)), "substantial", "he и she"),
        )
        for wrong_ids, severity, term in scenarios:
            with self.subTest(wrong_ids=sorted(wrong_ids)):
                self.assert_report_contract("1-2", wrong_ids, severity, term)

    def test_3_4_distinguishes_new_topics_from_early_foundation(self):
        facts, report = self.assert_report_contract(
            "3-4", {5, 6, 7, 8}, "noticeable", "сравнительную степень"
        )
        self.assertEqual(0, facts["foundation"]["mistakes"])
        self.assertIn("базу за 1–2 класс, ошибок не было", report)
        self.assertIn("Материал предыдущего этапа ребёнок усвоил", report)
        self.assertIn("учится в 3 классе", report)
        self.assertIn("Past Simple", report)
        self.assertIn("мог ещё не проходить", report)

        facts, report = self.assert_report_contract(
            "3-4", {1}, "noticeable", "his и her"
        )
        self.assertEqual([1], facts["foundation"]["mistake_question_ids"])
        self.assertIn("была одна ошибка", report)
        self.assertIn("В целом материал предыдущего этапа ребёнок усвоил", report)

        facts, report = self.assert_report_contract(
            "3-4", set(range(1, 13)), "substantial", "his и her"
        )
        self.assertEqual(4, facts["foundation"]["mistakes"])
        self.assertIn("было 4 ошибки", report)
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
            "5-6", {10, 11, 12, 13}, "noticeable", "степеней сравнения коротких наречий"
        )
        self.assertEqual(0, facts["foundation"]["mistakes"])
        self.assertIn("первых девяти заданиях", report)
        self.assertIn("базу за 3–4 класс, ошибок не было", report)
        self.assertIn("Материал предыдущего этапа ребёнок усвоил", report)

        facts, report = self.assert_report_contract(
            "5-6", {1, 2}, "noticeable", "his и her"
        )
        self.assertEqual(2, facts["foundation"]["mistakes"])
        self.assertIn("перехода в 7 класс", report.lower())
        self.assertIn("грамматика и лексика станут сложнее", report)

        facts, report = self.assert_report_contract(
            "5-6", {1, 2, 3, 4, 5}, "substantial", "his и her"
        )
        self.assertEqual(5, facts["foundation"]["mistakes"])
        self.assertIn("значительную часть проверенного материала", report)
        self.assertIn("было 5 ошибок", report)
        self.assertIn("Даже если ребёнок сейчас учится в 5 классе", report)

        facts, _report = self.assert_report_contract(
            "5-6", {20}, "small", "решение, принятое сейчас"
        )
        self.assertEqual(19, facts["correct_total"])
        self.assertEqual(0, facts["foundation"]["mistakes"])

    def test_5_6_medium_score_is_good_intermediate_result_for_fifth_grader(self):
        facts, report = self.assert_report_contract(
            "5-6", set(range(10, 19)), "noticeable", "степеней сравнения коротких наречий"
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
                self.assertIn(f"ориентир: {level}", report)
                self.assertNotIn("предварительная оценка", report)
                self.assertNotIn("официальн", report.lower())
                if route == "5-6":
                    self.assertNotRegex(report, r"\bA2\b")

    def test_3_4_reports_confirmed_lexical_errors_separately_from_grammar(self):
        lexical_choices = {
            1: "FAMILY_DAUGHTER_HUSBAND",
            2: "FEELINGS_APPEARANCE",
            3: "DOLL_BALL",
            4: "ACTION_VOCABULARY",
        }
        summary = summary_for("3-4", lexical_choices, lexical_choices)
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(0, facts["grammar"]["error_count"])
        self.assertEqual(4, facts["vocabulary"]["error_count"])
        self.assertEqual("substantial", facts["vocabulary"]["severity"])
        self.assertIn("семья", facts["vocabulary"]["categories"])
        self.assertIn("husband", report)
        self.assertIn("happy и sad", report)
        self.assertIn("doll и ball", report)
        self.assertIn("clothes и daily routine", report)
        self.assertIn("В грамматике ребёнок правильно выполнил все задания", report)

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
        self.assertIn("travel, drive и fly", report)

    def test_grammar_errors_do_not_become_vocabulary_errors(self):
        summary = summary_for("5-6", {10, 11, 12, 13})
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(0, facts["vocabulary"]["error_count"])
        self.assertEqual([], facts["vocabulary"]["categories"])
        self.assertGreater(facts["grammar"]["error_count"], 0)
        self.assertIn("В проверенной лексике явных трудностей не видно", report)
        self.assertNotIn("весь словарный запас", report)
        self.assertNotIn("только часть словарного запаса", report)

    def test_new_5_6_lexical_distractors_are_reported_separately(self):
        lexical_choices = {
            11: "FREE_TIME_ACTIVITY",
            13: "REFLEXIVE_CRIME_ACTIONS",
            17: "ROAD_SAFETY_ROUTE",
            19: "PLAN_VS_WILL_GARDEN",
            20: "DECISION_VS_ARRANGEMENT_ACTIONS",
        }
        summary = summary_for("5-6", lexical_choices, lexical_choices)
        facts = self.ai_report.build_report_facts(summary)
        self.assertEqual(5, facts["vocabulary"]["error_count"])
        self.assertEqual(
            [11, 13, 17, 19, 20],
            [item["question_id"] for item in facts["vocabulary"]["confirmed_errors"]],
        )
        self.assertIn("свободное время", facts["vocabulary"]["categories"])
        self.assertIn("безопасность на дороге и направления", facts["vocabulary"]["categories"])
        self.assertEqual([13, 19, 20], facts["grammar"]["mistake_question_ids"])

    def test_possible_lexical_cause_is_not_reported_as_confirmed(self):
        summary = summary_for("5-6", {1}, {1: "BE_HAVE_CONFUSION"})
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)
        self.assertEqual(0, facts["vocabulary"]["error_count"])
        self.assertEqual(["семья и аксессуары"], facts["vocabulary"]["possible_categories"])
        self.assertIn("может указывать", report)
        self.assertIn("может объясняться и грамматической ошибкой", report)

    def test_3_4_report_uses_the_seven_selected_mistakes_for_13_of_20(self):
        selected_errors = {
            3: "DOLL_BALL",
            5: "COMPARATIVE_FORM",
            7: "SOME_ANY_QUESTION",
            9: "PAST_GO_WENT",
            10: "PAST_DID_BASE_FORM",
            15: "PRESENT_SIMPLE_3SG",
            18: "CHEESE_EGGS",
        }
        summary = summary_for("3-4", selected_errors, selected_errors)
        facts = self.ai_report.build_report_facts(summary)
        report = self.ai_report.fallback_report(summary)

        self.assertEqual(13, facts["correct_total"])
        self.assertEqual(list(selected_errors), [
            item["question_id"] for item in facts["selected_mistakes"]
        ])
        self.assertEqual(list(selected_errors.values()), [
            item["error"] for item in facts["selected_mistakes"]
        ])
        self.assertEqual(
            ["vocabulary", "grammar", "grammar", "grammar", "grammar", "grammar", "vocabulary"],
            [item["kind"] for item in facts["selected_mistakes"]],
        )
        for mistake in facts["selected_mistakes"]:
            self.assertTrue(mistake["meaning"])
            self.assertTrue(mistake["selected_text"])
            self.assertTrue(mistake["correct_text"])

        for expected in (
            "doll и ball",
            "неправильно образует сравнительную степень",
            "путает some и any",
            "глагол go меняется на went",
            "после did оставляет глагол в прошедшей форме",
            "забывает окончание -s в 3-м лице",
            "cheese и eggs",
            "Возможно, ребёнок не помнит и другие слова по теме еды",
        ):
            self.assertIn(expected, report)
        self.assertIn("была одна ошибка", report)
        self.assertNotIn("есть ошибки в нескольких темах", report.lower())
        self.assertFalse(self.ai_report.has_semantic_repetition(report))
        self.assertTrue(self.ai_report.report_is_usable(report, facts))

    def test_repeated_lexical_errors_allow_stronger_topic_inference(self):
        selected_errors = {
            7: "FOOD_ICE_CREAM_CHEESE",
            18: "CHEESE_EGGS",
        }
        report = self.ai_report.fallback_report(
            summary_for("3-4", selected_errors, selected_errors)
        )

        self.assertIn("путает названия еды", report)
        self.assertIn("cheese и eggs", report)
        self.assertIn(
            "Несколько ошибок показывают, что ребёнок не помнит часть слов по теме еды",
            report,
        )
        self.assertNotIn("не усвоил всю лексику", report)
        self.assert_parent_safe(report)

    def test_same_score_with_different_selected_answers_produces_different_diagnosis(self):
        first_errors = {
            3: "DOLL_BALL",
            5: "COMPARATIVE_FORM",
            7: "SOME_ANY_QUESTION",
            9: "PAST_GO_WENT",
            10: "PAST_DID_BASE_FORM",
            15: "PRESENT_SIMPLE_3SG",
            18: "CHEESE_EGGS",
        }
        second_errors = {
            1: "HIS_HER",
            2: "BE_HAVE_CONFUSION",
            6: "SUPERLATIVE_FORM",
            11: "WAS_WERE",
            12: "THERE_WAS_WERE_NUMBER",
            13: "TAKE_FEED",
            14: "MUST_BASE_VERB",
        }
        first = self.ai_report.fallback_report(summary_for("3-4", first_errors, first_errors))
        second = self.ai_report.fallback_report(summary_for("3-4", second_errors, second_errors))
        self.assertIn("13 из 20", first)
        self.assertIn("13 из 20", second)
        self.assertNotEqual(first, second)
        self.assertIn("doll и ball", first)
        self.assertIn("his и her", second)
        self.assertIn("was и were", second)

    def test_validator_rejects_frankenstein_semantic_repetition(self):
        repeated = (
            "Ребёнок понимает многие проверенные темы, но пока ошибается в нескольких из них. "
            "Есть ошибки в нескольких темах. Ребёнок ошибается в нескольких темах."
        )
        self.assertTrue(self.ai_report.has_semantic_repetition(repeated))

    def test_teacher_stub_uses_new_parent_report_structure(self):
        report = self.ai_report.teacher_stub(summary_for("3-4", {1, 2, 9, 10, 11}))
        self.assertIn("3–4 класс", report)
        self.assertIn("значительную часть проверенного материала", report)
        self.assertIn("базу за 1–2 класс", report)
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
