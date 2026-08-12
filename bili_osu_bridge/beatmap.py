from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Literal

import aiohttp


_BEATMAPSET_JSON_PATTERN = re.compile(
    r'<script\b[^>]*\bid=["\']json-beatmapset["\'][^>]*>(.*?)</script\s*>',
    re.IGNORECASE | re.DOTALL,
)

_STATUS_NAMES = {
    "ranked": "Ranked",
    "approved": "Approved",
    "qualified": "Qualified",
    "loved": "Loved",
    "pending": "Pending",
    "wip": "WIP",
    "graveyard": "Graveyard",
}


class BeatmapNotFoundError(ValueError):
    """The requested beatmap or beatmapset definitively has no usable result."""


@dataclass(frozen=True)
class BeatmapReference:
    kind: Literal["beatmap", "set"]
    id: int
    mods: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.id}"

    @property
    def label(self) -> str:
        base = ("b/" if self.kind == "beatmap" else "s/") + str(self.id)
        return base + self.mods_text

    @property
    def mods_text(self) -> str:
        return "+" + "".join(self.mods) if self.mods else ""


@dataclass(frozen=True)
class BeatmapInfo:
    beatmap_id: int
    status: str
    artist: str
    title: str
    version: str
    bpm: float
    stars: float
    total_length: int
    beatmapset_id: int = 0
    artist_unicode: str = ""
    title_unicode: str = ""


def _text(value: object) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def _preferred_text(data: dict, primary_key: str, fallback_key: str) -> str:
    return _text(data.get(primary_key)) or _text(data.get(fallback_key))


def parse_beatmapset_html(html: str, beatmap_id: int | None = None) -> BeatmapInfo:
    match = _BEATMAPSET_JSON_PATTERN.search(html)
    if match is None:
        raise ValueError("osu! 页面中没有找到谱面数据")

    try:
        beatmapset = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("osu! 页面中的谱面数据格式错误") from exc

    maps = beatmapset.get("beatmaps") or []
    if beatmap_id is None:
        beatmap = max(
            maps,
            key=lambda item: float(item.get("difficulty_rating") or 0),
            default=None,
        )
    else:
        beatmap = next(
            (item for item in maps if int(item.get("id", 0)) == beatmap_id),
            None,
        )
    if beatmap is None:
        if beatmap_id is None:
            raise BeatmapNotFoundError("osu! 谱面集中没有可用难度")
        raise BeatmapNotFoundError(f"osu! 页面中没有 beatmap {beatmap_id}")

    selected_id = int(beatmap.get("id", 0))
    if selected_id <= 0:
        raise ValueError("osu! 谱面数据中缺少 beatmap ID")

    raw_status = _text(beatmap.get("status") or beatmapset.get("status")).lower()
    return BeatmapInfo(
        beatmap_id=selected_id,
        status=_STATUS_NAMES.get(raw_status, raw_status.title() or "Unknown"),
        artist=_preferred_text(beatmapset, "artist", "artist_unicode") or "Unknown Artist",
        title=_preferred_text(beatmapset, "title", "title_unicode") or "Unknown Title",
        version=_text(beatmap.get("version")) or "Unknown Difficulty",
        bpm=float(beatmap.get("bpm") or beatmapset.get("bpm") or 0),
        stars=float(beatmap.get("difficulty_rating") or 0),
        total_length=max(0, int(beatmap.get("total_length") or 0)),
        beatmapset_id=max(
            0,
            int(beatmapset.get("id") or beatmap.get("beatmapset_id") or 0),
        ),
        artist_unicode=_preferred_text(
            beatmapset,
            "artist_unicode",
            "artist",
        ) or "Unknown Artist",
        title_unicode=_preferred_text(
            beatmapset,
            "title_unicode",
            "title",
        ) or "Unknown Title",
    )


class BeatmapLookup:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        cache_seconds: float = 3600,
    ) -> None:
        self.session = session
        self.cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, BeatmapInfo]] = {}

    async def get(self, reference: BeatmapReference | int) -> BeatmapInfo:
        if isinstance(reference, int):
            reference = BeatmapReference("beatmap", reference)
        cached = self._cache.get(reference.key)
        now = time.monotonic()
        if cached is not None and now - cached[0] < self.cache_seconds:
            return cached[1]

        if reference.kind == "beatmap":
            url = f"https://osu.ppy.sh/b/{reference.id}"
        else:
            url = f"https://osu.ppy.sh/beatmapsets/{reference.id}"
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "osu-BiliRequest/1.0.0",
        }
        async with self.session.get(url, headers=headers, allow_redirects=True) as response:
            if response.status == 404:
                raise BeatmapNotFoundError(f"{reference.label} 不存在或不可访问")
            response.raise_for_status()
            html = await response.text()

        selected_id = reference.id if reference.kind == "beatmap" else None
        info = parse_beatmapset_html(html, selected_id)
        self._cache[reference.key] = (now, info)
        return info
