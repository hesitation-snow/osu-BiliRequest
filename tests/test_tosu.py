import unittest

from bili_osu_bridge.tosu import TosuSnapshot


class TosuTests(unittest.TestCase):
    def test_parses_v2_current_beatmap(self):
        snapshot = TosuSnapshot.from_payload(
            {
                "state": {"number": 2, "name": "play"},
                "beatmap": {
                    "id": 3228594,
                    "artist": "Artist",
                    "artistUnicode": "艺术家",
                    "title": "Title",
                    "titleUnicode": "标题",
                    "version": "Insane",
                },
            }
        )

        self.assertTrue(snapshot.connected)
        self.assertEqual(snapshot.beatmap_id, 3228594)
        self.assertEqual(snapshot.state, "play")
        self.assertEqual(snapshot.beatmap_label, "Artist - Title [Insane]")
        self.assertEqual(snapshot.beatmap_unicode_label, "艺术家 - 标题 [Insane]")
        self.assertEqual(snapshot.to_json()["beatmapId"], 3228594)
        self.assertEqual(
            snapshot.to_json()["beatmapUnicodeLabel"],
            "艺术家 - 标题 [Insane]",
        )
        self.assertEqual(snapshot.to_json()["beatmapUnicodeTitle"], "艺术家 - 标题")
        self.assertEqual(snapshot.to_json()["beatmapVersion"], "Insane")
        self.assertEqual(
            snapshot.to_json(False)["beatmapDisplayLabel"],
            "Artist - Title [Insane]",
        )
        self.assertEqual(
            snapshot.to_json(True)["beatmapDisplayLabel"],
            "艺术家 - 标题 [Insane]",
        )

    def test_handles_menu_without_loaded_beatmap(self):
        snapshot = TosuSnapshot.from_payload(
            {"state": {"name": "menu"}, "beatmap": {}}
        )

        self.assertEqual(snapshot.beatmap_id, 0)
        self.assertEqual(snapshot.beatmap_label, "未加载谱面")


if __name__ == "__main__":
    unittest.main()
