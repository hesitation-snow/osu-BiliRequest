import time
import unittest
from unittest import mock

import blivedm.models.web as web_models

from bili_osu_bridge.app import DanmakuHandler, RequestBridge, _open_dashboard
from bili_osu_bridge.beatmap import BeatmapInfo, BeatmapNotFoundError
from bili_osu_bridge.config import Config
from bili_osu_bridge.messages import RequestMessage
from bili_osu_bridge.tosu import TosuSnapshot


class _Sender:
    def __init__(self):
        self.messages = []

    async def send_privmsg(self, _message):
        self.messages.append(_message)

    async def close(self):
        return None


class _Beatmaps:
    async def get(self, _reference):
        raise AssertionError("not used in submit test")


class _NotFoundBeatmaps:
    async def get(self, reference):
        raise BeatmapNotFoundError(f"{reference.label} 不存在")


class _TransientBeatmaps:
    async def get(self, _reference):
        raise TimeoutError("temporary timeout")


class _KnownBeatmaps:
    async def get(self, reference):
        return BeatmapInfo(
            beatmap_id=reference.id,
            status="Ranked",
            artist="Artist",
            title="Song",
            version="Insane",
            bpm=180,
            stars=5.5,
            total_length=180,
            beatmapset_id=99,
        )


class _NotFoundApi:
    configured = True

    async def get_beatmap(self, reference):
        raise BeatmapNotFoundError(f"{reference.label} 不存在")


class _CountingBeatmaps:
    def __init__(self):
        self.calls = 0

    async def get(self, _reference):
        self.calls += 1
        raise AssertionError("API 已确认不存在后不应查询网页")


