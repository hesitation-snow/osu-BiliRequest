import unittest

from bili_osu_bridge.beatmap import BeatmapInfo
from bili_osu_bridge.parser import (
    format_irc_request,
    parse_beatmap_id,
    parse_beatmap_reference,
    parse_osu_beatmap_url,
)


class ParserTests(unittest.TestCase):
    def test_accepts_supported_formats(self):
        expected = 123456
        for value in ("123456", " 点歌123456 ", "点歌 123456", "点歌：123456", "点歌: 123456"):
            with self.subTest(value=value):
                self.assertEqual(parse_beatmap_id(value), expected)

    def test_rejects_links_and_extra_text(self):
        for value in (
            "https://osu.ppy.sh/b/123456",
            "点歌https://osu.ppy.sh/b/123456",
            "点歌123456谢谢",
            "我要点歌 123456",
            "0",
            "",
        ):
            with self.subTest(value=value):
                self.assertIsNone(parse_beatmap_id(value))

    def test_parses_official_osu_urls_for_chat_platforms(self):
        cases = {
            "https://osu.ppy.sh/b/5600294": ("beatmap", 5600294, ()),
            "https://osu.ppy.sh/beatmaps/5600294 +HD": (
                "beatmap", 5600294, ("HD",)
            ),
            "https://osu.ppy.sh/s/2533001": ("set", 2533001, ()),
            "https://osu.ppy.sh/beatmapsets/2533001": ("set", 2533001, ()),
            "https://osu.ppy.sh/beatmapsets/2533001#osu/5600294 +HDDT": (
                "beatmap", 5600294, ("HD", "DT")
            ),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                reference = parse_osu_beatmap_url(value)
                self.assertEqual((reference.kind, reference.id, reference.mods), expected)

        self.assertIsNone(parse_osu_beatmap_url("https://example.com/b/5600294"))
        self.assertIsNone(
            parse_osu_beatmap_url("看看 https://osu.ppy.sh/b/5600294")
        )

    def test_distinguishes_set_and_difficulty_ids(self):
        set_ref = parse_beatmap_reference("点歌 s/2533001")
        beatmap_ref = parse_beatmap_reference("b/5600294")
        plain_ref = parse_beatmap_reference("5600294")

        self.assertEqual((set_ref.kind, set_ref.id), ("set", 2533001))
        self.assertEqual((beatmap_ref.kind, beatmap_ref.id), ("beatmap", 5600294))
        self.assertEqual((plain_ref.kind, plain_ref.id), ("beatmap", 5600294))

    def test_uses_configurable_request_keywords(self):
        reference = parse_beatmap_reference(
            "来一首：s/2533001 +HD",
            ("来一首", "request"),
        )

        self.assertEqual((reference.kind, reference.id), ("set", 2533001))
        self.assertEqual(reference.mods, ("HD",))
        self.assertIsNone(
            parse_beatmap_reference("点歌123456", ("来一首", "request"))
        )
        self.assertEqual(parse_beatmap_reference("123456", ()).id, 123456)

    def test_parses_and_normalizes_mods(self):
        reference = parse_beatmap_reference("点歌 b/5600294 +HD +DT +HD")
        nc_reference = parse_beatmap_reference("s/2533001 DTNC")

        self.assertEqual(reference.mods, ("HD", "DT"))
        self.assertEqual(reference.mods_text, "+HDDT")
        self.assertEqual(nc_reference.mods, ("NC",))
        self.assertIsNone(parse_beatmap_reference("b/5600294 +DTHT"))
        self.assertIsNone(parse_beatmap_reference("b/5600294 +ABC"))

    def test_formats_clickable_osu_link(self):
        text = format_irc_request(123456, "测试\n用户")
        self.assertEqual(
            text,
            "[https://osu.ppy.sh/b/123456 beatmap 123456] <- osu-BiliRequest: 测试 用户",
        )

    def test_formats_rich_beatmap_link(self):
        info = BeatmapInfo(
            beatmap_id=1909273,
            status="Ranked",
            artist="米倉千尋",
            title="恋せよ乙女！",
            version="Skystar's Koigokoro",
            bpm=220,
            stars=6.5758,
            total_length=238,
            artist_unicode="Unicode 艺术家",
            title_unicode="Unicode 标题",
        )
        text = format_irc_request(1909273, "夏目", info)
        self.assertEqual(
            text,
            "[夏目] -> [Ranked] "
            "[https://osu.ppy.sh/b/1909273 米倉千尋 - 恋せよ乙女！ [Skystar's Koigokoro]] "
            "(220 BPM, 6.58*, 3:58)",
        )
        unicode_text = format_irc_request(
            1909273,
            "夏目",
            info,
            use_unicode_metadata=True,
        )
        self.assertIn("Unicode 艺术家 - Unicode 标题", unicode_text)

    def test_formats_speed_mods_without_fake_modded_stars(self):
        info = BeatmapInfo(
            beatmap_id=5600294,
            status="Ranked",
            artist="iroha(sasaki)",
            title="Meltdown",
            version="02",
            bpm=165,
            stars=5.79,
            total_length=320,
            beatmapset_id=2533001,
        )
        reference = parse_beatmap_reference("b/5600294 +HDDT")
        text = format_irc_request(reference, "viewer", info)

        self.assertTrue(
            text.endswith(
                "(247.5 BPM, base 5.79*, 3:33) +HDDT "
                "Sayobot:"
                "[https://dl.sayobot.cn/beatmaps/download/full/2533001 Full]~"
                "[https://dl.sayobot.cn/beatmaps/download/novideo/2533001 NoVideo]"
            )
        )

        api_text = format_irc_request(reference, "viewer", info, 7.1234)
        self.assertIn("(247.5 BPM, 7.12*, 3:33) +HDDT", api_text)
        self.assertTrue(api_text.endswith("2533001 NoVideo]"))


if __name__ == "__main__":
    unittest.main()
