from __future__ import annotations

import asyncio
import http.cookies
import logging
import random
import time
import webbrowser
from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp
import blivedm
import blivedm.models.web as web_models

from .config import Config
from .dashboard import DashboardServer
from .beatmap import BeatmapLookup, BeatmapNotFoundError, BeatmapReference
from .irc import BanchoIrcClient
from .limiter import RequestLimiter
from .network import apply_http_proxy
from .osu_api import OsuApiClient
from .parser import format_irc_request, parse_beatmap_reference
from .tosu import TosuMonitor, TosuSnapshot


logger = logging.getLogger(__name__)


class InvalidSongRequestError(ValueError):
    pass


def _safe_avatar_url(value: object) -> str:
    url = str(value or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://"):
        url = "https://" + url[7:]
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    return url


@dataclass(frozen=True)
class SongRequest:
    reference: BeatmapReference
    requester_name: str
    user_key: str
    record_id: int


@dataclass
class RequestRecord:
    id: int
    created_at: float
    requester_name: str
    avatar_url: str
    reference_label: str
    requested_beatmap_id: int
    state: str = "queued"
    resolved_beatmap_id: int = 0
    map_label: str = ""
    overlay_map_label: str = ""
    overlay_title_label: str = ""
    overlay_difficulty: str = ""
    error: str = ""
    overlay_started_at: float = 0.0
    overlay_matched_at: float = 0.0
    overlay_play_finished_at: float = 0.0
    overlay_dismissed: bool = False


class RequestBridge:
    def __init__(
        self,
        config: Config,
        sender: BanchoIrcClient,
        beatmaps: BeatmapLookup,
        osu_api: OsuApiClient | None = None,
    ) -> None:
        self.config = config
        self.sender = sender
        self.beatmaps = beatmaps
        self.osu_api = osu_api
        self.queue: asyncio.Queue[SongRequest] = asyncio.Queue(config.queue_max_size)
        self.limiter = RequestLimiter(
            config.user_cooldown_seconds,
            config.map_dedupe_seconds,
        )
        self._blacklisted_ids = set(config.blacklisted_user_ids)
        self._blacklisted_names = {
            name.casefold() for name in config.blacklisted_usernames
        }
        self._worker_task: asyncio.Task | None = None
        self._next_record_id = 1
        self._records: list[RequestRecord] = []
        self._overlay_current_id: int | None = None
        self._overlay_playing = False

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._worker())

    async def close(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
        await self.sender.close()

    def submit(self, message: web_models.DanmakuMessage) -> None:
        if message.dm_type != 0:
            return
        reference = parse_beatmap_reference(
            message.msg,
            self.config.request_keywords,
        )
        if reference is None:
            return

        uid = str(message.uid) if message.uid else ""
        username = (message.uname or "").strip()
        if uid in self._blacklisted_ids or username.casefold() in self._blacklisted_names:
            logger.info(
                "忽略黑名单用户点歌：用户=%s，UID=%s，谱面=%s",
                username or "匿名",
                uid or "未知",
                reference.label,
            )
            return

        user_key = str(message.uid or message.uid_crc32 or username or "anonymous")
        accepted, reason = self.limiter.accept(user_key, reference.key)
        if not accepted:
            logger.info(
                "忽略点歌：%s，用户=%s，谱面=%s",
                reason,
                message.uname or "匿名",
                reference.label,
            )
            return

        record_id = self._next_record_id
        request = SongRequest(
            reference,
            message.uname or "观众",
            user_key,
            record_id,
        )
        try:
            self.queue.put_nowait(request)
        except asyncio.QueueFull:
            logger.warning("点歌队列已满，忽略谱面 %s", reference.label)
            return

        self._next_record_id += 1
        requested_beatmap_id = reference.id if reference.kind == "beatmap" else 0
        self._records.append(
            RequestRecord(
                id=record_id,
                created_at=time.time(),
                requester_name=request.requester_name,
                avatar_url=_safe_avatar_url(message.face),
                reference_label=reference.label,
                requested_beatmap_id=requested_beatmap_id,
                resolved_beatmap_id=requested_beatmap_id,
            )
        )
        self._records = self._records[-100:]

        logger.info(
            "收到点歌：用户=%s，谱面=%s，队列=%d",
            request.requester_name,
            request.reference.label,
            self.queue.qsize(),
        )

    def _record(self, record_id: int) -> RequestRecord | None:
        return next(
            (record for record in reversed(self._records) if record.id == record_id),
            None,
        )

    def dashboard_payload(self, tosu: TosuSnapshot) -> dict:
        current_id = tosu.beatmap_id if tosu.connected else 0

        def serialize(record: RequestRecord) -> dict:
            match: bool | None = None
            if current_id > 0 and record.resolved_beatmap_id > 0:
                match = current_id == record.resolved_beatmap_id
            return {
                "id": record.id,
                "createdAt": record.created_at,
                "requester": record.requester_name,
                "avatarUrl": record.avatar_url,
                "reference": record.reference_label,
                "state": record.state,
                "resolvedBeatmapId": record.resolved_beatmap_id,
                "mapLabel": record.map_label,
                "overlayMapLabel": record.overlay_map_label,
                "overlayTitleLabel": record.overlay_title_label,
                "overlayDifficulty": record.overlay_difficulty,
                "currentMatch": match,
                "error": record.error,
            }

        overlay_current = self._update_overlay(tosu)
        overlay_candidates = [
            record
            for record in self._records
            if not record.overlay_dismissed and record.state != "failed"
        ]
        overlay_waiting = sorted(
            (
                record
                for record in overlay_candidates
                if overlay_current is not None and record.id != overlay_current.id
            ),
            key=lambda record: (record.created_at, record.id),
        )
        active_records = [
            record
            for record in self._records
            if record.state in {"queued", "processing"}
        ]
        return {
            "tosu": tosu.to_json(
                self.config.use_unicode_web,
                self.config.use_unicode_overlay,
            ),
            "queueCount": len(active_records),
            "waitingQueue": [serialize(record) for record in active_records],
            "requests": [
                serialize(record) for record in reversed(self._records[-50:])
            ],
            "overlay": {
                "current": (
                    serialize(overlay_current) if overlay_current is not None else None
                ),
                "remainingCount": len(overlay_waiting),
                "waiting": [serialize(record) for record in overlay_waiting],
                "playing": self._overlay_playing,
            },
            "generatedAt": time.time(),
        }

    def _set_overlay_current(
        self,
        record: RequestRecord,
        now: float,
        *,
        playing: bool,
    ) -> RequestRecord:
        if self._overlay_current_id != record.id:
            record.overlay_started_at = now
            record.overlay_play_finished_at = 0.0
        self._overlay_current_id = record.id
        self._overlay_playing = playing
        if playing:
            record.overlay_play_finished_at = 0.0
        return record

    def _clear_overlay_current(self) -> None:
        self._overlay_current_id = None
        self._overlay_playing = False

    def _update_overlay(self, tosu: TosuSnapshot) -> RequestRecord | None:
        now = time.time()
        state = tosu.state.casefold()
        current = (
            self._record(self._overlay_current_id)
            if self._overlay_current_id is not None
            else None
        )
        if current is not None and (
            current.overlay_dismissed or current.state == "failed"
        ):
            self._clear_overlay_current()
            current = None

        candidates = [
            record
            for record in self._records
            if not record.overlay_dismissed and record.state != "failed"
        ]
        if state == "play" and tosu.beatmap_id > 0:
            matching = next(
                (
                    record
                    for record in candidates
                    if record.resolved_beatmap_id == tosu.beatmap_id
                ),
                None,
            )
            if matching is not None:
                if current is not None and current.id != matching.id:
                    current.overlay_dismissed = True
                return self._set_overlay_current(matching, now, playing=True)

        if self._overlay_playing:
            if current is None:
                self._clear_overlay_current()
            else:
                switched_away = (
                    tosu.connected
                    and tosu.beatmap_id > 0
                    and current.resolved_beatmap_id > 0
                    and tosu.beatmap_id != current.resolved_beatmap_id
                )
                if not switched_away:
                    if current.overlay_play_finished_at <= 0:
                        current.overlay_play_finished_at = now
                    if (
                        now - current.overlay_play_finished_at
                        < self.config.overlay_played_hold_seconds
                    ):
                        return current
                current.overlay_dismissed = True
                self._clear_overlay_current()
                current = None
                candidates = [
                    record for record in candidates if not record.overlay_dismissed
                ]

        if current is not None:
            if current.state in {"queued", "processing"}:
                return current
            started_at = current.overlay_started_at or current.created_at
            is_selected = (
                tosu.connected
                and tosu.beatmap_id > 0
                and current.resolved_beatmap_id > 0
                and tosu.beatmap_id == current.resolved_beatmap_id
            )
            if is_selected:
                if current.overlay_matched_at <= 0:
                    current.overlay_matched_at = now
                hold_seconds = self.config.overlay_matched_hold_seconds
                hold_started_at = current.overlay_matched_at
            else:
                current.overlay_matched_at = 0.0
                hold_seconds = self.config.overlay_hold_seconds
                hold_started_at = started_at
            if now - hold_started_at < hold_seconds:
                return current
            current.overlay_dismissed = True
            self._clear_overlay_current()
            candidates = [record for record in candidates if record.id != current.id]

        if not candidates:
            return None
        next_record = min(candidates, key=lambda record: (record.created_at, record.id))
        return self._set_overlay_current(next_record, now, playing=False)

    async def _worker(self) -> None:
        while True:
            request = await self.queue.get()
            record = self._record(request.record_id)
            if record is not None:
                record.state = "processing"
            try:
                info = None
                not_found_reasons: list[str] = []
                if self.osu_api is not None and self.osu_api.configured:
                    try:
                        info = await self.osu_api.get_beatmap(request.reference)
                    except BeatmapNotFoundError as exc:
                        not_found_reasons.append(str(exc))
                        logger.warning(
                            "osu! API 未找到谱面，改用网页确认：谱面=%s",
                            request.reference.label,
                        )
                    except Exception as exc:
                        logger.warning(
                            "osu! API 获取谱面资料失败，改用网页解析：谱面=%s，原因=%s",
                            request.reference.label,
                            exc,
                        )
                if info is None:
                    try:
                        info = await self.beatmaps.get(request.reference)
                    except BeatmapNotFoundError as exc:
                        not_found_reasons.append(str(exc))
                        logger.warning(
                            "osu! 网页未找到谱面：谱面=%s",
                            request.reference.label,
                        )
                    except Exception as exc:
                        logger.warning(
                            "获取谱面信息失败，改用基础链接：谱面=%s，原因=%s",
                            request.reference.label,
                            exc,
                        )
                if info is None and not_found_reasons:
                    if request.reference.kind == "beatmap":
                        message = (
                            f"{request.reference.label} 不存在。"
                            f"如果这是 Beatmapset ID，请使用 s/{request.reference.id}"
                        )
                    else:
                        message = (
                            f"{request.reference.label} 不存在或没有可用难度"
                        )
                    raise InvalidSongRequestError(message)
                if record is not None and info is not None:
                    web_artist = (
                        info.artist_unicode
                        if self.config.use_unicode_web
                        else info.artist
                    ) or info.artist
                    web_title = (
                        info.title_unicode
                        if self.config.use_unicode_web
                        else info.title
                    ) or info.title
                    overlay_artist = (
                        info.artist_unicode
                        if self.config.use_unicode_overlay
                        else info.artist
                    ) or info.artist
                    overlay_title = (
                        info.title_unicode
                        if self.config.use_unicode_overlay
                        else info.title
                    ) or info.title
                    record.resolved_beatmap_id = info.beatmap_id
                    record.map_label = (
                        f"{web_artist} - {web_title} [{info.version}]"
                    )
                    record.overlay_map_label = (
                        f"{overlay_artist} - {overlay_title} "
                        f"[{info.version}]"
                    )
                    record.overlay_title_label = (
                        f"{overlay_artist} - {overlay_title}"
                    )
                    record.overlay_difficulty = info.version
                modded_stars = None
                if (
                    info is not None
                    and request.reference.mods
                    and self.osu_api is not None
                    and self.osu_api.configured
                ):
                    try:
                        modded_stars = await self.osu_api.get_modded_stars(
                            info.beatmap_id,
                            request.reference.mods,
                        )
                    except Exception as exc:
                        logger.warning(
                            "osu! API 查询 Mod 星数失败，改用原始星数：谱面=%s，原因=%s",
                            request.reference.label,
                            exc,
                        )
                text = format_irc_request(
                    request.reference,
                    request.requester_name,
                    info,
                    modded_stars,
                    self.config.use_unicode_irc,
                )
                await self.sender.send_privmsg(text)
                if record is not None:
                    record.state = "sent"
                if request.reference.kind == "set" and info is not None:
                    logger.info(
                        "谱面集已选择最高星难度：s/%d -> b/%d",
                        request.reference.id,
                        info.beatmap_id,
                    )
                logger.info("点歌已转发：谱面=%s", request.reference.label)
            except InvalidSongRequestError as exc:
                if record is not None:
                    record.state = "failed"
                    record.error = str(exc)
                logger.warning("无效点歌：用户=%s，原因=%s", request.requester_name, exc)
            except Exception as exc:
                if record is not None:
                    record.state = "failed"
                    record.error = f"{type(exc).__name__}: {exc}".rstrip(": ")
                logger.exception("转发点歌失败：谱面=%s", request.reference.label)
            finally:
                self.queue.task_done()


class DanmakuHandler(blivedm.BaseHandler):
    _CMD_CALLBACK_DICT = dict(blivedm.BaseHandler._CMD_CALLBACK_DICT)
    _CMD_CALLBACK_DICT["LOG_IN_NOTICE"] = None
    _CMD_CALLBACK_DICT["WATCHED_CHANGE"] = None
    _CMD_CALLBACK_DICT["ENTRY_EFFECT_MUST_RECEIVE"] = None
    _CMD_CALLBACK_DICT["ONLINE_RANK_V3"] = None
    _CMD_CALLBACK_DICT["FLOW_REWARD_CARD"] = None
    _CMD_CALLBACK_DICT["LIVE_ANI_RES_UPDATE"] = None
    _CMD_CALLBACK_DICT["LIKE_GUIDE_USER"] = None

    def __init__(self, bridge: RequestBridge) -> None:
        self.bridge = bridge

    def _on_danmaku(
        self,
        client: blivedm.BLiveClient,
        message: web_models.DanmakuMessage,
    ) -> None:
        self.bridge.submit(message)


def _reconnect_interval(retry_count: int, _total_retry_count: int) -> float:
    return min(1 + max(0, retry_count - 1) * 2, 20) + random.uniform(0, 3)


def _create_session(sessdata: str, proxy_url: str) -> aiohttp.ClientSession:
    cookies = http.cookies.SimpleCookie()
    if sessdata:
        cookies["SESSDATA"] = sessdata
        cookies["SESSDATA"]["domain"] = "bilibili.com"
    session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=15),
        trust_env=bool(proxy_url),
    )
    if sessdata:
        session.cookie_jar.update_cookies(cookies)
    return session


