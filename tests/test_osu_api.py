import unittest

from bili_osu_bridge.osu_api import OsuApiClient
from bili_osu_bridge.beatmap import BeatmapNotFoundError, BeatmapReference


class _Response:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def json(self):
        return self.payload


class _Session:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/oauth/token"):
            return _Response(
                200,
                {"access_token": "token-value", "expires_in": 3600},
            )
        return _Response(200, {"attributes": {"star_rating": 7.1234}})

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/beatmapsets/" in url:
            return _Response(
                200,
                {
                    "id": 99,
                    "status": "ranked",
                    "artist": "Artist",
                    "artist_unicode": "艺术家",
                    "title": "Title",
                    "title_unicode": "标题",
                    "beatmaps": [
                        {"id": 1, "version": "Easy", "bpm": 180, "difficulty_rating": 2, "total_length": 100},
                        {"id": 2, "version": "Insane", "bpm": 180, "difficulty_rating": 5.5, "total_length": 120},
                    ],
                },
            )
        return _Response(
            200,
            {
                "id": 2,
                "status": "ranked",
                "version": "Insane",
                "bpm": 180,
                "difficulty_rating": 5.5,
                "total_length": 120,
                "beatmapset_id": 99,
                "beatmapset": {
                    "id": 99,
                    "artist": "Artist",
                    "artist_unicode": "艺术家",
                    "title": "Title",
                    "title_unicode": "标题",
                },
            },
        )


class _NotFoundSession(_Session):
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response(404, {})


class OsuApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_gets_modded_stars_and_reuses_token(self):
        session = _Session()
        client = OsuApiClient(session, 123, "secret")

        first = await client.get_modded_stars(5600294, ("HD", "DT"))
        second = await client.get_modded_stars(5600294, ("HD", "DT"))

        self.assertEqual(first, 7.1234)
        self.assertEqual(second, 7.1234)
        self.assertEqual(len([url for url, _ in session.calls if url.endswith("/oauth/token")]), 1)
        _, attributes_call = session.calls[1]
        self.assertEqual(attributes_call["json"], {"mods": ["HD", "DT"]})
        self.assertEqual(
            attributes_call["headers"]["Authorization"],
            "Bearer token-value",
        )

    async def test_gets_beatmap_metadata_and_highest_set_difficulty(self):
        session = _Session()
        client = OsuApiClient(session, 123, "secret")

        beatmap = await client.get_beatmap(BeatmapReference("beatmap", 2))
        beatmapset = await client.get_beatmap(BeatmapReference("set", 99))

        self.assertEqual(beatmap.title_unicode, "标题")
        self.assertEqual(beatmap.version, "Insane")
        self.assertEqual(beatmapset.beatmap_id, 2)
        self.assertEqual(beatmapset.stars, 5.5)

    async def test_404_is_classified_as_definitive_not_found(self):
        client = OsuApiClient(_NotFoundSession(), 123, "secret")

        with self.assertRaises(BeatmapNotFoundError):
            await client.get_beatmap(BeatmapReference("beatmap", 999999999))


if __name__ == "__main__":
    unittest.main()