class AppTests(unittest.TestCase):
    def test_qq_accepts_direct_osu_link_without_changing_bilibili_parser(self):
        config = Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="",
            osu_irc_password="",
            osu_target_username="",
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())

        bridge.submit_message(
            RequestMessage(
                source="qq",
                user_id="qq-user",
                username="QQ Viewer",
                content="https://osu.ppy.sh/beatmapsets/2533001#osu/5600294 +HD",
            )
        )
        bridge.submit(
            web_models.DanmakuMessage(
                uid=123,
                uname="bilibili Viewer",
                msg="https://osu.ppy.sh/b/123456",
            )
        )

        self.assertEqual(bridge.queue.qsize(), 1)
        request = bridge.queue.get_nowait()
        self.assertEqual((request.reference.kind, request.reference.id), ("beatmap", 5600294))
        self.assertEqual(request.reference.mods, ("HD",))

    def test_ignores_non_request_room_events(self):
        for command in (
            "ENTRY_EFFECT_MUST_RECEIVE",
            "ONLINE_RANK_V3",
            "FLOW_REWARD_CARD",
            "LIVE_ANI_RES_UPDATE",
            "LIKE_GUIDE_USER",
        ):
            with self.subTest(command=command):
                self.assertIn(command, DanmakuHandler._CMD_CALLBACK_DICT)
                self.assertIsNone(DanmakuHandler._CMD_CALLBACK_DICT[command])

    def test_blacklist_matches_uid_and_beatmap_number(self):
        config = Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="",
            osu_irc_password="",
            osu_target_username="",
            blacklisted_user_ids=("123",),
            blacklisted_beatmap_ids=("2",),
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())

        bridge.submit(web_models.DanmakuMessage(uid=123, uname="ok", msg="1"))
        bridge.submit(web_models.DanmakuMessage(uid=456, uname="anyone", msg="2"))
        bridge.submit(
            web_models.DanmakuMessage(
                uid=789,
                uname="allowed",
                face="http://i0.hdslb.com/test-avatar.jpg",
                msg="3",
            )
        )

        self.assertEqual(bridge.queue.qsize(), 1)
        self.assertEqual(bridge.queue.get_nowait().reference.id, 3)

        dashboard = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=3)
        )
        self.assertEqual(dashboard["queueCount"], 1)
        self.assertEqual(len(dashboard["waitingQueue"]), 1)
        self.assertEqual(
            dashboard["waitingQueue"][0]["avatarUrl"],
            "https://i0.hdslb.com/test-avatar.jpg",
        )
        self.assertEqual(dashboard["waitingQueue"][0]["requester"], "allowed")
        self.assertEqual(dashboard["waitingQueue"][0]["source"], "bilibili")
        self.assertTrue(dashboard["requests"][0]["currentMatch"])
        self.assertEqual(dashboard["requests"][0]["state"], "queued")
        self.assertEqual(dashboard["overlay"]["current"]["id"], 1)
        self.assertEqual(dashboard["overlay"]["remainingCount"], 0)

    def test_overlay_queue_does_not_replace_first_request(self):
        config = Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="",
            osu_irc_password="",
            osu_target_username="",
            user_cooldown_seconds=0,
            map_dedupe_seconds=0,
            overlay_hold_seconds=1,
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())
        bridge.submit(web_models.DanmakuMessage(
            uid=1, uname="先点歌", face="https://example.com/first.jpg", msg="11"
        ))
        bridge.submit(web_models.DanmakuMessage(
            uid=2, uname="后点歌", face="https://example.com/second.jpg", msg="22"
        ))
        for record in bridge._records:
            record.state = "sent"
            record.overlay_map_label = f"Unicode {record.resolved_beatmap_id}"

        first = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=11, state="selectPlay")
        )
        self.assertEqual(first["overlay"]["current"]["id"], 1)
        self.assertEqual(first["overlay"]["current"]["requester"], "先点歌")
        self.assertEqual(first["overlay"]["remainingCount"], 1)
        self.assertEqual(first["overlay"]["waiting"][0]["requester"], "后点歌")
        self.assertEqual(
            first["overlay"]["waiting"][0]["avatarUrl"],
            "https://example.com/second.jpg",
        )

        still_first = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=22, state="selectPlay")
        )
        self.assertEqual(still_first["overlay"]["current"]["id"], 1)
        self.assertEqual(still_first["overlay"]["remainingCount"], 1)

        playing = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=11, state="play")
        )
        self.assertTrue(playing["overlay"]["playing"])
        bridge._records[0].overlay_started_at = time.time() - 100
        still_playing = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=11, state="resultsScreen")
        )
        self.assertEqual(still_playing["overlay"]["current"]["id"], 1)

        next_song = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=11, state="selectPlay")
        )
        self.assertEqual(next_song["overlay"]["current"]["id"], 1)
        bridge._records[0].overlay_play_finished_at = time.time() - 61
        next_song = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=11, state="selectPlay")
        )
        self.assertEqual(next_song["overlay"]["current"]["id"], 2)
        self.assertEqual(next_song["overlay"]["current"]["requester"], "后点歌")
        self.assertEqual(next_song["overlay"]["remainingCount"], 0)

    def test_selected_unplayed_request_uses_shorter_hold(self):
        config = Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="",
            osu_irc_password="",
            osu_target_username="",
            user_cooldown_seconds=0,
            map_dedupe_seconds=0,
            overlay_hold_seconds=500,
            overlay_matched_hold_seconds=120,
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())
        bridge.submit(web_models.DanmakuMessage(uid=1, uname="当前", msg="11"))
        bridge.submit(web_models.DanmakuMessage(uid=2, uname="候场", msg="22"))
        for record in bridge._records:
            record.state = "sent"

        selected = TosuSnapshot(connected=True, beatmap_id=11, state="selectPlay")
        bridge.dashboard_payload(selected)
        bridge.dashboard_payload(selected)
        bridge._records[0].overlay_matched_at = time.time() - 121
        advanced = bridge.dashboard_payload(selected)

        self.assertEqual(advanced["overlay"]["current"]["id"], 2)

    def test_unmatched_unplayed_request_uses_300_second_hold(self):
        config = Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="",
            osu_irc_password="",
            osu_target_username="",
            user_cooldown_seconds=0,
            map_dedupe_seconds=0,
            overlay_hold_seconds=300,
            overlay_matched_hold_seconds=120,
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())
        bridge.submit(web_models.DanmakuMessage(uid=1, uname="当前", msg="11"))
        bridge._records[0].state = "sent"
        snapshot = TosuSnapshot(connected=True, beatmap_id=99, state="selectPlay")
        bridge.dashboard_payload(snapshot)
        bridge._records[0].overlay_started_at = time.time() - 299

        still_current = bridge.dashboard_payload(snapshot)

        self.assertEqual(still_current["overlay"]["current"]["id"], 1)

    def test_switching_away_after_play_advances_immediately(self):
        config = Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="",
            osu_irc_password="",
            osu_target_username="",
            user_cooldown_seconds=0,
            map_dedupe_seconds=0,
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())
        bridge.submit(web_models.DanmakuMessage(uid=1, uname="当前", msg="11"))
        bridge.submit(web_models.DanmakuMessage(uid=2, uname="下一首", msg="22"))
        for record in bridge._records:
            record.state = "sent"

        bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=11, state="play")
        )
        advanced = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=99, state="selectPlay")
        )

        self.assertEqual(advanced["overlay"]["current"]["id"], 2)

    def test_playing_later_queued_request_replaces_current(self):
        config = Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="",
            osu_irc_password="",
            osu_target_username="",
            user_cooldown_seconds=0,
            map_dedupe_seconds=0,
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())
        for uid, beatmap_id in ((1, 11), (2, 22), (3, 33)):
            bridge.submit(
                web_models.DanmakuMessage(
                    uid=uid,
                    uname=f"用户{uid}",
                    msg=str(beatmap_id),
                )
            )
        for record in bridge._records:
            record.state = "sent"

        bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=11, state="selectPlay")
        )
        jumped = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=33, state="play")
        )

        self.assertEqual(jumped["overlay"]["current"]["id"], 3)
        self.assertTrue(jumped["overlay"]["playing"])
        self.assertTrue(bridge._records[0].overlay_dismissed)
        self.assertFalse(bridge._records[1].overlay_dismissed)
        self.assertEqual(jumped["overlay"]["remainingCount"], 1)
        self.assertEqual(jumped["overlay"]["waiting"][0]["id"], 2)

        bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=33, state="resultsScreen")
        )
        advanced = bridge.dashboard_payload(
            TosuSnapshot(connected=True, beatmap_id=99, state="selectPlay")
        )
        self.assertEqual(advanced["overlay"]["current"]["id"], 2)

    def test_open_dashboard_uses_default_browser(self):
        with mock.patch(
            "bili_osu_bridge.app.webbrowser.open",
            return_value=True,
        ) as browser_open:
            import asyncio

            asyncio.run(_open_dashboard("http://127.0.0.1:24051/"))

        browser_open.assert_called_once_with("http://127.0.0.1:24051/")