async def _open_dashboard(url: str) -> None:
    try:
        await asyncio.to_thread(webbrowser.open, url)
        logger.info("已在默认浏览器打开 Web 队列页面：%s", url)
    except Exception as exc:
        logger.warning("无法自动打开 Web 队列页面，请手动访问 %s：%s", url, exc)


async def run(config: Config) -> None:
    apply_http_proxy(config.proxy_url)
    sender = BanchoIrcClient(
        config.osu_irc_username,
        config.osu_irc_password,
        config.osu_target_username,
        host=config.osu_irc_host,
        port=config.osu_irc_port,
        send_interval_seconds=config.irc_send_interval_seconds,
        proxy_url=config.proxy_url,
    )

    await sender.connect()
    if config.send_startup_message:
        await sender.send_privmsg(
            f"[osu-BiliRequest] 连接成功，正在监听直播间 {config.bili_room_id}。"
        )
        logger.info("已向 osu! 接收者发送连接成功消息")

    session = _create_session(config.bili_sessdata, config.proxy_url)
    osu_api = OsuApiClient(
        session,
        config.osu_api_client_id if config.osu_api_enabled else 0,
        config.osu_api_client_secret if config.osu_api_enabled else "",
    )
    bridge = RequestBridge(config, sender, BeatmapLookup(session), osu_api)
    bridge.start()
    tosu = (
        TosuMonitor(config.tosu_url, config.tosu_poll_interval_seconds)
        if config.tosu_enabled
        else None
    )
    if tosu is not None:
        await tosu.start()
    disabled_tosu = TosuSnapshot(
        enabled=False,
        connected=False,
        error="tosu 状态同步已在配置中关闭",
    )
    dashboard = DashboardServer(
        config.web_port,
        lambda: bridge.dashboard_payload(
            tosu.snapshot if tosu is not None else disabled_tosu
        ),
    )
    try:
        await dashboard.start()
        await _open_dashboard(f"http://127.0.0.1:{config.web_port}/")
    except OSError as exc:
        logger.warning("Web 队列页面启动失败：%s", exc)
        await dashboard.close()
    client = blivedm.BLiveClient(
        config.bili_room_id,
        session=session,
        heartbeat_interval=10,
    )
    client.set_reconnect_policy(_reconnect_interval)
    client.set_handler(DanmakuHandler(bridge))
    client.start()

    if not config.bili_sessdata:
        logger.warning(
            "bilibili当前为匿名连接，观众昵称可能显示为 M***；"
            "运行 configure.bat 并填写 SESSDATA 后可读取完整昵称"
        )
    logger.info("开始监听 bilibili直播间 %d", config.bili_room_id)
    try:
        await client.join()
    finally:
        await client.stop_and_close()
        await dashboard.close()
        if tosu is not None:
            await tosu.close()
        await bridge.close()
        await session.close()
