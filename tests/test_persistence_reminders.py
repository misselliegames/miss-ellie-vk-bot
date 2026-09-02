from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reminders import due_reminder_index, reminder_random_id, render_reminder
from session_store import SessionStore


class PersistenceReminderTests(unittest.TestCase):
    def test_session_round_trip_preserves_progress_and_option_order(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "sessions.sqlite3")
            session = {
                "session_id": "abc",
                "stage": "question",
                "class": "5-6",
                "question_index": 7,
                "answers": [{"question_id": 7, "correct": True}],
                "emeralds": 11,
                "option_orders": {8: [2, 0, 1]},
                "world_intros_sent": {1, 4, 6},
                "last_activity_at": "2026-09-02T10:00:00+00:00",
                "reminders_sent": 2,
                "completed": False,
            }
            store.save(123, session)
            restored = SessionStore(Path(directory) / "sessions.sqlite3").load_all()[123]
            self.assertEqual("5-6", restored["class"])
            self.assertEqual(7, restored["question_index"])
            self.assertEqual(11, restored["emeralds"])
            self.assertEqual([2, 0, 1], restored["option_orders"][8])
            self.assertEqual({1, 4, 6}, restored["world_intros_sent"])
            self.assertEqual(2, restored["reminders_sent"])

    def test_three_reminders_are_relative_to_latest_activity(self):
        base = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
        delays = (20 * 60, 3 * 60 * 60, 24 * 60 * 60)
        session = {
            "stage": "question",
            "answers": [{"question_id": 1}],
            "completed": False,
            "last_activity_at": base.isoformat(),
            "reminders_sent": 0,
        }
        self.assertIsNone(due_reminder_index(session, base + timedelta(minutes=19), delays))
        self.assertEqual(0, due_reminder_index(session, base + timedelta(minutes=20), delays))
        session["reminders_sent"] = 1
        session["last_activity_at"] = (base + timedelta(hours=1)).isoformat()
        self.assertIsNone(due_reminder_index(session, base + timedelta(hours=3, minutes=59), delays))
        self.assertEqual(1, due_reminder_index(session, base + timedelta(hours=4), delays))
        session["reminders_sent"] = 2
        session["last_activity_at"] = (base + timedelta(hours=5)).isoformat()
        self.assertEqual(2, due_reminder_index(session, base + timedelta(hours=29), delays))
        session["reminders_sent"] = 3
        self.assertIsNone(due_reminder_index(session, base + timedelta(days=10), delays))

    def test_reminders_stop_outside_question_phase(self):
        now = datetime.now(timezone.utc)
        session = {
            "stage": "shop",
            "answers": [{"question_id": 1}],
            "completed": False,
            "last_activity_at": (now - timedelta(days=2)).isoformat(),
            "reminders_sent": 0,
        }
        self.assertIsNone(due_reminder_index(session, now, (1, 2, 3)))
        session["stage"] = "question"
        session["completed"] = True
        self.assertIsNone(due_reminder_index(session, now, (1, 2, 3)))

    def test_rendered_text_and_vk_random_id_are_stable(self):
        text, button = render_reminder(0, 13)
        self.assertIn("13 вопросов", text)
        self.assertEqual("Продолжить тест", button)
        self.assertEqual(reminder_random_id("session", 1), reminder_random_id("session", 1))
        self.assertNotEqual(reminder_random_id("session", 1), reminder_random_id("session", 2))


if __name__ == "__main__":
    unittest.main()
