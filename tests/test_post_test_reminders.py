from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.fake_vk import install

install()

import bot  # noqa: E402
from session_store import SessionStore  # noqa: E402


class PostTestReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "sessions.sqlite3"
        bot.SESSION_STORE = SessionStore(self.db_path)
        bot.SUBSCRIBERS_CSV_PATH = Path(self.temp.name) / "subscribers.csv"
        bot.SESSIONS.clear()
        self.messages = []
        bot.send = lambda user_id, text, keyboard=None, attachment=None, random_id=None: self.messages.append({
            "user_id": user_id,
            "text": text,
            "keyboard": keyboard,
            "attachment": attachment,
            "random_id": random_id,
        }) or 1
        self.original_reminder_delays = bot.REMINDER_DELAYS

    def tearDown(self):
        bot.REMINDER_DELAYS = self.original_reminder_delays
        self.temp.cleanup()

    @staticmethod
    def _actions(message):
        return message["keyboard"].actions if message["keyboard"] else []

    def test_unfinished_test_receives_only_existing_reminders(self):
        base = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
        session = bot.blank_session()
        session.update({
            "stage": "question",
            "class": "3-4",
            "question_index": 4,
            "answers": [{"question_id": 1}],
            "last_activity_at": base.isoformat(),
            "completed": False,
            "post_test_completed_at": base.isoformat(),
        })
        bot.SESSIONS[701] = session
        bot.REMINDER_DELAYS = (1, 2, 3)

        self.assertEqual(0, bot.run_due_post_test_reminders(base + timedelta(days=2)))
        self.assertEqual(1, bot.run_due_reminders(base + timedelta(seconds=1)))
        self.assertEqual(1, session["reminders_sent"])
        self.assertIn("Продолжить тест", [action[1] for action in self._actions(self.messages[-1])])

    def test_completed_test_receives_three_exact_persistent_reminders(self):
        base = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
        session = bot.blank_session()
        session.update({
            "stage": "done",
            "class": "5-6",
            "question_index": 20,
            "answers": [{"question_id": question_id} for question_id in range(1, 21)],
            "last_activity_at": (base - timedelta(days=2)).isoformat(),
            "completed": True,
            "post_test_completed_at": base.isoformat(),
            "post_test_reminders_sent": 0,
        })
        bot.SESSIONS[702] = session
        bot.persist_session(702)
        bot.REMINDER_DELAYS = (1, 2, 3)

        self.assertEqual(0, bot.run_due_reminders(base + timedelta(days=2)))
        self.assertEqual(0, bot.run_due_post_test_reminders(base + timedelta(minutes=19, seconds=59)))

        self.assertEqual(1, bot.run_due_post_test_reminders(base + timedelta(minutes=20)))
        self.assertEqual(bot.POST_TEST_REMINDERS[0][0], self.messages[-1]["text"])
        self.assertIn(("button", "Забрать подарок", "primary"), self._actions(self.messages[-1]))

        bot.on_message(702, "Забрать подарок")
        self.assertEqual("Для какого класса выбрать подарок?", self.messages[-1]["text"])
        self.assertEqual("gift_class", session["stage"])

        self.assertEqual(1, bot.run_due_post_test_reminders(base + timedelta(hours=3)))
        self.assertEqual(bot.POST_TEST_REMINDERS[1][0], self.messages[-1]["text"])
        self.assertIn(
            ("openlink", "Записаться на пробный", "https://vk.me/ellie_englie"),
            self._actions(self.messages[-1]),
        )

        self.assertEqual(1, bot.run_due_post_test_reminders(base + timedelta(hours=24)))
        self.assertEqual(bot.POST_TEST_REMINDERS[2][0], self.messages[-1]["text"])
        self.assertIn(
            ("openlink", "Записаться на пробный", "https://vk.me/ellie_englie"),
            self._actions(self.messages[-1]),
        )
        self.assertEqual(3, session["post_test_reminders_sent"])
        self.assertEqual(0, bot.run_due_post_test_reminders(base + timedelta(days=30)))

        restored = SessionStore(self.db_path).load_all()[702]
        self.assertEqual(3, restored["post_test_reminders_sent"])
        bot.SESSIONS[702] = restored
        self.assertEqual(0, bot.run_due_post_test_reminders(base + timedelta(days=31)))

    def test_parent_report_starts_post_test_clock_only_after_result_is_sent(self):
        base = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
        session = bot.blank_session()
        session.update({"stage": "await_parent", "class": "1-2", "question_index": 20})
        bot.SESSIONS[703] = session
        bot.build_summary = lambda _session: {"route": "1-2"}
        bot.generate_parent_report = lambda _user_id, _summary: "Готовый результат"
        original_utc_now = bot.utc_now
        bot.utc_now = lambda: base.isoformat()
        try:
            bot.send_parent_report(703)
        finally:
            bot.utc_now = original_utc_now

        report_index = next(index for index, message in enumerate(self.messages) if message["text"] == "Готовый результат")
        self.assertLess(report_index, len(self.messages) - 1)
        self.assertTrue(session["completed"])
        self.assertEqual(base.isoformat(), session["post_test_completed_at"])
        self.assertEqual(0, session["post_test_reminders_sent"])
        restored = SessionStore(self.db_path).load_all()[703]
        self.assertEqual(base.isoformat(), restored["post_test_completed_at"])


if __name__ == "__main__":
    unittest.main()
