from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import aiohttp


logger = logging.getLogger(__name__)


def _text(value: object) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


@dataclass(frozen=True)
class TosuSnapshot:
    enabled: bool = True
    connected: bool = False
    beatmap_id: int = 0
    artist: str = ""
    artist_unicode: str = ""
    title: str = ""
    title_unicode: str = ""
    version: str = ""
    state: str = ""
    error: str = ""
    updated_at: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict) -> "TosuSnapshot":
        beatmap = payload.get("beatmap") or {}
        state = payload.get("state") or {}
        try:
            beatmap_id = max(0, int(beatmap.get("id") or 0))
        except (TypeError, ValueError):
            beatmap_id = 0
        return cls(
            connected=True,
            beatmap_id=beatmap_id,
            artist=_text(beatmap.get("artist")),
            artist_unicode=_text(beatmap.get("artistUnicode")),
            title=_text(beatmap.get("title")),
            title_unicode=_text(beatmap.get("titleUnicode")),
            version=_text(beatmap.get("version")),
            state=_text(state.get("name") if isinstance(state, dict) else state),
            updated_at=time.time(),
        )

    @property
    def beatmap_label(self) -> str:
        if not self.beatmap_id:
            return "未加载谱面"
        artist = self.artist or "Unknown Artist"
        title = self.title or "Unknown Title"
        version = f" [{self.version}]" if self.version else ""
        return f"{artist} - {title}{version}"

    @property
    def beatmap_unicode_label(self) -> str:
        if not self.beatmap_id:
            return "未加载谱面"
        artist = self.artist_unicode or self.artist or "Unknown Artist"
        title = self.title_unicode or self.title or "Unknown Title"
        version = f" [{self.version}]" if self.version else ""
        return f"{artist} - {title}{version}"

    def to_json(
        self,
        use_unicode_web: bool = True,
        use_unicode_overlay: bool | None = None,
    ) -> dict:
        if use_unicode_overlay is None:
            use_unicode_overlay = use_unicode_web

        def preferred(unicode_value: str, normal_value: str, use_unicode: bool) -> str:
            if use_unicode:
                return unicode_value or normal_value
            return normal_value or unicode_value

        display_artist = preferred(
            self.artist_unicode,
            self.artist,
            use_unicode_web,
        ) or "Unknown Artist"
        display_title = preferred(
            self.title_unicode,
            self.title,
            use_unicode_web,
        ) or "Unknown Title"
        overlay_artist = preferred(
            self.artist_unicode,
            self.artist,
            use_unicode_overlay,
        ) or "Unknown Artist"
        overlay_title = preferred(
            self.title_unicode,
            self.title,
            use_unicode_overlay,
        ) or "Unknown Title"
        display_version = f" [{self.version}]" if self.version else ""
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "beatmapId": self.beatmap_id,
            "beatmapLabel": self.beatmap_label,
            "beatmapUnicodeLabel": self.beatmap_unicode_label,
            "beatmapUnicodeTitle": (
                f"{self.artist_unicode or self.artist or 'Unknown Artist'} - "
                f"{self.title_unicode or self.title or 'Unknown Title'}"
                if self.beatmap_id
                else ""
            ),
            "beatmapVersion": self.version,
            "beatmapDisplayTitle": (
                f"{display_artist} - {display_title}" if self.beatmap_id else ""
            ),
            "beatmapOverlayTitle": (
                f"{overlay_artist} - {overlay_title}" if self.beatmap_id else ""
            ),
            "beatmapDisplayLabel": (
                f"{display_artist} - {display_title}{display_version}"
                if self.beatmap_id
                else "未加载谱面"
            ),
            "state": self.state,
            "error": self.error,
            "updatedAt": self.updated_at,
        }


class TosuMonitor:
    def __init__(self, url: str, poll_interval_seconds: float = 1.0) -> None:
        self.url = url
        self.poll_interval_seconds = poll_interval_seconds
        self.snapshot = TosuSnapshot()
        self._session: aiohttp.ClientSession | None = None
        self._task: asyncio.Task | None = None
        self._was_connected: bool | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=3),
            trust_env=False,
        )
        self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def refresh(self) -> TosuSnapshot:
        if self._session is None:
            raise RuntimeError("tosu monitor 尚未启动")
        async with self._session.get(self.url) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
        if not isinstance(payload, dict):
            raise ValueError("tosu 返回内容不是 JSON 对象")
        self.snapshot = TosuSnapshot.from_payload(payload)
        return self.snapshot

    async def _run(self) -> None:
        while True:
            try:
                await self.refresh()
                if self._was_connected is not True:
                    logger.info("tosu 已连接：%s", self.url)
                self._was_connected = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}".rstrip(": ")
                self.snapshot = TosuSnapshot(
                    connected=False,
                    error=error,
                    updated_at=time.time(),
                )
                if self._was_connected is not False:
                    logger.warning("tosu 暂时无法连接：%s", error)
                self._was_connected = False
            await asyncio.sleep(self.poll_interval_seconds)