class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def _config(self) -> Config:
        return Config(
            bili_room_id=1,
            bili_sessdata="",
            osu_irc_username="sender",
            osu_irc_password="password",
            osu_target_username="target",
            user_cooldown_seconds=0,
            map_dedupe_seconds=0,
        )

    async def test_missing_plain_id_fails_with_sid_hint_and_sends_nothing(self):
        sender = _Sender()
        bridge = RequestBridge(self._config(), sender, _NotFoundBeatmaps())
        bridge.start()
        try:
            bridge.submit(
                web_models.DanmakuMessage(
                    uid=1,
                    uname="viewer",
                    msg="2533001",
                )
            )
            await bridge.queue.join()

            self.assertEqual(sender.messages, [])
            self.assertEqual(bridge._records[0].state, "failed")
            self.assertIn("请使用 s/2533001", bridge._records[0].error)
            payload = bridge.dashboard_payload(TosuSnapshot(connected=False))
            self.assertIsNone(payload["overlay"]["current"])
        finally:
            await bridge.close()

    async def test_api_not_found_skips_webpage_lookup(self):
        sender = _Sender()
        beatmaps = _CountingBeatmaps()
        bridge = RequestBridge(
            self._config(),
            sender,
            beatmaps,
            osu_api=_NotFoundApi(),
        )
        bridge.start()
        try:
            bridge.submit_message(RequestMessage("qq", "user", "群友", "123456"))
            await bridge.queue.join()

            self.assertEqual(beatmaps.calls, 0)
            self.assertEqual(sender.messages, [])
            self.assertEqual(bridge._records[0].state, "failed")
        finally:
            await bridge.close()

    async def test_transient_lookup_failure_keeps_basic_link_fallback(self):
        sender = _Sender()
        bridge = RequestBridge(self._config(), sender, _TransientBeatmaps())
        replies = []

        async def reply(text):
            replies.append(text)

        bridge.start()
        try:
            bridge.submit_message(
                RequestMessage(
                    source="qq",
                    user_id="qq-user",
                    username="QQ Viewer",
                    content="123456",
                    reply=reply,
                )
            )
            await bridge.queue.join()
            await __import__("asyncio").sleep(0)

            self.assertEqual(bridge._records[0].state, "sent")
            self.assertEqual(len(sender.messages), 1)
            self.assertIn("https://osu.ppy.sh/b/123456", sender.messages[0])
            self.assertEqual(replies, ["点歌推送成功：b/123456"])
        finally:
            await bridge.close()

    async def test_resolved_request_exposes_overlay_duration_and_stars(self):
        bridge = RequestBridge(self._config(), _Sender(), _KnownBeatmaps())
        bridge.start()
        try:
            bridge.submit_message(
                RequestMessage("qq", "user", "Viewer", "123456 +DT")
            )
            await bridge.queue.join()

            record = bridge._records[0]
            self.assertEqual(record.duration_label, "2:00")
            self.assertEqual(record.stars_label, "base 5.50*")
            self.assertEqual(
                record.overlay_avatar_url,
                "https://assets.ppy.sh/beatmaps/99/covers/list.jpg",
            )
            payload = bridge.dashboard_payload(TosuSnapshot(connected=False))
            self.assertEqual(payload["overlay"]["current"]["durationLabel"], "2:00")
            self.assertEqual(
                payload["overlay"]["current"]["starsLabel"],
                "base 5.50*",
            )
        finally:
            await bridge.close()

    async def test_qq_list_np_and_help_commands(self):
        replies = []

        async def reply(text):
            replies.append(text)

        snapshot = TosuSnapshot(
            connected=True,
            beatmap_id=123,
            artist="Artist",
            title="Title",
            version="Insane",
            state="play",
        )
        bridge = RequestBridge(
            self._config(),
            _Sender(),
            _Beatmaps(),
            tosu_snapshot_provider=lambda: snapshot,
        )
        for command in ("/list", "/np", "/help"):
            bridge.submit_message(
                RequestMessage("qq", "user", "Viewer", command, reply=reply)
            )
        await __import__("asyncio").sleep(0)

        self.assertEqual(replies[0], "当前点歌列表为空。")
        self.assertIn("主播正在听：Artist - Title", replies[1])
        self.assertIn("https://osu.ppy.sh/b/123", replies[1])
        self.assertIn("主播正在听", replies[1])
        self.assertNotIn("[Insane]", replies[1])
        self.assertNotIn("状态：", replies[1])
        self.assertIn("/list", replies[2])
        self.assertNotIn("osu-BiliRequest 点歌助手", replies[2])
        self.assertNotIn("旧版 ! 指令仍然兼容", replies[2])

    async def test_qq_private_skip_only_removes_own_request(self):
        replies = []

        async def reply(text):
            replies.append(text)

        bridge = RequestBridge(self._config(), _Sender(), _Beatmaps())
        bridge.submit_message(
            RequestMessage("qq", "user-a", "Alice", "11")
        )
        bridge.submit_message(
            RequestMessage("qq", "user-b", "Bob", "22")
        )
        bridge._records[0].map_label = "Artist A - Song A [Insane]"
        bridge._records[0].duration_label = "2:03"
        bridge._records[0].stars_label = "5.55*"

        bridge.submit_message(
            RequestMessage(
                "qq", "user-a", "Alice", "!list", is_private=True, reply=reply
            )
        )
        bridge.submit_message(
            RequestMessage(
                "qq", "user-a", "Alice", "!skip 2", is_private=True, reply=reply
            )
        )
        bridge.submit_message(
            RequestMessage(
                "qq", "user-a", "Alice", "!skip", is_private=True, reply=reply
            )
        )
        await __import__("asyncio").sleep(0)

        self.assertIn("2:03 · 5.55*", replies[0])
        self.assertEqual(replies[1], "只能跳过自己提交的点歌；主播可以跳过任意项目。")
        self.assertIn("已跳过：Artist A - Song A [Insane]", replies[2])
        self.assertEqual(bridge._records[0].state, "skipped")
        self.assertTrue(bridge._records[0].overlay_dismissed)
        self.assertFalse(bridge._records[1].overlay_dismissed)

    async def test_qq_owner_can_skip_another_users_request_in_group(self):
        replies = []

        async def reply(text):
            replies.append(text)

        config = self._config()
        config = __import__("dataclasses").replace(
            config,
            qq_owner_openids=("streamer-openid",),
        )
        bridge = RequestBridge(config, _Sender(), _Beatmaps())
        bridge.submit_message(RequestMessage("qq", "viewer", "群友", "11"))
        bridge.submit_message(
            RequestMessage(
                "qq",
                "streamer-openid",
                "群友",
                "/skip",
                reply=reply,
            )
        )
        await __import__("asyncio").sleep(0)

        self.assertEqual(bridge._records[0].state, "skipped")
        self.assertIn("已跳过", replies[0])

    async def test_qq_ownerid_works_in_group_and_private_chat(self):
        replies = []

        async def reply(text):
            replies.append(text)

        bridge = RequestBridge(self._config(), _Sender(), _Beatmaps())
        bridge.submit_message(
            RequestMessage("qq", "owner-123", "群友", "/ownerid", reply=reply)
        )
        bridge.submit_message(
            RequestMessage(
                "qq",
                "owner-123",
                "群友",
                "/ownerid",
                is_private=True,
                reply=reply,
            )
        )
        await __import__("asyncio").sleep(0)

        self.assertIn("owner-123", replies[0])
        self.assertIn("owner-123", replies[1])

    async def test_qq_requester_can_skip_own_request_in_group_chat(self):
        replies = []

        async def reply(text):
            replies.append(text)

        bridge = RequestBridge(self._config(), _Sender(), _Beatmaps())
        bridge.submit_message(RequestMessage("qq", "user", "Viewer", "11"))
        bridge.submit_message(
            RequestMessage("qq", "user", "Viewer", "!skip 1", reply=reply)
        )
        await __import__("asyncio").sleep(0)

        self.assertIn("已跳过", replies[0])
        self.assertTrue(bridge._records[0].overlay_dismissed)

    async def test_irc_disabled_keeps_queue_and_reports_added(self):
        replies = []

        async def reply(text):
            replies.append(text)

        config = self._config()
        bridge = RequestBridge(config, None, _KnownBeatmaps())
        bridge.start()
        try:
            bridge.submit_message(
                RequestMessage("qq", "user", "群友", "123", reply=reply)
            )
            await bridge.queue.join()
            await __import__("asyncio").sleep(0)

            self.assertEqual(bridge._records[0].state, "sent")
            self.assertEqual(replies, ["点歌已加入队列：Artist - Song [Insane]"])
        finally:
            await bridge.close()


if __name__ == "__main__":
    unittest.main()
