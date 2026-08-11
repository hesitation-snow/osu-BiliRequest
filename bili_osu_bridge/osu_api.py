from __future__ import annotations

import asyncio
import time

import aiohttp

from .beatmap import BeatmapInfo, BeatmapNotFoundError, BeatmapReference


class OsuApiClient:
    """Small osu! API v2 client for beatmap metadata and difficulty data."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: int,
        client_secret: str,
        *,
        oauth_url: str = "https://osu.ppy.sh/oauth/token",
        api_base_url: str = "https://osu.ppy.sh/api/v2",
    ) -> None:
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_url = oauth_url
        self.api_base_url = api_base_url.rstrip("/")
        self._token = ""
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._beatmap_cache: dict[str, tuple[float, BeatmapInfo]] = {}

    @property
    def configured(self) -> bool:
        return self.client_id > 0 and bool(self.client_secret)

    async def _get_token(self, *, force_refresh: bool = False) -> str:
        if not self.configured:
            raise RuntimeError("osu! API 尚未配置")
        if not force_refresh and self._token and time.monotonic() < self._token_expires_at:
            return self._token

        async with self._token_lock:
            if not force_refresh and self._token and time.monotonic() < self._token_expires_at:
                return self._token
            async with self.session.post(
                self.oauth_url,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "public",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json()
            token = str(payload.get("access_token") or "")
            if not token:
                raise ValueError("osu! API 登录响应缺少 access_token")
            expires_in = max(60, int(payload.get("expires_in") or 3600))
            self._token = token
            self._token_expires_at = time.monotonic() + max(30, expires_in - 60)
            return token

    async def get_modded_stars(
        self,
        beatmap_id: int,
        mods: tuple[str, ...],
    ) -> float:
        if not mods:
            raise ValueError("查询 Mod 后星数时必须提供 Mods")

        for attempt in range(2):
            token = await self._get_token(force_refresh=attempt > 0)
            async with self.session.post(
                f"{self.api_base_url}/beatmaps/{beatmap_id}/attributes",
                headers={"Authorization": f"Bearer {token}"},
                json={"mods": list(mods)},
            ) as response:
                if response.status == 401 and attempt == 0:
                    self._token = ""
                    continue
                if response.status == 404:
                    raise BeatmapNotFoundError(
                        f"osu! API 中没有找到 b/{beatmap_id}"
                    )
                response.raise_for_status()
                payload = await response.json()
            stars = float((payload.get("attributes") or {}).get("star_rating"))
            if stars < 0:
                raise ValueError("osu! API 返回了无效星数")
            return stars
        raise RuntimeError("osu! API 身份验证失败")

    async def get_beatmap(self, reference: BeatmapReference) -> BeatmapInfo:
        cached = self._beatmap_cache.get(reference.key)
        now = time.monotonic()
        if cached is not None and now - cached[0] < 3600:
            return cached[1]

        endpoint = (
            f"{self.api_base_url}/beatmaps/{reference.id}"
            if reference.kind == "beatmap"
            else f"{self.api_base_url}/beatmapsets/{reference.id}"
        )
        payload: dict | None = None
        for attempt in range(2):
            token = await self._get_token(force_refresh=attempt > 0)
            async with self.session.get(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
            ) as response:
                if response.status == 401 and attempt == 0:
                    self._token = ""
                    continue
                if response.status == 404:
                    raise BeatmapNotFoundError(
                        f"osu! API 中没有找到 {reference.label}"
                    )
                response.raise_for_status()
                payload = await response.json()
            break
        if payload is None:
            raise RuntimeError("osu! API 身份验证失败")

        if reference.kind == "beatmap":
            beatmap = payload
            beatmapset = payload.get("beatmapset") or {}
        else:
            beatmapset = payload
            beatmaps = payload.get("beatmaps") or []
            beatmap = max(
                beatmaps,
                key=lambda item: float(item.get("difficulty_rating") or 0),
                default=None,
            )
            if beatmap is None:
                raise BeatmapNotFoundError(
                    "osu! API 返回的谱面集中没有可用难度"
                )

        beatmap_id = int(beatmap.get("id") or 0)
        if beatmap_id <= 0:
            raise ValueError("osu! API 返回的谱面缺少 Beatmap ID")
        raw_status = str(
            beatmap.get("status") or beatmapset.get("status") or "Unknown"
        )
        info = BeatmapInfo(
            beatmap_id=beatmap_id,
            status=raw_status.replace("_", " ").title(),
            artist=str(beatmapset.get("artist") or beatmapset.get("artist_unicode") or "Unknown Artist"),
            title=str(beatmapset.get("title") or beatmapset.get("title_unicode") or "Unknown Title"),
            version=str(beatmap.get("version") or "Unknown Difficulty"),
            bpm=float(beatmap.get("bpm") or beatmapset.get("bpm") or 0),
            stars=float(beatmap.get("difficulty_rating") or 0),
            total_length=max(0, int(beatmap.get("total_length") or 0)),
            beatmapset_id=max(
                0,
                int(beatmapset.get("id") or beatmap.get("beatmapset_id") or 0),
            ),
            artist_unicode=str(
                beatmapset.get("artist_unicode") or beatmapset.get("artist") or "Unknown Artist"
            ),
            title_unicode=str(
                beatmapset.get("title_unicode") or beatmapset.get("title") or "Unknown Title"
            ),
        )
        self._beatmap_cache[reference.key] = (now, info)
        return info
