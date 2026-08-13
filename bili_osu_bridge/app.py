from __future__ import annotations

import asyncio
import http.cookies
import logging
import random
import re
import time
import webbrowser
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import blivedm
import blivedm.models.web as web_models

from .config import Config
from .dashboard import DashboardServer
from .beatmap import BeatmapLookup, BeatmapNotFoundError, BeatmapReference
from .irc import BanchoIrcClient
from .limiter import RequestLimiter
from .messages import RequestMessage
from .network import apply_http_proxy
from .osu_api import OsuApiClient
from .parser import (
    format_duration,
    format_irc_request,
    parse_beatmap_reference,
    parse_osu_beatmap_url,
)
from .qq import QQBotClient
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
    reply: Callable[[str], Awaitable[None]] | None = None


@dataclass
class RequestRecord:
    id: int
    created_at: float
    source: str
    user_key: str
    requester_name: str
    avatar_url: str
    overlay_avatar_url: str
    reference_label: str
    requested_beatmap_id: int
    state: str = "queued"
    resolved_beatmap_id: int = 0
    map_label: str = ""
    overlay_map_label: str = ""
    overlay_title_label: str = ""
    overlay_difficulty: str = ""
    duration_label: str = ""
    stars_label: str = ""
    error: str = ""
    overlay_started_at: float = 0.0
    overlay_matched_at: float = 0.0
    overlay_play_finished_at: float = 0.0
    overlay_dismissed: bool = False


