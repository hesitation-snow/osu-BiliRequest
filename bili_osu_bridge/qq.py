from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from collections.abc import Callable
from typing import Any

import aiohttp

from .messages import RequestMessage


logger = logging.getLogger(__name__)

_ACCESS_TOKEN_URL = "https://api.bot.qq.com/app/getAppAccessToken"
_GATEWAY_URL = "https://api.bot.qq.com/gateway"
_MESSAGE_API_BASE = "https://api.sgroup.qq.com"
_GROUP_AND_C2C_EVENT_INTENT = 1 << 25
_SUPPORTED_EVENTS = {
    "C2C_MESSAGE_CREATE",
    "GROUP_AT_MESSAGE_CREATE",
    "GROUP_MESSAGE_CREATE",
}


class QQBotClient:
    """Minimal QQ official-bot Gateway client for song-request messages."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        app_id: str,
        app_secret: str,
        on_message: Callable[[RequestMessage], None],
        *,
        allowed_group_openids: tuple[str, ...] = (),
    ) -> None:
        self.session = session
        self.app_id = app_id
        self.app_secret = app_secret
        self.on_message = on_message
        self.allowed_group_openids = set(allowed_group_openids)

        self._task: asyncio.Task[None] | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._access_token = ""
        self._access_token_expires_at = 0.0
        self._session_id = ""
        self._sequence: int | None = None
        self._seen_message_ids: set[str] = set()
        self._seen_message_order: deque[str] = deque()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="qq-bot")

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def _get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._access_token_expires_at:
            return self._access_token
        async with self.session.post(
            _ACCESS_TOKEN_URL,
            json={"appId": self.app_id, "clientSecret": self.app_secret},
        ) as response:
            payload = await response.json(content_type=None)
            if response.status != 200:
                if response.status in {401, 403}:
                    self._access_token = ""
                    self._access_token_expires_at = 0.0
                raise RuntimeError(
                    f"QQ Access Token 获取失败：HTTP {response.status} {payload}"
                )
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError(f"QQ Access Token 响应缺少 access_token：{payload}")
        try:
            expires_in = max(120, int(payload.get("expires_in") or 7200))
        except (TypeError, ValueError):
            expires_in = 7200
        self._access_token = token
        self._access_token_expires_at = time.monotonic() + max(60, expires_in - 60)
        return token

    async def _get_gateway(self, token: str) -> str:
        async with self.session.get(
            _GATEWAY_URL,
            headers={"Authorization": f"QQBot {token}"},
        ) as response:
            payload = await response.json(content_type=None)
            if response.status != 200:
                raise RuntimeError(
                    f"QQ Gateway 地址获取失败：HTTP {response.status} {payload}"
                )
        url = str(payload.get("url") or "").strip()
        if not url.startswith("wss://"):
            raise RuntimeError(f"QQ Gateway 响应地址无效：{url or payload}")
        return url

    async def _run(self) -> None:
        retry_count = 0
        while True:
            try:
                await self._connect_once()
                retry_count = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                retry_count += 1
                delay = min(2 ** min(retry_count, 5), 30) + random.random()
                logger.exception("QQ 机器人连接中断，%.1f 秒后重连", delay)
                await asyncio.sleep(delay)

    async def _connect_once(self) -> None:
        token = await self._get_access_token()
        gateway = await self._get_gateway(token)
        async with self.session.ws_connect(gateway, autoping=True) as ws:
            self._ws = ws
            hello = await ws.receive_json(timeout=20)
            if int(hello.get("op", -1)) != 10:
                raise RuntimeError(f"QQ Gateway 未返回 Hello：{hello}")
            interval_ms = int((hello.get("d") or {}).get("heartbeat_interval") or 45000)

            if self._session_id and self._sequence is not None:
                await ws.send_json(
                    {
                        "op": 6,
                        "d": {
                            "token": f"QQBot {token}",
                            "session_id": self._session_id,
                            "seq": self._sequence,
                        },
                    }
                )
            else:
                await ws.send_json(
                    {
                        "op": 2,
                        "d": {
                            "token": f"QQBot {token}",
                            "intents": _GROUP_AND_C2C_EVENT_INTENT,
                            "shard": [0, 1],
                            "properties": {
                                "$os": "windows",
                                "$browser": "osu-BiliRequest",
                                "$device": "osu-BiliRequest",
                            },
                        },
                    }
                )

            heartbeat = asyncio.create_task(
                self._heartbeat(ws, interval_ms / 1000), name="qq-heartbeat"
            )
            logger.info("QQ 官方机器人正在连接 Gateway")
            try:
                async for item in ws:
                    if item.type == aiohttp.WSMsgType.TEXT:
                        payload = item.json()
                        await self._handle_payload(ws, payload)
                    elif item.type in {
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    }:
                        break
            finally:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
                self._ws = None
        raise ConnectionError("QQ Gateway 连接已关闭")

    async def _heartbeat(
        self, ws: aiohttp.ClientWebSocketResponse, interval_seconds: float
    ) -> None:
        await asyncio.sleep(random.random() * min(interval_seconds, 5))
        while not ws.closed:
            await ws.send_json({"op": 1, "d": self._sequence})
            await asyncio.sleep(max(1.0, interval_seconds))

    async def _handle_payload(
        self, ws: aiohttp.ClientWebSocketResponse, payload: dict[str, Any]
    ) -> None:
        sequence = payload.get("s")
        if isinstance(sequence, int):
            self._sequence = sequence
        opcode = int(payload.get("op", -1))
        if opcode == 0:
            event = str(payload.get("t") or "")
            data = payload.get("d") or {}
            if event == "READY":
                self._session_id = str(data.get("session_id") or "")
                robot = data.get("user") or {}
                logger.info("QQ 官方机器人已连接：%s", robot.get("username") or self.app_id)
            elif event == "RESUMED":
                logger.info("QQ 官方机器人会话已恢复")
            elif event in _SUPPORTED_EVENTS and isinstance(data, dict):
                self._handle_message_event(event, data)
        elif opcode == 1:
            await ws.send_json({"op": 1, "d": self._sequence})
        elif opcode == 7:
            await ws.close()
        elif opcode == 9:
            self._session_id = ""
            self._sequence = None
            await ws.close()

    def _handle_message_event(self, event: str, data: dict[str, Any]) -> None:
        message_id = str(data.get("id") or "")
        if message_id and not self._remember_message(message_id):
            return
        author = data.get("author") or {}
        if not isinstance(author, dict) or author.get("bot"):
            return
        group_openid = str(data.get("group_openid") or "")
        if (
            event in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}
            and self.allowed_group_openids
            and group_openid not in self.allowed_group_openids
        ):
            return
        user_id = str(
            author.get("member_openid")
            or author.get("user_openid")
            or author.get("id")
            or ""
        )
        member = data.get("member") or {}
        if not isinstance(member, dict):
            member = {}
        username = str(
            member.get("nick")
            or member.get("nickname")
            or author.get("nickname")
            or author.get("username")
            or author.get("name")
            or "群友"
        ).strip() or "群友"
        avatar_url = str(
            member.get("avatar")
            or member.get("avatar_url")
            or author.get("avatar")
            or author.get("avatar_url")
            or ""
        ).strip()

        async def reply(content: str) -> None:
            await self._send_reply(
                group_openid=group_openid,
                user_openid=user_id,
                message_id=message_id,
                content=content,
            )

        self.on_message(
            RequestMessage(
                source="qq",
                user_id=user_id,
                username=username,
                content=str(data.get("content") or "").strip(),
                avatar_url=avatar_url,
                scope_id=group_openid or user_id,
                is_private=event == "C2C_MESSAGE_CREATE",
                reply=reply,
            )
        )

    async def _send_reply(
        self,
        *,
        group_openid: str,
        user_openid: str,
        message_id: str,
        content: str,
    ) -> None:
        if not message_id:
            raise ValueError("QQ 回复缺少原消息 ID")
        target = group_openid or user_openid
        if not target:
            raise ValueError("QQ 回复缺少群或用户 OpenID")
        token = await self._get_access_token()
        if group_openid:
            url = f"{_MESSAGE_API_BASE}/v2/groups/{group_openid}/messages"
        else:
            url = f"{_MESSAGE_API_BASE}/v2/users/{user_openid}/messages"
        payload = {
            "content": str(content).strip()[:1800],
            "msg_type": 0,
            "msg_id": message_id,
        }
        async with self.session.post(
            url,
            headers={
                "Authorization": f"QQBot {token}",
                "X-Union-Appid": self.app_id,
            },
            json=payload,
        ) as response:
            response_text = await response.text()
            if response.status not in {200, 201}:
                raise RuntimeError(
                    f"QQ 消息回复失败：HTTP {response.status} {response_text}"
                )

    def _remember_message(self, message_id: str) -> bool:
        if message_id in self._seen_message_ids:
            return False
        self._seen_message_ids.add(message_id)
        self._seen_message_order.append(message_id)
        while len(self._seen_message_order) > 1000:
            expired = self._seen_message_order.popleft()
            self._seen_message_ids.discard(expired)
        return True
