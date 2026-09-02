from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.fake_vk import install

install()

import bot  # noqa: E402
from question_sets import QUESTION_SETS  # noqa: E402
from session_store import SessionStore  # noqa: E402


class BotFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        bot.SESSION_STORE = SessionStore(Path(self.temp.name) / "sessions.sqlite3")
        bot.SESSIONS.clear()
        self.messages = []
        bot.send = lambda user_id, text, keyboard=None, attachment=None, random_id=None: self.messages.append({
            "user_id": user_id,
            "text": text,
            "keyboard": keyboard,
            "attachment": attachment,
            "random_id": random_id,
        }) or 1
        bot.upload_photo = lambda _path: "photo1_1"
        bot.update_subscriber = lambda _user_id, **_updates: None
        bot.generate_parent_report = lambda _user_id, summary: f"REPORT {summary['route']}"
        bot.build_trial_lesson_link = lambda _emeralds: "https://example.com/trial"

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _label_for_original_option(session, question, option_index):
        displayed_index = session["option_orders"][question["id"]].index(option_index)
        return "ABC"[displayed_index]

    def run_route(self, route, mode, user_id):
        session = bot.blank_session()
        session["class"] = route
        session["stage"] = "question"
        bot.SESSIONS[user_id] = session
        bot.send_question(user_id)
        first_order = list(session["option_orders"][1])
        bot.send_question(user_id)
        self.assertEqual(first_order, session["option_orders"][1])

        for index, question in enumerate(QUESTION_SETS[route]):
            want_correct = mode == "correct" or (mode == "mixed" and index % 2 == 0)
            original_index = next(
                option_index for option_index, option in enumerate(question["options"])
                if bool(option.get("correct")) is want_correct
            )
            label = self._label_for_original_option(session, question, original_index)
            bot.handle_answer(user_id, label)

        self.assertEqual("shop", session["stage"])
        self.assertEqual(list(range(1, 21)), [answer["question_id"] for answer in session["answers"]])
        return session

    def test_all_routes_correct_incorrect_and_mixed(self):
        expected = {"correct": (20, 40), "incorrect": (0, 20), "mixed": (10, 30)}
        user_id = 100
        for route in QUESTION_SETS:
            for mode, (correct_total, emeralds) in expected.items():
                user_id += 1
                session = self.run_route(route, mode, user_id)
                summary = bot.build_summary(session)
                with self.subTest(route=route, mode=mode):
                    self.assertEqual(correct_total, summary["correct_total"])
                    self.assertEqual(emeralds, session["emeralds"])
                    self.assertEqual(20, summary["total_questions"])

    def test_shop_parent_report_and_cta_still_work(self):
        user_id = 500
        session = self.run_route("1-2", "correct", user_id)
        for _category in bot.SHOP_CATEGORIES:
            bot.handle_shop_choice(user_id, "1. first")
        self.assertEqual("await_parent", session["stage"])
        bot.send_parent_report(user_id)
        self.assertEqual("done", session["stage"])
        self.assertTrue(session["completed"])
        self.assertTrue(any(message["text"].startswith("REPORT") for message in self.messages))
        self.assertTrue(any("пробный урок" in message["text"] for message in self.messages))

    def test_due_reminders_resume_current_question_and_survive_restart(self):
        user_id = 700
        session = bot.blank_session()
        session.update({
            "class": "3-4",
            "stage": "question",
            "question_index": 5,
            "answers": [{"question_id": 1, "correct": True}],
            "emeralds": 2,
            "last_activity_at": datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc).isoformat(),
        })
        session["option_orders"][6] = [2, 0, 1]
        bot.SESSIONS[user_id] = session
        bot.REMINDER_DELAYS = (1, 2, 3)
        base = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)

        self.assertEqual(1, bot.run_due_reminders(base + timedelta(seconds=1)))
        self.assertEqual(1, session["reminders_sent"])
        self.assertIn("15 вопросов", self.messages[-1]["text"])
        first_random_id = self.messages[-1]["random_id"]
        self.assertEqual(0, bot.run_due_reminders(base + timedelta(seconds=1)))

        session["last_activity_at"] = (base + timedelta(seconds=10)).isoformat()
        self.assertEqual(1, bot.run_due_reminders(base + timedelta(seconds=12)))
        session["last_activity_at"] = (base + timedelta(seconds=20)).isoformat()
        self.assertEqual(1, bot.run_due_reminders(base + timedelta(seconds=23)))
        self.assertEqual(3, session["reminders_sent"])
        self.assertEqual(0, bot.run_due_reminders(base + timedelta(days=1)))

        restored = SessionStore(Path(self.temp.name) / "sessions.sqlite3").load_all()[user_id]
        self.assertEqual(5, restored["question_index"])
        self.assertEqual([2, 0, 1], restored["option_orders"][6])
        self.assertEqual(2, restored["emeralds"])
        self.assertEqual(3, restored["reminders_sent"])
        self.assertEqual(first_random_id, bot.reminder_random_id(restored["session_id"], 1))

        bot.SESSIONS[user_id] = restored
        bot.on_message(user_id, "Закончить тест")
        self.assertEqual(5, restored["question_index"])
        self.assertEqual([2, 0, 1], restored["option_orders"][6])


if __name__ == "__main__":
    unittest.main()
