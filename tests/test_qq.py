import unittest
import time

from bili_osu_bridge.qq import QQBotClient


class QQBotTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.client = QQBotClient(
            object(),
            "app-id",
            "app-secret",
            self.messages.append,
            allowed_group_openids=("allowed-group",),
        )

    def test_accepts_allowed_group_and_deduplicates_message(self):
        event = {
            "id": "message-1",
            "group_openid": "allowed-group",
            "content": "点歌 123456",
            "author": {
                "member_openid": "member-1",
                "nickname": "QQ Viewer",
                "avatar": "https://q.qlogo.cn/test.jpg",
                "bot": False,
            },
        }

        self.client._handle_message_event("GROUP_AT_MESSAGE_CREATE", event)
        self.client._handle_message_event("GROUP_AT_MESSAGE_CREATE", event)

        self.assertEqual(len(self.messages), 1)
        message = self.messages[0]
        self.assertEqual(message.source, "qq")
        self.assertEqual(message.user_id, "member-1")
        self.assertEqual(message.username, "QQ Viewer")
        self.assertEqual(message.content, "点歌 123456")
        self.assertEqual(message.avatar_url, "https://q.qlogo.cn/test.jpg")
        self.assertEqual(message.scope_id, "allowed-group")
        self.assertFalse(message.is_private)
        self.assertEqual(message.user_key, "qq:member-1")
        self.assertIsNotNone(message.reply)

    def test_group_allowlist_does_not_block_private_message(self):
        self.client._handle_message_event(
            "GROUP_AT_MESSAGE_CREATE",
            {
                "id": "blocked",
                "group_openid": "another-group",
                "content": "123456",
                "author": {"member_openid": "member-2", "username": "Blocked"},
            },
        )
        self.client._handle_message_event(
            "C2C_MESSAGE_CREATE",
            {
                "id": "private",
                "content": "654321",
                "author": {"user_openid": "user-1", "username": "Private"},
            },
        )

        self.assertEqual(len(self.messages), 1)
        self.assertEqual(self.messages[0].user_id, "user-1")
        self.assertEqual(self.messages[0].content, "654321")
        self.assertTrue(self.messages[0].is_private)

    def test_ignores_messages_from_bots(self):
        self.client._handle_message_event(
            "C2C_MESSAGE_CREATE",
            {
                "id": "bot-message",
                "content": "123",
                "author": {"id": "bot", "username": "Robot", "bot": True},
            },
        )
        self.assertEqual(self.messages, [])


class _ReplyResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def text(self):
        return "{}"


class _ReplySession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _ReplyResponse()


class QQReplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_group_reply_uses_official_endpoint_and_original_message(self):
        session = _ReplySession()
        client = QQBotClient(session, "app-id", "secret", lambda _message: None)
        client._access_token = "token"
        client._access_token_expires_at = time.monotonic() + 60

        await client._send_reply(
            group_openid="group-id",
            user_openid="member-id",
            message_id="message-id",
            content="点歌推送成功",
        )

        url, request = session.calls[0]
        self.assertEqual(
            url,
            "https://api.sgroup.qq.com/v2/groups/group-id/messages",
        )
        self.assertEqual(request["json"]["msg_id"], "message-id")
        self.assertEqual(request["json"]["content"], "点歌推送成功")
        self.assertEqual(request["headers"]["Authorization"], "QQBot token")


if __name__ == "__main__":
    unittest.main()
