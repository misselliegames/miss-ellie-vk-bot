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

    @staticmethod
    def _keyboard_actions(message):
        keyboard = message["keyboard"]
        return keyboard.actions if keyboard else []

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
        final_actions = self._keyboard_actions(self.messages[-1])
        self.assertEqual(
            [
                ("button", bot.FINAL_TRIAL_LABEL, "positive"),
                ("button", bot.GIFTS_LABEL, "secondary"),
                ("button", bot.REVIEWS_LABEL, "secondary"),
                ("button", bot.RESTART_LABEL, "secondary"),
            ],
            [action for action in final_actions if action[0] != "line"],
        )
        self.assertNotIn(
            bot.MAIN_MENU_LABEL,
            [action[1] for action in final_actions if action[0] == "button"],
        )

        bot.on_message(user_id, bot.FINAL_TRIAL_LABEL)
        self.assertIn(bot.TRIAL_URL, self.messages[-1]["text"])

    def test_new_user_follows_approved_start_consent_and_class_flow(self):
        user_id = 600
        bot.on_message(user_id, "старт")
        session = bot.SESSIONS[user_id]
        self.assertEqual("welcome", session["stage"])
        self.assertEqual(bot.TEST_WELCOME_TEXT, self.messages[-1]["text"])
        self.assertIn(
            ("button", bot.TEST_START_LABEL, "positive"),
            self._keyboard_actions(self.messages[-1]),
        )

        bot.on_message(user_id, bot.TEST_START_LABEL)
        session = bot.SESSIONS[user_id]
        self.assertEqual("await_pd_consent", session["stage"])
        self.assertTrue(self.messages[-1]["text"].startswith(
            "Ура! Вы добрались до ворот Изумрудного Города 💚 Элли хлопает в ладоши и очень рада вас видеть.\n\n"
            "Но даже здесь есть пара волшебных бумажек — обычная бюрократия."
        ))

        bot.on_message(user_id, "Согласен(на), идём дальше")
        self.assertTrue(session["pd_consent"])
        self.assertEqual("await_marketing_consent", session["stage"])
        bot.on_message(user_id, "Нет, спасибо")
        self.assertFalse(session["marketing_consent"])
        self.assertEqual("await_class", session["stage"])
        self.assertEqual(bot.CLASS_SELECTION_TEXT, self.messages[-1]["text"])

        bot.on_message(user_id, "3–4 класс")
        self.assertEqual("3-4", session["class"])
        self.assertEqual("await_handoff", session["stage"])
        bot.on_message(user_id, "Да")
        self.assertEqual("await_go", session["stage"])
        bot.on_message(user_id, "Вперёд!")
        self.assertEqual("question", session["stage"])
        self.assertIn("Задание 1/20", self.messages[-1]["text"])

    def test_main_menu_has_exact_four_actions_and_links(self):
        user_id = 610
        bot.show_main_menu(user_id)
        actions = self._keyboard_actions(self.messages[-1])
        self.assertEqual(
            [
                ("button", bot.TEST_MENU_LABEL, "positive"),
                ("button", bot.GIFTS_LABEL, "primary"),
                ("openlink", bot.REVIEWS_LABEL, bot.REVIEWS_URL),
                ("openlink", bot.TRIAL_LABEL, bot.TRIAL_URL),
            ],
            [action for action in actions if action[0] != "line"],
        )

    def test_navigation_does_not_skip_unanswered_marketing_consent(self):
        user_id = 615
        bot.on_message(user_id, "старт")
        bot.on_message(user_id, bot.TEST_START_LABEL)
        bot.on_message(user_id, "Согласен(на), идём дальше")
        session = bot.SESSIONS[user_id]
        self.assertEqual("await_marketing_consent", session["stage"])

        bot.on_message(user_id, bot.GIFTS_LABEL)
        bot.on_message(user_id, "3–4 класс")
        self.assertEqual("await_marketing_consent", session["stage"])
        bot.on_message(user_id, bot.MAIN_MENU_LABEL)
        bot.on_message(user_id, bot.TEST_MENU_LABEL)
        bot.on_message(user_id, bot.TEST_START_LABEL)

        self.assertEqual("await_marketing_consent", session["stage"])
        self.assertIn("Хотите иногда получать", self.messages[-1]["text"])

    def test_gifts_are_selected_independently_and_all_six_links_are_exact(self):
        user_id = 620
        session = bot.blank_session()
        session.update({"stage": "done", "completed": True, "pd_consent": True, "class": "5-6"})
        bot.SESSIONS[user_id] = session

        expected_urls = set()
        for label, route in (("1–2 класс", "1-2"), ("3–4 класс", "3-4"), ("5–6 класс", "5-6")):
            bot.on_message(user_id, bot.GIFTS_LABEL)
            self.assertEqual("Для какого класса выбрать подарок?", self.messages[-1]["text"])
            bot.on_message(user_id, label)
            gift_message = self.messages[-1]
            gifts = bot.GIFT_OPTIONS[route]
            self.assertEqual("\n\n".join(item[0] for item in gifts), gift_message["text"])
            links = [action[2] for action in self._keyboard_actions(gift_message) if action[0] == "openlink"]
            self.assertEqual([item[2] for item in gifts], links)
            self.assertEqual("5-6", session["class"])
            expected_urls.update(links)

        self.assertEqual(
            {
                "https://misselliegames.github.io/read-and-shoot/",
                "https://misselliegames.github.io/ReadingLoadBoat/",
                "https://misselliegames.github.io/GrammarDungeon/",
                "https://view.genially.com/68aacd3b7eb807e23b78c9f9",
                "https://misselliegames.github.io/TintinExpedition/",
                "https://view.genially.com/6880daeca1dc1c756166020b",
            },
            expected_urls,
        )
        bot.on_message(user_id, bot.MAIN_MENU_LABEL)
        self.assertEqual("main_menu", session["stage"])
        self.assertEqual("Главное меню", self.messages[-1]["text"])

    def test_restart_skips_welcome_and_consents_and_clears_old_result(self):
        user_id = 630
        old_session = bot.blank_session()
        old_session.update({
            "stage": "done",
            "completed": True,
            "pd_consent": True,
            "marketing_consent": False,
            "class": "3-4",
            "question_index": 20,
            "answers": [{"question_id": 1, "correct": True}],
            "emeralds": 35,
            "option_orders": {1: [2, 0, 1]},
            "shop_selected": {"house": "house_08_small"},
        })
        old_session_id = old_session["session_id"]
        bot.SESSIONS[user_id] = old_session

        bot.on_message(user_id, bot.RESTART_LABEL)
        new_session = bot.SESSIONS[user_id]
        self.assertNotEqual(old_session_id, new_session["session_id"])
        self.assertEqual("await_class", new_session["stage"])
        self.assertEqual(bot.CLASS_SELECTION_TEXT, self.messages[-1]["text"])
        self.assertEqual("", new_session["class"])
        self.assertEqual(0, new_session["question_index"])
        self.assertEqual(0, new_session["emeralds"])
        self.assertEqual([], new_session["answers"])
        self.assertEqual({}, new_session["option_orders"])
        self.assertEqual({}, new_session["shop_selected"])
        self.assertTrue(new_session["pd_consent"])
        self.assertFalse(new_session["marketing_consent"])
        self.assertFalse(new_session["completed"])
        restored = bot.SESSION_STORE.load_all()[user_id]
        self.assertEqual("await_class", restored["stage"])
        self.assertEqual([], restored["answers"])
        self.assertTrue(restored["pd_consent"])

        message_count = len(self.messages)
        bot.on_message(user_id, "не тот класс")
        self.assertEqual(message_count + 1, len(self.messages))
        self.assertEqual(bot.CLASS_SELECTION_TEXT, self.messages[-1]["text"])

    def test_start_menu_and_gifts_do_not_destroy_unfinished_test(self):
        user_id = 640
        session = bot.blank_session()
        session.update({
            "stage": "question",
            "class": "5-6",
            "question_index": 5,
            "answers": [{"question_id": 1, "correct": True}],
            "emeralds": 2,
            "pd_consent": True,
        })
        bot.SESSIONS[user_id] = session

        bot.on_message(user_id, "тест")
        self.assertEqual("question", session["stage"])
        self.assertEqual(5, session["question_index"])
        self.assertEqual(bot.TEST_WELCOME_TEXT, self.messages[-1]["text"])
        bot.on_message(user_id, bot.TEST_START_LABEL)
        self.assertEqual("question", session["stage"])
        self.assertEqual(5, session["question_index"])
        self.assertEqual(2, session["emeralds"])
        self.assertIn("Задание 6/20", self.messages[-1]["text"])
        self.assertIn(
            ("button", bot.MAIN_MENU_LABEL, "secondary"),
            self._keyboard_actions(self.messages[-1]),
        )

        bot.on_message(user_id, bot.MAIN_MENU_LABEL)
        self.assertEqual("question", session["stage"])
        self.assertEqual(5, session["question_index"])
        self.assertEqual("Главное меню", self.messages[-1]["text"])
        self.assertEqual(
            [bot.CONTINUE_TEST_LABEL, bot.GIFTS_LABEL],
            [action[1] for action in self._keyboard_actions(self.messages[-1]) if action[0] == "button"],
        )

        restored = bot.SESSION_STORE.load_all()[user_id]
        self.assertEqual("question", restored["stage"])
        self.assertEqual(5, restored["question_index"])
        self.assertEqual(2, restored["emeralds"])
        self.assertEqual(session["answers"], restored["answers"])

        bot.on_message(user_id, bot.CONTINUE_TEST_LABEL)
        self.assertEqual("question", session["stage"])
        self.assertEqual(5, session["question_index"])
        self.assertEqual(2, session["emeralds"])
        self.assertIn("Задание 6/20", self.messages[-1]["text"])

        bot.on_message(user_id, bot.GIFTS_LABEL)
        self.assertEqual("question", session["stage"])
        self.assertEqual("Для какого класса выбрать подарок?", self.messages[-1]["text"])
        bot.on_message(user_id, "1–2 класс")
        self.assertEqual("question", session["stage"])
        self.assertIn(bot.GIFT_OPTIONS["1-2"][0][0], self.messages[-1]["text"])
        self.assertEqual(5, session["question_index"])
        self.assertEqual(2, session["emeralds"])

        bot.on_message(user_id, bot.MAIN_MENU_LABEL)
        bot.on_message(user_id, bot.TEST_MENU_LABEL)
        bot.on_message(user_id, bot.TEST_START_LABEL)
        self.assertEqual("question", session["stage"])
        self.assertEqual(5, session["question_index"])
        self.assertIn("Задание 6/20", self.messages[-1]["text"])

    def test_main_menu_resume_survives_session_reload(self):
        user_id = 645
        session = bot.blank_session()
        session.update({
            "stage": "question",
            "class": "3-4",
            "question_index": 8,
            "answers": [
                {"question_id": question_id, "correct": question_id % 2 == 0}
                for question_id in range(1, 9)
            ],
            "emeralds": 12,
            "pd_consent": True,
        })
        session["option_orders"][9] = [2, 0, 1]
        bot.SESSIONS[user_id] = session

        bot.on_message(user_id, bot.MAIN_MENU_LABEL)
        self.assertIn(
            ("button", bot.CONTINUE_TEST_LABEL, "positive"),
            self._keyboard_actions(self.messages[-1]),
        )

        bot.SESSIONS.clear()
        bot.SESSIONS.update(bot.SESSION_STORE.load_all())
        restored = bot.SESSIONS[user_id]
        bot.on_message(user_id, bot.CONTINUE_TEST_LABEL)

        self.assertEqual("question", restored["stage"])
        self.assertEqual(8, restored["question_index"])
        self.assertEqual(12, restored["emeralds"])
        self.assertEqual(8, len(restored["answers"]))
        self.assertEqual([2, 0, 1], restored["option_orders"][9])
        self.assertIn("Задание 9/20", self.messages[-1]["text"])

    def test_legacy_saved_consent_also_skips_legal_steps_on_restart(self):
        user_id = 650
        bot.SUBSCRIBERS_CSV_PATH.write_text(
            "vk_id,pd_consent,marketing_consent\n650,true,false\n",
            encoding="utf-8",
        )
        session = bot.blank_session()
        session.pop("pd_consent")
        session.pop("marketing_consent")
        session.update({"stage": "done", "completed": True})
        bot.SESSIONS[user_id] = session

        bot.on_message(user_id, bot.RESTART_LABEL)
        restarted = bot.SESSIONS[user_id]
        self.assertEqual("await_class", restarted["stage"])
        self.assertEqual(bot.CLASS_SELECTION_TEXT, self.messages[-1]["text"])
        self.assertTrue(restarted["pd_consent"])
        self.assertFalse(restarted["marketing_consent"])

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
