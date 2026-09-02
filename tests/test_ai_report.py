from __future__ import annotations

import importlib
import os
import sys
import types
import unittest

from diagnostics import build_summary
from question_sets import QUESTION_SETS


class FakeResponse:
    @staticmethod
    def raise_for_status():
        return None

    @staticmethod
    def json():
        return {"choices": [{"message": {"content": "Короткий обезличенный отчёт."}}]}


class FakeRequests(types.ModuleType):
    class HTTPError(Exception):
        pass

    def __init__(self):
        super().__init__("requests")
        self.payload = None

    def post(self, _url, headers=None, json=None, timeout=None):
        self.payload = json
        return FakeResponse()


def summary_for(route):
    answers = []
    for question in QUESTION_SETS[route]:
        correct = next(option for option in question["options"] if option.get("correct"))
        answers.append({
            "question_id": question["id"],
            "topic": question["topic"],
            "topic_ru": question["topic_ru"],
            "question": question["question"],
            "selected_text": correct["text"],
            "correct_text": correct["text"],
            "correct": True,
            "meaning": None,
        })
    return build_summary({"class": route, "answers": answers, "emeralds": 40})


class AiReportTests(unittest.TestCase):
    def test_reports_support_all_routes_and_payload_is_deidentified(self):
        fake_requests = FakeRequests()
        previous_requests = sys.modules.get("requests")
        sys.modules["requests"] = fake_requests
        previous_env = {name: os.environ.get(name) for name in ("AI_API_URL", "AI_API_KEY", "AI_MODEL")}
        os.environ.update({
            "AI_API_URL": "https://example.invalid/chat/completions",
            "AI_API_KEY": "test-key",
            "AI_MODEL": "test-model",
        })
        try:
            if "ai_report" in sys.modules:
                del sys.modules["ai_report"]
            ai_report = importlib.import_module("ai_report")
            for route in QUESTION_SETS:
                summary = summary_for(route)
                report = ai_report.generate_parent_report(999999, summary)
                with self.subTest(route=route):
                    self.assertEqual("Короткий обезличенный отчёт.", report)
                    self.assertEqual(route in {"1-2", "3-4", "5-6"}, True)
                    serialized = str(fake_requests.payload)
                    self.assertNotIn("vk_id", serialized)
                    self.assertNotIn("phone", serialized.lower())
                    self.assertNotIn("email", serialized.lower())
                    self.assertIn(summary["route"], serialized)
        finally:
            if previous_requests is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = previous_requests
            for name, value in previous_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
