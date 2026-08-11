import unittest

from bili_osu_bridge.limiter import RequestLimiter


class LimiterTests(unittest.TestCase):
    def test_user_cooldown_and_map_dedupe(self):
        now = [100.0]
        limiter = RequestLimiter(30, 600, clock=lambda: now[0])

        self.assertTrue(limiter.accept("user-a", 1)[0])
        self.assertFalse(limiter.accept("user-a", 2)[0])
        self.assertFalse(limiter.accept("user-b", 1)[0])

        now[0] += 31
        self.assertTrue(limiter.accept("user-a", 2)[0])

        now[0] += 601
        self.assertTrue(limiter.accept("user-b", 1)[0])


if __name__ == "__main__":
    unittest.main()
