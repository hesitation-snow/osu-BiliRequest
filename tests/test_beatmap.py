import json
import unittest

from bili_osu_bridge.beatmap import BeatmapNotFoundError, parse_beatmapset_html


class BeatmapTests(unittest.TestCase):
    def test_parses_selected_difficulty_and_unicode_fallback(self):
        data = {
            "id": 999,
            "artist": "Romanized Artist",
            "artist_unicode": "艺术家",
            "title": "Romanized Title",
            "title_unicode": "",
            "status": "ranked",
            "bpm": 180,
            "beatmaps": [
                {
                    "id": 123,
                    "status": "ranked",
                    "version": "Another",
                    "bpm": 180,
                    "difficulty_rating": 3,
                    "total_length": 60,
                },
                {
                    "id": 456,
                    "status": "loved",
                    "version": "Insane",
                    "bpm": 200,
                    "difficulty_rating": 5.126,
                    "total_length": 125,
                },
            ],
        }
        html = (
            '<html><script id="json-beatmapset" type="application/json">'
            + json.dumps(data, ensure_ascii=False)
            + "</script></html>"
        )
        info = parse_beatmapset_html(html, 456)

        self.assertEqual(info.artist, "Romanized Artist")
        self.assertEqual(info.artist_unicode, "艺术家")
        self.assertEqual(info.title, "Romanized Title")
        self.assertEqual(info.title_unicode, "Romanized Title")
        self.assertEqual(info.status, "Loved")
        self.assertEqual(info.version, "Insane")
        self.assertEqual(info.bpm, 200)
        self.assertEqual(info.stars, 5.126)
        self.assertEqual(info.total_length, 125)
        self.assertEqual(info.beatmapset_id, 999)

        highest = parse_beatmapset_html(html)
        self.assertEqual(highest.beatmap_id, 456)

    def test_empty_beatmapset_is_a_definitive_not_found_result(self):
        html = (
            '<html><script id="json-beatmapset" type="application/json">'
            '{"id":999,"beatmaps":[]}'
            "</script></html>"
        )

        with self.assertRaises(BeatmapNotFoundError):
            parse_beatmapset_html(html)


if __name__ == "__main__":
    unittest.main()
