import unittest
from unittest.mock import AsyncMock, patch

from bili_osu_bridge.bili_login import generate_qr_ticket, poll_qr_ticket


class BilibiliLoginTests(unittest.IsolatedAsyncioTestCase):
    async def test_generates_embedded_qr_image(self):
        payload = {
            "code": 0,
            "data": {"url": "https://example.com/qr", "qrcode_key": "key-1"},
        }
        with patch(
            "bili_osu_bridge.bili_login._get_json",
            new=AsyncMock(return_value=(payload, {})),
        ):
            ticket = await generate_qr_ticket()

        self.assertEqual(ticket.key, "key-1")
        self.assertTrue(ticket.image_data_url.startswith("data:image/png;base64,"))

    async def test_poll_returns_login_credentials(self):
        payload = {"code": 0, "data": {"code": 0}}
        with (
            patch(
                "bili_osu_bridge.bili_login._get_json",
                new=AsyncMock(return_value=(payload, {"SESSDATA": "cookie"})),
            ),
            patch(
                "bili_osu_bridge.bili_login._fetch_username",
                new=AsyncMock(return_value="测试用户"),
            ),
        ):
            result = await poll_qr_ticket("key-1")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.sessdata, "cookie")
        self.assertEqual(result.username, "测试用户")


if __name__ == "__main__":
    unittest.main()
