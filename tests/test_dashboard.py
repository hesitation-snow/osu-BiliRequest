import unittest

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
        self.assertIn("item.overlayTitleLabel", html)
        self.assertIn("item.overlayDifficulty", html)
        self.assertIn("item.requester", html)
        self.assertIn("队列 ${remaining} 人", html)
        self.assertIn("waiting-avatar", html)
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


if __name__ == "__main__":
    unittest.main()
