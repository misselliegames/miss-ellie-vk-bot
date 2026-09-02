from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from diagnostics import build_summary
from question_sets import QUESTION_ASSET_SUBDIRS, QUESTION_SETS


ROOT = Path(__file__).resolve().parents[1]


def make_answers(route, mode):
    answers = []
    emeralds = 0
    for index, question in enumerate(QUESTION_SETS[route]):
        want_correct = mode == "correct" or (mode == "mixed" and index % 2 == 0)
        option = next(
            option for option in question["options"]
            if bool(option.get("correct")) is want_correct
        )
        correct = bool(option.get("correct"))
        emeralds += 2 if correct else 1
        correct_option = next(option for option in question["options"] if option.get("correct"))
        answers.append({
            "question_id": question["id"],
            "topic": question["topic"],
            "topic_ru": question["topic_ru"],
            "question": question["question"],
            "selected_text": option["text"],
            "correct_text": correct_option["text"],
            "correct": correct,
            "error": option.get("error"),
            "meaning": option.get("meaning"),
        })
    return answers, emeralds


class RouteDataTests(unittest.TestCase):
    def test_question_contract_for_all_routes(self):
        for route, questions in QUESTION_SETS.items():
            with self.subTest(route=route):
                self.assertEqual(20, len(questions))
                self.assertEqual(list(range(1, 21)), [question["id"] for question in questions])
                self.assertEqual(20, len({question["image"] for question in questions}))
                for question in questions:
                    self.assertEqual(3, len(question["options"]))
                    self.assertEqual(1, sum(bool(option.get("correct")) for option in question["options"]))
                    for option in question["options"]:
                        if not option.get("correct"):
                            self.assertTrue(option.get("meaning"))

    def test_route_assets_exist_and_open(self):
        for route, questions in QUESTION_SETS.items():
            subdir = QUESTION_ASSET_SUBDIRS[route]
            for question in questions:
                path = ROOT / "assets" / "questions" / subdir / question["image"] if subdir else ROOT / "assets" / "questions" / question["image"]
                with self.subTest(route=route, question=question["id"], path=str(path)):
                    self.assertTrue(path.exists())
                    with Image.open(path) as image:
                        image.verify()

    def test_correct_incorrect_and_mixed_summaries(self):
        expected = {
            "correct": (20, 40),
            "incorrect": (0, 20),
            "mixed": (10, 30),
        }
        for route in QUESTION_SETS:
            for mode, (correct_total, emeralds) in expected.items():
                answers, actual_emeralds = make_answers(route, mode)
                session = {"class": route, "answers": answers, "emeralds": actual_emeralds}
                summary = build_summary(session)
                with self.subTest(route=route, mode=mode):
                    self.assertEqual(correct_total, summary["correct_total"])
                    self.assertEqual(emeralds, summary["emeralds"])
                    self.assertEqual(20, summary["total_questions"])
                    self.assertEqual(20, sum(topic["max"] for topic in summary["topics"]))
                    if mode == "incorrect":
                        self.assertTrue(all(answer["error"] for answer in summary["answers"]))


if __name__ == "__main__":
    unittest.main()
