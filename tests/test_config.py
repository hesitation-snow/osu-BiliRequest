import json
import tempfile
import unittest
from pathlib import Path

from bili_osu_bridge.config import Config
from bili_osu_bridge.parser import DEFAULT_IRC_MESSAGE_TEMPLATE
from bili_osu_bridge.setup_web import SetupWebServer, build_config_from_payload


def setup_payload(**overrides):
    payload = {
        "roomId": 268086,
        "sessdata": "sess-cookie",
        "qqEnabled": False,
        "qqAppId": "",
        "qqAppSecret": "",
        "qqAllowedGroupOpenids": "",
        "qqOwnerOpenids": "",
        "ircEnabled": True,
        "ircServer": "irc.ppy.sh:6667",
        "ircUsername": "sender",
        "ircPassword": "irc-password",
        "targetUsername": "target",
        "ircSendIntervalSeconds": 1,
        "sendStartupMessage": True,
        "apiEnabled": False,
        "apiClientId": 0,
        "apiClientSecret": "",
        "requestKeywords": "点歌\nrequest",
        "tosuEnabled": True,
        "tosuUrl": "http://127.0.0.1:24050/json/v2",
        "tosuPollSeconds": 1,
        "useUnicodeIrc": False,
        "useUnicodeWeb": True,
        "useUnicodeOverlay": True,
        "webPort": 24051,
        "overlayHoldSeconds": 300,
        "overlayMatchedHoldSeconds": 120,
        "overlayPlayedHoldSeconds": 60,
        "userCooldownSeconds": 30,
        "mapDedupeSeconds": 600,
        "queueMaxSize": 50,
        "proxy": "",
        "blacklistedUserIds": "123\n456",
        "blacklistedBeatmapIds": "666\n233",
        "logLevel": "INFO",
    }
    payload.update(overrides)
    return payload


class ConfigTests(unittest.TestCase):
    def test_loads_json_config_with_new_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                "// JSONC comment support\n"
                + json.dumps(
                    {
                        "bilibili": {"roomId": 268086, "sessdata": "cookie"},
                        "osuIrc": {
                            "username": "sender",
                            "password": "secret",
                            "targetUsername": "target",
                        },
                    }
                ),
                encoding="utf-8",
            )
            config = Config.load(path)

        self.assertTrue(config.tosu_enabled)
        self.assertTrue(config.osu_irc_enabled)
        self.assertEqual(config.osu_irc_server, "irc.ppy.sh:6667")
        self.assertEqual(config.osu_irc_host, "irc.ppy.sh")
        self.assertEqual(config.osu_irc_port, 6667)
        self.assertFalse(config.use_unicode_irc)
        self.assertTrue(config.use_unicode_web)
        self.assertTrue(config.use_unicode_overlay)
        self.assertEqual(config.overlay_hold_seconds, 300)
        self.assertEqual(config.overlay_matched_hold_seconds, 120)
        self.assertEqual(config.overlay_played_hold_seconds, 60)
        rendered = config.to_json_dict()
        self.assertTrue(rendered["tosu"]["enabled"])
        self.assertFalse(rendered["display"]["useUnicodeIrc"])
        self.assertTrue(rendered["display"]["useUnicodeWeb"])
        self.assertTrue(rendered["display"]["useUnicodeOverlay"])
        self.assertEqual(rendered["web"]["overlayHoldSeconds"], 300)
        self.assertEqual(rendered["web"]["overlayPlayedHoldSeconds"], 60)
        self.assertNotIn("_comment", rendered["osuIrc"])
        self.assertEqual(rendered["osuIrc"]["server"], "irc.ppy.sh:6667")
        self.assertEqual(
            rendered["osuIrc"]["messageTemplate"],
            DEFAULT_IRC_MESSAGE_TEMPLATE,
        )

    def test_irc_can_be_disabled_without_credentials(self):
        config = build_config_from_payload(
            setup_payload(
                ircEnabled=False,
                ircUsername="",
                ircPassword="",
                targetUsername="",
            )
        )

        self.assertFalse(config.osu_irc_enabled)
        self.assertFalse(config.to_json_dict()["osuIrc"]["enabled"])

    def test_loads_custom_irc_server(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "bilibili": {"roomId": 268086},
                        "osuIrc": {
                            "server": "irc.example.test:7777",
                            "username": "sender",
                            "password": "secret",
                            "targetUsername": "target",
                        },
                    }
                ),
                encoding="utf-8",
            )
            config = Config.load(path)

        self.assertEqual(config.osu_irc_host, "irc.example.test")
        self.assertEqual(config.osu_irc_port, 7777)

    def test_rejects_unknown_irc_template_placeholder(self):
        with self.assertRaisesRegex(ValueError, "unknown_field"):
            build_config_from_payload(
                setup_payload(ircMessageTemplate="{requester} {unknown_field}")
            )

    def test_web_payload_builds_complete_config(self):
        config = build_config_from_payload(
            setup_payload(
                apiEnabled=True,
                apiClientId=12345,
                apiClientSecret="api-secret",
                qqEnabled=True,
                qqAppId="123456",
                qqAppSecret="qq-secret",
                qqAllowedGroupOpenids="group-a\ngroup-b",
                qqOwnerOpenids="owner-a\nowner-b",
                tosuEnabled=False,
                useUnicodeIrc=True,
                useUnicodeWeb=False,
                useUnicodeOverlay=True,
                proxy="http://127.0.0.1:7890",
            )
        )

        self.assertEqual(config.bili_room_id, 268086)
        self.assertEqual(config.request_keywords, ("点歌", "request"))
        self.assertFalse(config.tosu_enabled)
        self.assertTrue(config.use_unicode_irc)
        self.assertFalse(config.use_unicode_web)
        self.assertTrue(config.use_unicode_overlay)
        self.assertTrue(config.osu_api_enabled)
        self.assertEqual(config.osu_api_client_secret, "api-secret")
        self.assertTrue(config.qq_enabled)
        self.assertEqual(config.qq_app_id, "123456")
        self.assertEqual(config.qq_app_secret, "qq-secret")
        self.assertEqual(config.qq_allowed_group_openids, ("group-a", "group-b"))
        self.assertEqual(config.qq_owner_openids, ("owner-a", "owner-b"))
        self.assertEqual(config.blacklisted_user_ids, ("123", "456"))
        self.assertEqual(config.blacklisted_beatmap_ids, ("666", "233"))

        customized = build_config_from_payload(
            setup_payload(
                ircMessageTemplate="{requester}: {beatmap_link}",
                ircFallbackTemplate="{requester}: {reference_url}",
            )
        )
        self.assertEqual(customized.irc_message_template, "{requester}: {beatmap_link}")
        self.assertEqual(customized.irc_fallback_template, "{requester}: {reference_url}")

    def test_migrates_previous_default_hold_to_300(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "bilibili": {"roomId": 1},
                        "osuIrc": {
                            "username": "sender",
                            "password": "secret",
                            "targetUsername": "target",
                        },
                        "web": {
                            "overlayHoldSeconds": 500,
                            "overlayMatchedHoldSeconds": 120,
                        },
                    }
                ),
                encoding="utf-8",
            )
            config = Config.load(path)

        self.assertEqual(config.overlay_hold_seconds, 300)

    def test_web_payload_preserves_blank_secrets(self):
        current = build_config_from_payload(
            setup_payload(
                apiEnabled=True,
                apiClientId=1,
                apiClientSecret="old-secret",
                qqEnabled=True,
                qqAppId="123",
                qqAppSecret="old-qq-secret",
            )
        )
        updated = build_config_from_payload(
            setup_payload(
                sessdata="",
                ircPassword="",
                apiEnabled=True,
                apiClientId=1,
                apiClientSecret="",
                qqEnabled=True,
                qqAppId="123",
                qqAppSecret="",
            ),
            current,
        )

        self.assertEqual(updated.bili_sessdata, "sess-cookie")
        self.assertEqual(updated.osu_irc_password, "irc-password")
        self.assertEqual(updated.osu_api_client_secret, "old-secret")
        self.assertEqual(updated.qq_app_secret, "old-qq-secret")

    def test_config_save_has_security_comments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            config = build_config_from_payload(setup_payload())
            config.save(path)
            loaded = Config.load(path)
            raw = path.read_text(encoding="utf-8")

        self.assertEqual(config, loaded)
        self.assertTrue(raw.startswith("// 安全提醒"))
        self.assertIn("// Security warning:", raw)
        self.assertNotIn('"_comment"', raw)


class SetupWebTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_page_contains_all_major_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            server = SetupWebServer(Path(temp_dir) / "config.json")
            response = await server._index(None)
            html = response.text

        self.assertIn("bilibili 直播间", html)
        self.assertIn("QQ 官方机器人", html)
        self.assertIn("qqAllowedGroupOpenids", html)
        self.assertIn("qqOwnerOpenids", html)
        self.assertIn("/ownerid", html)
        self.assertIn("QQ群内点歌或使用指令时，需要先 @机器人", html)
        self.assertIn('class="home-link" href="/"', html)
        self.assertIn("osu-BiliRequest 设置", html)
        self.assertIn("网络代理", html)
        self.assertIn("osu! IRC 转发", html)
        self.assertIn("osu!lazer 无法在游戏内收到同一账号通过 IRC 发给自己的消息", html)
        self.assertIn('id="ircEnabled"', html)
        self.assertIn('id="ircServer"', html)
        self.assertIn('id="ircMessageTemplate"', html)
        self.assertIn('id="ircFallbackTemplate"', html)
        self.assertIn('id="ircTemplatePreview"', html)
        self.assertIn('id="resetIrcTemplates"', html)
        self.assertIn("{beatmap_link}", html)
        self.assertIn("<h2>osu! API</h2>", html)
        self.assertIn("tosu 状态同步", html)
        self.assertIn("useUnicodeIrc", html)
        self.assertIn("useUnicodeWeb", html)
        self.assertIn("useUnicodeOverlay", html)
        self.assertIn("overlayHoldSeconds", html)
        self.assertIn("overlayPlayedHoldSeconds", html)
        self.assertIn("blacklistedBeatmapIds", html)
        self.assertNotIn("blacklistedUsernames", html)
        self.assertIn('id="save"', html)
        self.assertIn("保存配置", html)
        self.assertIn("扫码登录", html)
        self.assertIn("GitHub 开源地址", html)
        self.assertTrue(server._public_config()["values"]["apiEnabled"])


if __name__ == "__main__":
    unittest.main()
