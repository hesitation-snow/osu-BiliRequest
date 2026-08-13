import unittest
from types import SimpleNamespace

from bili_osu_bridge.dashboard import DashboardServer


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_obs_overlay_is_transparent_and_uses_server_queue(self):
        server = DashboardServer(24051, lambda: {})
        response = await server._overlay(None)
        html = response.text

        self.assertIn("background: transparent", html)
        self.assertIn("data.overlay.current", html)
        self.assertIn("data.overlay.remainingCount", html)
        self.assertIn("data.overlay.waiting", html)
        self.assertIn("data.overlay.playing", html)
        self.assertIn("item.avatarUrl", html)
        self.assertIn("item.overlayAvatarUrl", html)
        self.assertIn("item.overlayTitleLabel", html)
        self.assertIn("item.overlayDifficulty", html)
        self.assertIn("item.requester", html)
        self.assertIn("队列 ${remaining} 人", html)
        self.assertIn("waiting-avatar", html)
        self.assertIn("transition: opacity .55s", html)
        self.assertIn("classList.add('entering')", html)
        self.assertIn("classList.add('leaving')", html)
        self.assertIn("item.durationLabel", html)
        self.assertIn("item.starsLabel", html)
        self.assertNotIn("后面 ${remaining} 人", html)
        self.assertNotIn("等待 bilibili 观众点歌", html)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    async def test_dashboard_shows_requester_avatar_and_overlay_preview(self):
        server = DashboardServer(24051, lambda: {})
        response = await server._index(None)
        html = response.text

        self.assertIn("request-avatar", html)
        self.assertIn("item.avatarUrl", html)
        self.assertIn("item.requester", html)
        self.assertIn('id="overlay-preview"', html)
        self.assertIn('src="/overlay"', html)
        self.assertIn('id="copy-overlay-url"', html)
        self.assertIn("推荐分辨率：760 × 100", html)
        self.assertIn("bili-overlay-height", html)
        self.assertIn("osu-BiliRequest", html)
        self.assertIn('href="/settings"', html)
        self.assertIn('id="restart-app"', html)
        self.assertIn("/api/restart", html)
        self.assertIn("GitHub 开源地址", html)
        self.assertIn('href="/api"', html)
        self.assertIn("osu-BiliRequest-tosu-overlay.zip", html)
        self.assertIn("tosu 与点歌队列 WebSocket", html)

    async def test_public_overlay_api_is_versioned_and_cors_enabled(self):
        payload = {
            "overlay": {"current": {"id": 1}, "waiting": []},
            "tosu": {"connected": True},
            "queueCount": 1,
            "requests": [{"id": 1}],
        }
        server = DashboardServer(24051, lambda: payload)

        request = SimpleNamespace(headers={"Origin": "null"})
        response = await server._api_overlay(request)
        status_response = await server._api_status(request)
        body = __import__("json").loads(response.text)
        status_body = __import__("json").loads(status_response.text)
        docs = await server._api_docs(None)
        directory = await server._api_v1(request)

        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(status_body["schemaVersion"], 1)
        self.assertEqual(body["overlay"]["current"]["id"], 1)
        self.assertEqual(body["requests"][0]["id"], 1)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "null")
        self.assertIn("/api/v1/ws", docs.text)
        self.assertIn("WebSocket", docs.text)
        self.assertIn("/api/v1/status", directory.text)
        self.assertIn("/websocket/v2", docs.text)
        self.assertIn("osu-BiliRequest-tosu-overlay.zip", docs.text)


if __name__ == "__main__":
    unittest.main()
