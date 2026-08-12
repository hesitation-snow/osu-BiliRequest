from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


_CONFIG_COMMENTS = """// 安全提醒：请勿公开分享此文件；其中包含登录账号、密码、Cookie 和 Client Secret。
// Security warning: Do not share this file publicly; it contains login usernames, passwords, cookies, and client secrets.
"""


def _strip_json_line_comments(value: str) -> str:
    """Replace // comments outside JSON strings while preserving line numbers."""
    result: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(value):
        char = value[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < len(value) and value[index + 1] == "/":
            result.extend((" ", " "))
            index += 2
            while index < len(value) and value[index] not in "\r\n":
                result.append(" ")
                index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} 必须是 JSON 对象")
    return value


def _string_tuple(value: object, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{key} 必须是 JSON 数组")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _split_irc_server(value: str) -> tuple[str, int]:
    server = value.strip()
    if not server or "://" in server:
        raise ValueError("osuIrc.server 必须使用 主机名 或 主机名:端口 格式")
    parsed = urlsplit(f"//{server}")
    try:
        port = parsed.port or 6667
    except ValueError as exc:
        raise ValueError("osuIrc.server 的端口必须在 1 到 65535 之间") from exc
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not 1 <= port <= 65535
    ):
        raise ValueError("osuIrc.server 必须使用 主机名 或 主机名:端口 格式")
    return parsed.hostname, port


