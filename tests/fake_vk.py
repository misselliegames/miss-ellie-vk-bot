from __future__ import annotations

import os
import sys
import tempfile
import types


def install():
    vk_api_module = types.ModuleType("vk_api")
    bot_longpoll_module = types.ModuleType("vk_api.bot_longpoll")
    keyboard_module = types.ModuleType("vk_api.keyboard")
    requests_module = types.ModuleType("requests")

    class FakeGroups:
        @staticmethod
        def getById():
            return [{"id": 1}]

    class FakeUtils:
        @staticmethod
        def resolveScreenName(**_kwargs):
            return {"type": "user", "object_id": 1}

    class FakeUsers:
        @staticmethod
        def get(**_kwargs):
            return [{"id": 1}]

    class FakeMessages:
        @staticmethod
        def send(**_kwargs):
            return 1

    class FakeApi:
        groups = FakeGroups()
        utils = FakeUtils()
        users = FakeUsers()
        messages = FakeMessages()

    class FakeVkApi:
        def __init__(self, token):
            self.token = token

        @staticmethod
        def get_api():
            return FakeApi()

    class FakeUpload:
        def __init__(self, _session):
            pass

        @staticmethod
        def photo_messages(**_kwargs):
            return [{"owner_id": 1, "id": 1}]

    class FakeLongPoll:
        def __init__(self, *_args):
            pass

        @staticmethod
        def listen():
            return []

    class FakeEventType:
        MESSAGE_NEW = "message_new"

    class FakeKeyboardColor:
        PRIMARY = "primary"
        POSITIVE = "positive"
        SECONDARY = "secondary"

    class FakeKeyboard:
        def __init__(self, one_time=True):
            self.one_time = one_time
            self.actions = []

        def add_button(self, label, color=None):
            self.actions.append(("button", label, color))

        def add_line(self):
            self.actions.append(("line",))

        def add_openlink_button(self, label, link):
            self.actions.append(("openlink", label, link))

        def get_keyboard(self):
            return "{}"

    vk_api_module.VkApi = FakeVkApi
    vk_api_module.VkUpload = FakeUpload
    bot_longpoll_module.VkBotLongPoll = FakeLongPoll
    bot_longpoll_module.VkBotEventType = FakeEventType
    keyboard_module.VkKeyboard = FakeKeyboard
    keyboard_module.VkKeyboardColor = FakeKeyboardColor
    class FakeRequestError(Exception):
        pass

    requests_module.exceptions = types.SimpleNamespace(
        ReadTimeout=FakeRequestError,
        ConnectionError=FakeRequestError,
    )
    requests_module.post = lambda *_args, **_kwargs: None
    sys.modules["vk_api"] = vk_api_module
    sys.modules["vk_api.bot_longpoll"] = bot_longpoll_module
    sys.modules["vk_api.keyboard"] = keyboard_module
    sys.modules["requests"] = requests_module

    os.environ.setdefault("VK_TOKEN", "test-token")
    os.environ["SESSION_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "import-sessions.sqlite3")