class RequestBridge:
    def __init__(
        self,
        config: Config,
        sender: BanchoIrcClient | None,
        beatmaps: BeatmapLookup,
        osu_api: OsuApiClient | None = None,
        tosu_snapshot_provider: Callable[[], TosuSnapshot] | None = None,
    ) -> None:
        self.config = config
        self.sender = sender
        self.beatmaps = beatmaps
        self.osu_api = osu_api
        self.tosu_snapshot_provider = tosu_snapshot_provider
        self.queue: asyncio.Queue[SongRequest] = asyncio.Queue(config.queue_max_size)
        self.limiter = RequestLimiter(
            config.user_cooldown_seconds,
            config.map_dedupe_seconds,
        )
        self._blacklisted_ids = set(config.blacklisted_user_ids)
        self._qq_owner_ids = set(config.qq_owner_openids)
        self._blacklisted_beatmap_ids = {
            str(int(value)) for value in config.blacklisted_beatmap_ids
        }
        self._worker_task: asyncio.Task | None = None
        self._next_record_id = 1
        self._records: list[RequestRecord] = []
        self._overlay_current_id: int | None = None
        self._overlay_playing = False
        self._reply_tasks: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._worker())

    async def close(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
        for task in tuple(self._reply_tasks):
            task.cancel()
        if self._reply_tasks:
            await asyncio.gather(*self._reply_tasks, return_exceptions=True)
        if self.sender is not None:
            await self.sender.close()

    def _reply(
        self,
        callback: Callable[[str], Awaitable[None]] | None,
        text: str,
    ) -> None:
        if callback is None:
            return

        async def send() -> None:
            try:
                await callback(text)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("QQ 回复发送失败：%s", exc)

        task = asyncio.create_task(send(), name="qq-reply")
        self._reply_tasks.add(task)
        task.add_done_callback(self._reply_tasks.discard)

    def _handle_qq_command(self, message: RequestMessage) -> bool:
        raw = " ".join(message.content.strip().split()).casefold()
        command = raw.replace("！", "!", 1)
        if command.startswith("/"):
            command = "!" + command[1:]
        skip_match = re.fullmatch(r"!skip(?:\s+([1-9][0-9]{0,2}))?", command)
        if command not in {"!list", "!np", "!help", "!ownerid"} and skip_match is None:
            return False
        if command == "!ownerid":
            self._reply(
                message.reply,
                "你的机器人专属 OpenID：\n"
                f"{message.user_id}\n\n"
                "请复制到 Web 设置的“主播 OpenID”。它不是 QQ 号。",
            )
            return True
        if command == "!help":
            self._reply(
                message.reply,
                "点歌\n"
                "发送 osu! 谱面链接或 beatmap ID\n\n"
                "指令\n"
                "/list  查看点歌列表\n"
                "/np  查看主播正在听的谱面\n"
                "/skip [序号]  跳过点歌\n"
                "/help  显示本帮助",
            )
            return True
        if command == "!np":
            snapshot = (
                self.tosu_snapshot_provider()
                if self.tosu_snapshot_provider is not None
                else TosuSnapshot(enabled=False, error="tosu 未启用")
            )
            if not snapshot.enabled:
                text = "当前未启用 tosu，无法读取主播正在游玩的谱面。"
            elif not snapshot.connected:
                text = "tosu 暂未连接，无法读取主播当前谱面。"
            elif not snapshot.beatmap_id:
                text = f"主播当前没有加载谱面（状态：{snapshot.state or '未知'}）。"
            else:
                artist = (
                    snapshot.artist_unicode or snapshot.artist
                    if self.config.use_unicode_web
                    else snapshot.artist or snapshot.artist_unicode
                ) or "Unknown Artist"
                title = (
                    snapshot.title_unicode or snapshot.title
                    if self.config.use_unicode_web
                    else snapshot.title or snapshot.title_unicode
                ) or "Unknown Title"
                text = (
                    f"主播正在听：{artist} - {title}\n"
                    f"https://osu.ppy.sh/b/{snapshot.beatmap_id}"
                )
            self._reply(message.reply, text)
            return True

        items = self._qq_list_items()
        if skip_match is not None:
            position = int(skip_match.group(1) or 1)
            if position > len(items):
                self._reply(message.reply, f"序号 {position} 不在当前点歌列表中，请先发送 /list。")
                return True
            record = items[position - 1]
            is_owner = message.user_id in self._qq_owner_ids
            if record.user_key != message.user_key and not is_owner:
                self._reply(message.reply, "只能跳过自己提交的点歌；主播可以跳过任意项目。")
                return True
            record.overlay_dismissed = True
            record.state = "skipped"
            if self._overlay_current_id == record.id:
                self._clear_overlay_current()
            self._reply(
                message.reply,
                f"已跳过：{record.map_label or record.reference_label}",
            )
            logger.info(
                "群友跳过自己的点歌：用户=%s，谱面=%s",
                message.username or "群友",
                record.reference_label,
            )
            return True

        if not items:
            self._reply(message.reply, "当前点歌列表为空。")
            return True
        lines = ["当前点歌列表："]
        for index, record in enumerate(items[:8], 1):
            label = record.map_label or record.reference_label
            details = " · ".join(
                value
                for value in (
                    record.duration_label or "时长解析中",
                    record.stars_label or "星数解析中",
                )
                if value
            )
            lines.append(f"{index}. {label} · {details} — {record.requester_name}")
        if len(items) > 8:
            lines.append(f"还有 {len(items) - 8} 首未显示。")
        self._reply(message.reply, "\n".join(lines))
        return True

    def _qq_list_items(self) -> list[RequestRecord]:
        return sorted(
            (
                record
                for record in self._records
                if not record.overlay_dismissed
                and record.state not in {"failed", "skipped"}
            ),
            key=lambda record: (record.created_at, record.id),
        )

    def submit(self, message: web_models.DanmakuMessage) -> None:
        if message.dm_type != 0:
            return
        user_id = str(message.uid or message.uid_crc32 or "")
        self.submit_message(
            RequestMessage(
                source="bilibili",
                user_id=user_id,
                username=message.uname or "观众",
                content=message.msg,
                avatar_url=message.face or "",
                scope_id=str(self.config.bili_room_id),
            )
        )

    def submit_message(self, message: RequestMessage) -> None:
        if message.source == "qq" and self._handle_qq_command(message):
            return
        reference = parse_beatmap_reference(
            message.content,
            self.config.request_keywords,
        )
        if reference is None and message.source == "qq":
            reference = parse_osu_beatmap_url(
                message.content,
                self.config.request_keywords,
            )
        if reference is None:
            return

        uid = message.user_id.strip()
        username = message.username.strip()
        if uid in self._blacklisted_ids:
            logger.info(
                "忽略黑名单用户点歌：来源=%s，用户=%s，UID/OpenID=%s，谱面=%s",
                message.source,
                username or "匿名",
                uid or "未知",
                reference.label,
            )
            self._reply(message.reply, "你的点歌请求未被接受。")
            return
        if str(reference.id) in self._blacklisted_beatmap_ids:
            logger.info(
                "忽略谱面数字黑名单：来源=%s，用户=%s，谱面=%s",
                message.source,
                username or "匿名",
                reference.label,
            )
            self._reply(message.reply, f"数字 {reference.id} 已被点歌规则屏蔽。")
            return

        user_key = message.user_key
        accepted, reason = self.limiter.accept(user_key, reference.key)
        if not accepted:
            logger.info(
                "忽略点歌：%s，来源=%s，用户=%s，谱面=%s",
                reason,
                message.source,
                username or "匿名",
                reference.label,
            )
            self._reply(message.reply, f"点歌未接受：{reason}。")
            return

        record_id = self._next_record_id
        request = SongRequest(
            reference,
            username or ("群友" if message.source == "qq" else "观众"),
            user_key,
            record_id,
            message.reply,
        )
        try:
            self.queue.put_nowait(request)
        except asyncio.QueueFull:
            logger.warning("点歌队列已满，忽略谱面 %s", reference.label)
            self._reply(message.reply, "点歌队列已满，请稍后再试。")
            return

        self._next_record_id += 1
        requested_beatmap_id = reference.id if reference.kind == "beatmap" else 0
        avatar_url = _safe_avatar_url(message.avatar_url)
        self._records.append(
            RequestRecord(
                id=record_id,
                created_at=time.time(),
                source=message.source,
                user_key=user_key,
                requester_name=request.requester_name,
                avatar_url=avatar_url,
                overlay_avatar_url=avatar_url,
                reference_label=reference.label,
                requested_beatmap_id=requested_beatmap_id,
                resolved_beatmap_id=requested_beatmap_id,
            )
        )
        self._records = self._records[-100:]

        logger.info(
            "收到点歌：来源=%s，范围=%s，用户=%s，谱面=%s，队列=%d",
            message.source,
            message.scope_id or "-",
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
                "source": record.source,
                "requester": record.requester_name,
                "avatarUrl": record.avatar_url,
                "overlayAvatarUrl": record.overlay_avatar_url,
                "reference": record.reference_label,
                "state": record.state,
                "resolvedBeatmapId": record.resolved_beatmap_id,
                "mapLabel": record.map_label,
                "overlayMapLabel": record.overlay_map_label,
                "overlayTitleLabel": record.overlay_title_label,
                "overlayDifficulty": record.overlay_difficulty,
                "durationLabel": record.duration_label,
                "starsLabel": record.stars_label,
                "currentMatch": match,
                "error": record.error,
            }

        overlay_current = self._update_overlay(tosu)
        overlay_candidates = [
            record
            for record in self._records
            if not record.overlay_dismissed
            and record.state not in {"failed", "skipped"}
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
            if record is not None and record.state == "skipped":
                self.queue.task_done()
                continue
            if record is not None:
                record.state = "processing"
            try:
                info = None
                not_found_reasons: list[str] = []
                if self.osu_api is not None and self.osu_api.configured:
                    try:
                        info = await self.osu_api.get_beatmap(request.reference)
                    except BeatmapNotFoundError:
                        logger.warning(
                            "osu! API 已确认谱面不存在：谱面=%s",
                            request.reference.label,
                        )
                        if request.reference.kind == "beatmap":
                            raise InvalidSongRequestError(
                                f"{request.reference.label} 不存在。"
                                "如果这是 beatmapset ID，"
                                f"请使用 s/{request.reference.id}"
                            )
                        raise InvalidSongRequestError(
                            f"{request.reference.label} 不存在或没有可用难度"
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
                            f"如果这是 beatmapset ID，请使用 s/{request.reference.id}"
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
                    if record.source == "qq" and info.beatmapset_id > 0:
                        record.overlay_avatar_url = (
                            "https://assets.ppy.sh/beatmaps/"
                            f"{info.beatmapset_id}/covers/list.jpg"
                        )
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
                if record is not None and record.state == "skipped":
                    logger.info("已跳过点歌，不发送 IRC：谱面=%s", request.reference.label)
                    continue
                if record is not None and info is not None:
                    rate = (
                        1.5
                        if {"DT", "NC"} & set(request.reference.mods)
                        else 0.75
                        if "HT" in request.reference.mods
                        else 1.0
                    )
                    record.duration_label = format_duration(
                        round(info.total_length / rate)
                    )
                    if request.reference.mods and modded_stars is None:
                        record.stars_label = f"base {info.stars:.2f}*"
                    else:
                        record.stars_label = f"{(modded_stars if modded_stars is not None else info.stars):.2f}*"
                text = format_irc_request(
                    request.reference,
                    request.requester_name,
                    info,
                    modded_stars=modded_stars,
                    use_unicode_metadata=self.config.use_unicode_irc,
                    message_template=self.config.irc_message_template,
                    fallback_template=self.config.irc_fallback_template,
                    platform=record.source if record is not None else "",
                )
                if self.sender is not None:
                    await self.sender.send_privmsg(text)
                if record is not None:
                    record.state = "sent"
                if request.reference.kind == "set" and info is not None:
                    logger.info(
                        "谱面集已选择最高星难度：s/%d -> b/%d",
                        request.reference.id,
                        info.beatmap_id,
                    )
                logger.info(
                    "点歌%s：谱面=%s",
                    "已转发" if self.sender is not None else "已加入队列（IRC 已停用）",
                    request.reference.label,
                )
                success_label = (
                    record.map_label
                    if record is not None and record.map_label
                    else request.reference.label
                )
                self._reply(
                    request.reply,
                    (
                        f"点歌推送成功：{success_label}"
                        if self.sender is not None
                        else f"点歌已加入队列：{success_label}"
                    ),
                )
            except InvalidSongRequestError as exc:
                if record is not None:
                    record.state = "failed"
                    record.error = str(exc)
                logger.warning("无效点歌：用户=%s，原因=%s", request.requester_name, exc)
                self._reply(request.reply, f"点歌失败：{exc}")
            except Exception as exc:
                if record is not None:
                    record.state = "failed"
                    record.error = f"{type(exc).__name__}: {exc}".rstrip(": ")
                logger.exception("转发点歌失败：谱面=%s", request.reference.label)
                self._reply(request.reply, "点歌转发失败，请稍后再试或联系主播查看日志。")
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


async def run(config: Config, config_path: Path | None = None) -> bool:
    apply_http_proxy(config.proxy_url)
    sender = (
        BanchoIrcClient(
            config.osu_irc_username,
            config.osu_irc_password,
            config.osu_target_username,
            host=config.osu_irc_host,
            port=config.osu_irc_port,
            send_interval_seconds=config.irc_send_interval_seconds,
            proxy_url=config.proxy_url,
        )
        if config.osu_irc_enabled
        else None
    )

    if sender is not None:
        await sender.connect()
        if config.send_startup_message:
            await sender.send_privmsg(
                f"[osu-BiliRequest] 连接成功，正在监听直播间 {config.bili_room_id}。"
            )
            logger.info("已向 osu! 接收者发送连接成功消息")
    else:
        logger.info("osu! IRC 转发已停用；Web、Overlay 和点歌队列仍会运行")

    session = _create_session(config.bili_sessdata, config.proxy_url)
    osu_api = OsuApiClient(
        session,
        config.osu_api_client_id if config.osu_api_enabled else 0,
        config.osu_api_client_secret if config.osu_api_enabled else "",
    )
    tosu = (
        TosuMonitor(config.tosu_url, config.tosu_poll_interval_seconds)
        if config.tosu_enabled
        else None
    )
    disabled_tosu = TosuSnapshot(
        enabled=False,
        connected=False,
        error="tosu 状态同步已在配置中关闭",
    )
    bridge = RequestBridge(
        config,
        sender,
        BeatmapLookup(session),
        osu_api,
        lambda: tosu.snapshot if tosu is not None else disabled_tosu,
    )
    bridge.start()
    qq_client = (
        QQBotClient(
            session,
            config.qq_app_id,
            config.qq_app_secret,
            bridge.submit_message,
            allowed_group_openids=config.qq_allowed_group_openids,
        )
        if config.qq_enabled
        else None
    )
    if qq_client is not None:
        qq_client.start()
    if tosu is not None:
        await tosu.start()
    dashboard = DashboardServer(
        config.web_port,
        lambda: bridge.dashboard_payload(
            tosu.snapshot if tosu is not None else disabled_tosu
        ),
        config_path,
    )
    dashboard_started = False
    try:
        await dashboard.start()
        dashboard_started = True
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
    restart_requested = False
    try:
        if dashboard_started:
            client_task = asyncio.create_task(client.join(), name="bilibili-client")
            restart_task = asyncio.create_task(
                dashboard.wait_for_restart(), name="web-restart"
            )
            done, pending = await asyncio.wait(
                {client_task, restart_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            restart_requested = restart_task in done
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if client_task in done:
                await client_task
        else:
            await client.join()
    finally:
        await client.stop_and_close()
        await dashboard.close()
        if tosu is not None:
            await tosu.close()
        if qq_client is not None:
            await qq_client.close()
        await bridge.close()
        await session.close()
    return restart_requested