@dataclasses.dataclass(frozen=True)
class Config:
    bili_room_id: int
    bili_sessdata: str
    osu_irc_username: str
    osu_irc_password: str
    osu_target_username: str
    qq_enabled: bool = False
    qq_app_id: str = ""
    qq_app_secret: str = ""
    qq_allowed_group_openids: tuple[str, ...] = ()
    qq_owner_openids: tuple[str, ...] = ()
    osu_irc_enabled: bool = True
    osu_irc_server: str = "irc.ppy.sh:6667"
    osu_api_enabled: bool = False
    osu_api_client_id: int = 0
    osu_api_client_secret: str = ""
    request_keywords: tuple[str, ...] = ("点歌",)
    tosu_enabled: bool = True
    tosu_url: str = "http://127.0.0.1:24050/json/v2"
    tosu_poll_interval_seconds: float = 1.0
    use_unicode_irc: bool = False
    use_unicode_web: bool = True
    use_unicode_overlay: bool = True
    web_port: int = 24051
    overlay_hold_seconds: float = 300.0
    overlay_matched_hold_seconds: float = 120.0
    overlay_played_hold_seconds: float = 60.0
    user_cooldown_seconds: float = 30.0
    map_dedupe_seconds: float = 600.0
    queue_max_size: int = 50
    irc_send_interval_seconds: float = 1.0
    send_startup_message: bool = True
    proxy_url: str = ""
    blacklisted_user_ids: tuple[str, ...] = ()
    blacklisted_beatmap_ids: tuple[str, ...] = ("666",)
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Path, *, validate: bool = True) -> "Config":
        try:
            raw = path.read_text(encoding="utf-8-sig")
            data = json.loads(_strip_json_line_comments(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 格式错误（第 {exc.lineno} 行，第 {exc.colno} 列）") from exc
        if not isinstance(data, dict):
            raise ValueError("配置文件最外层必须是 JSON 对象")

        bilibili = _section(data, "bilibili")
        qq = _section(data, "qq")
        osu_irc = _section(data, "osuIrc")
        osu_api = _section(data, "osuApi")
        chat = _section(data, "chat")
        tosu = _section(data, "tosu")
        display = _section(data, "display")
        web = _section(data, "web")
        limits = _section(data, "limits")
        network = _section(data, "network")
        blacklist = _section(data, "blacklist")

        try:
            api_client_id = int(osu_api.get("clientId", 0) or 0)
            api_client_secret = str(osu_api.get("clientSecret", "")).strip()
            api_enabled = bool(
                osu_api.get(
                    "enabled",
                    bool(api_client_id and api_client_secret),
                )
            )
            config = cls(
                bili_room_id=int(bilibili.get("roomId", 0)),
                bili_sessdata=str(bilibili.get("sessdata", "")).strip(),
                qq_enabled=bool(qq.get("enabled", False)),
                qq_app_id=str(qq.get("appId", "")).strip(),
                qq_app_secret=str(qq.get("appSecret", "")).strip(),
                qq_allowed_group_openids=_string_tuple(
                    qq.get("allowedGroupOpenids", []), "qq.allowedGroupOpenids"
                ),
                qq_owner_openids=_string_tuple(
                    qq.get("ownerOpenids", []), "qq.ownerOpenids"
                ),
                osu_irc_enabled=bool(osu_irc.get("enabled", True)),
                osu_irc_username=str(osu_irc.get("username", "")).strip(),
                osu_irc_password=str(osu_irc.get("password", "")).strip(),
                osu_target_username=str(osu_irc.get("targetUsername", "")).strip(),
                osu_irc_server=str(
                    osu_irc.get("server", "irc.ppy.sh:6667")
                ).strip(),
                osu_api_enabled=api_enabled,
                osu_api_client_id=api_client_id,
                osu_api_client_secret=api_client_secret,
                request_keywords=_string_tuple(
                    chat.get("requestKeywords", ["点歌"]),
                    "chat.requestKeywords",
                ),
                tosu_enabled=bool(tosu.get("enabled", True)),
                tosu_url=str(
                    tosu.get("url", "http://127.0.0.1:24050/json/v2")
                ).strip(),
                tosu_poll_interval_seconds=float(
                    tosu.get("pollIntervalSeconds", 1)
                ),
                use_unicode_irc=bool(display.get("useUnicodeIrc", False)),
                use_unicode_web=bool(
                    display.get(
                        "useUnicodeWeb",
                        display.get("useUnicodeMetadata", True),
                    )
                ),
                use_unicode_overlay=bool(
                    display.get(
                        "useUnicodeOverlay",
                        display.get("useUnicodeMetadata", True),
                    )
                ),
                web_port=int(web.get("port", 24051)),
                overlay_hold_seconds=(
                    300.0
                    if "display" not in data
                    and float(web.get("overlayHoldSeconds", 300)) in {120, 500}
                    else float(web.get("overlayHoldSeconds", 300))
                ),
                overlay_matched_hold_seconds=float(
                    web.get("overlayMatchedHoldSeconds", 120)
                ),
                overlay_played_hold_seconds=float(
                    web.get("overlayPlayedHoldSeconds", 60)
                ),
                user_cooldown_seconds=float(limits.get("userCooldownSeconds", 30)),
                map_dedupe_seconds=float(limits.get("mapDedupeSeconds", 600)),
                queue_max_size=int(limits.get("queueMaxSize", 50)),
                irc_send_interval_seconds=float(osu_irc.get("sendIntervalSeconds", 1)),
                send_startup_message=bool(osu_irc.get("sendStartupMessage", True)),
                proxy_url=str(network.get("proxy", "")).strip(),
                blacklisted_user_ids=_string_tuple(
                    blacklist.get("userIds", []), "blacklist.userIds"
                ),
                blacklisted_beatmap_ids=_string_tuple(
                    blacklist.get("beatmapIds", ["666"]), "blacklist.beatmapIds"
                ),
                log_level=str(data.get("logLevel", "INFO")).strip().upper(),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"配置值类型不正确：{exc}") from exc
        if validate:
            config.validate()
        return config

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "bilibili": {
                "roomId": self.bili_room_id,
                "sessdata": self.bili_sessdata,
            },
            "qq": {
                "enabled": self.qq_enabled,
                "appId": self.qq_app_id,
                "appSecret": self.qq_app_secret,
                "allowedGroupOpenids": list(self.qq_allowed_group_openids),
                "ownerOpenids": list(self.qq_owner_openids),
            },
            "osuIrc": {
                "enabled": self.osu_irc_enabled,
                "server": self.osu_irc_server,
                "username": self.osu_irc_username,
                "password": self.osu_irc_password,
                "targetUsername": self.osu_target_username,
                "sendIntervalSeconds": self.irc_send_interval_seconds,
                "sendStartupMessage": self.send_startup_message,
            },
            "osuApi": {
                "enabled": self.osu_api_enabled,
                "clientId": self.osu_api_client_id,
                "clientSecret": self.osu_api_client_secret,
            },
            "chat": {
                "requestKeywords": list(self.request_keywords),
            },
            "tosu": {
                "enabled": self.tosu_enabled,
                "url": self.tosu_url,
                "pollIntervalSeconds": self.tosu_poll_interval_seconds,
            },
            "display": {
                "useUnicodeIrc": self.use_unicode_irc,
                "useUnicodeWeb": self.use_unicode_web,
                "useUnicodeOverlay": self.use_unicode_overlay,
            },
            "web": {
                "port": self.web_port,
                "overlayHoldSeconds": self.overlay_hold_seconds,
                "overlayMatchedHoldSeconds": self.overlay_matched_hold_seconds,
                "overlayPlayedHoldSeconds": self.overlay_played_hold_seconds,
            },
            "limits": {
                "userCooldownSeconds": self.user_cooldown_seconds,
                "mapDedupeSeconds": self.map_dedupe_seconds,
                "queueMaxSize": self.queue_max_size,
            },
            "network": {
                "proxy": self.proxy_url,
            },
            "blacklist": {
                "userIds": list(self.blacklisted_user_ids),
                "beatmapIds": list(self.blacklisted_beatmap_ids),
            },
            "logLevel": self.log_level,
        }

    def save(self, path: Path) -> None:
        path.write_text(
            _CONFIG_COMMENTS
            + json.dumps(self.to_json_dict(), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    def validate(self) -> None:
        if self.bili_room_id <= 0:
            raise ValueError("bilibili.roomId 必须填写大于 0 的直播间号")
        if self.queue_max_size <= 0:
            raise ValueError("limits.queueMaxSize 必须大于 0")
        if self.user_cooldown_seconds < 0 or self.map_dedupe_seconds < 0:
            raise ValueError("冷却时间不能小于 0")
        if any(
            not value.isdigit() or int(value) <= 0
            for value in self.blacklisted_beatmap_ids
        ):
            raise ValueError("blacklist.beatmapIds 只能填写大于 0 的纯数字")
        if self.osu_irc_enabled and self.irc_send_interval_seconds < 0.5:
            raise ValueError("osuIrc.sendIntervalSeconds 不能小于 0.5")
        if self.osu_irc_enabled:
            _split_irc_server(self.osu_irc_server)
        if self.tosu_enabled and self.tosu_poll_interval_seconds < 0.25:
            raise ValueError("tosu.pollIntervalSeconds 不能小于 0.25")
        tosu_url = urlsplit(self.tosu_url)
        if self.tosu_enabled and (
            tosu_url.scheme.lower() not in {"http", "https"}
            or not tosu_url.hostname
        ):
            raise ValueError("tosu.url 必须是 http:// 或 https:// 开头的地址")
        if not 1 <= self.web_port <= 65535:
            raise ValueError("web.port 必须在 1 到 65535 之间")
        if not 0 <= self.overlay_hold_seconds <= 3600:
            raise ValueError("web.overlayHoldSeconds 必须在 0 到 3600 之间")
        if not 0 <= self.overlay_matched_hold_seconds <= 3600:
            raise ValueError(
                "web.overlayMatchedHoldSeconds 必须在 0 到 3600 之间"
            )
        if not 0 <= self.overlay_played_hold_seconds <= 3600:
            raise ValueError(
                "web.overlayPlayedHoldSeconds 必须在 0 到 3600 之间"
            )
        if self.osu_api_client_id < 0:
            raise ValueError("osuApi.clientId 不能小于 0")
        if bool(self.osu_api_client_id) != bool(self.osu_api_client_secret):
            raise ValueError("osuApi.clientId 和 osuApi.clientSecret 必须同时填写或同时留空")
        if self.osu_api_enabled and not self.osu_api_client_id:
            raise ValueError("启用 osu! API 前必须填写 clientId 和 clientSecret")
        if self.qq_enabled and not self.qq_app_id:
            raise ValueError("启用 QQ 官方机器人前必须填写 qq.appId")
        if self.qq_enabled and not self.qq_app_secret:
            raise ValueError("启用 QQ 官方机器人前必须填写 qq.appSecret")
        if self.proxy_url:
            proxy = urlsplit(self.proxy_url)
            if proxy.scheme.lower() not in {"http", "https"} or not proxy.hostname:
                raise ValueError(
                    "network.proxy 必须是 http:// 或 https:// 开头的代理地址"
                )
        if self.osu_irc_enabled:
            missing = [
                key
                for key, value in (
                    ("osuIrc.username", self.osu_irc_username),
                    ("osuIrc.password", self.osu_irc_password),
                    ("osuIrc.targetUsername", self.osu_target_username),
                )
                if not value
            ]
            if missing:
                raise ValueError("启用 osu! IRC 时必须填写：" + ", ".join(missing))

    def safe_summary(self) -> str:
        return (
            f"bilibili直播间={self.bili_room_id}, "
            f"bilibili登录={'已配置' if self.bili_sessdata else '匿名'}, "
            f"QQ机器人={'已启用' if self.qq_enabled else '已停用'}, "
            f"IRC={'已启用' if self.osu_irc_enabled else '已停用'}, "
            f"IRC用户={self.osu_irc_username or '未配置'}, "
            f"IRC服务器={self.osu_irc_server}, "
            f"接收用户={self.osu_target_username or '未配置'}, "
            f"osu!API={'已启用' if self.osu_api_enabled else '已停用' if self.osu_api_client_id else '未配置'}, "
            f"tosu={'已启用' if self.tosu_enabled else '已停用'}, "
            f"歌名=IRC{'Unicode' if self.use_unicode_irc else '普通'}/"
            f"Web{'Unicode' if self.use_unicode_web else '普通'}/"
            f"Overlay{'Unicode' if self.use_unicode_overlay else '普通'}, "
            f"代理={'已配置' if self.proxy_url else '直连'}, "
            f"Web=http://127.0.0.1:{self.web_port}, "
            f"用户黑名单={len(self.blacklisted_user_ids)}人, "
            f"谱面数字黑名单={len(self.blacklisted_beatmap_ids)}项"
        )

    @property
    def osu_irc_host(self) -> str:
        return _split_irc_server(self.osu_irc_server)[0]

    @property
    def osu_irc_port(self) -> int:
        return _split_irc_server(self.osu_irc_server)[1]
