from __future__ import annotations

import re
from urllib.parse import urlsplit

from .beatmap import BeatmapInfo, BeatmapReference


_REQUEST_PATTERN = re.compile(
    r"^\s*(?:([bBsS])\s*/?\s*)?([0-9]{1,10})(.*?)\s*$"
)

_VALID_MODS = {
    "NF", "EZ", "TD", "HD", "HR", "SD", "DT", "RX", "HT",
    "NC", "FL", "AT", "SO", "AP", "PF",
}


def _parse_mods(raw: str) -> tuple[str, ...] | None:
    if not raw.strip():
        return ()
    if re.fullmatch(r"[A-Za-z+\s]+", raw) is None:
        return None
    compact = re.sub(r"[+\s]", "", raw).upper()
    if not compact or len(compact) % 2 != 0:
        return None
    mods = [compact[index:index + 2] for index in range(0, len(compact), 2)]
    if any(mod not in _VALID_MODS for mod in mods):
        return None

    unique = list(dict.fromkeys(mods))
    if "NC" in unique and "DT" in unique:
        unique.remove("DT")
    if "PF" in unique and "SD" in unique:
        unique.remove("SD")
    if ({"DT", "NC"} & set(unique)) and "HT" in unique:
        return None
    if "EZ" in unique and "HR" in unique:
        return None
    return tuple(unique)


def _remove_request_keyword(message: str, keywords: tuple[str, ...]) -> str:
    cleaned = message.strip()
    normalized = sorted(
        {str(keyword).strip() for keyword in keywords if str(keyword).strip()},
        key=len,
        reverse=True,
    )
    for keyword in normalized:
        match = re.match(
            rf"^{re.escape(keyword)}\s*[:：]?\s*",
            cleaned,
            flags=re.IGNORECASE,
        )
        if match is not None:
            return cleaned[match.end():]
    return cleaned


def parse_beatmap_reference(
    message: str,
    keywords: tuple[str, ...] = ("点歌",),
) -> BeatmapReference | None:
    """Parse b/ difficulty IDs, s/ set IDs, or a plain difficulty ID."""
    if not isinstance(message, str):
        return None

    match = _REQUEST_PATTERN.fullmatch(_remove_request_keyword(message, keywords))
    if match is None:
        return None

    source_id = int(match.group(2))
    if source_id <= 0:
        return None
    kind = "set" if (match.group(1) or "b").lower() == "s" else "beatmap"
    mods = _parse_mods(match.group(3))
    if mods is None:
        return None
    return BeatmapReference(kind, source_id, mods)


def parse_osu_beatmap_url(
    message: str,
    keywords: tuple[str, ...] = ("点歌",),
) -> BeatmapReference | None:
    """Parse one official osu! beatmap URL, optionally followed by Mods."""
    if not isinstance(message, str):
        return None
    cleaned = _remove_request_keyword(message, keywords)
    parts = cleaned.split(maxsplit=1)
    if not parts:
        return None
    try:
        parsed = urlsplit(parts[0])
    except ValueError:
        return None
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or (parsed.hostname or "").lower() not in {"osu.ppy.sh", "www.osu.ppy.sh"}
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None

    segments = [segment for segment in parsed.path.split("/") if segment]
    kind = ""
    source_id = 0
    if len(segments) == 2 and segments[0].lower() in {"b", "beatmaps"}:
        kind, raw_id = "beatmap", segments[1]
    elif len(segments) == 2 and segments[0].lower() == "s":
        kind, raw_id = "set", segments[1]
    elif len(segments) == 2 and segments[0].lower() == "beatmapsets":
        fragment = re.fullmatch(r"[A-Za-z0-9_-]+/([0-9]{1,10})", parsed.fragment)
        if fragment is not None:
            kind, raw_id = "beatmap", fragment.group(1)
        else:
            kind, raw_id = "set", segments[1]
    else:
        return None
    if not raw_id.isdigit():
        return None
    source_id = int(raw_id)
    if source_id <= 0:
        return None
    mods = _parse_mods(parts[1] if len(parts) == 2 else "")
    if mods is None:
        return None
    return BeatmapReference(kind, source_id, mods)


def parse_beatmap_id(message: str) -> int | None:
    """Backward-compatible helper. Plain numbers are beatmap difficulty IDs."""
    reference = parse_beatmap_reference(message)
    if reference is None or reference.kind != "beatmap":
        return None
    return reference.id


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def sanitize_display_name(name: str, max_bytes: int = 48) -> str:
    """Keep a Bilibili display name on one IRC-safe line."""
    cleaned = " ".join(str(name or "观众").replace("\x00", "").split())
    return _truncate_utf8(cleaned or "观众", max_bytes)


def _format_number(value: float) -> str:
    return f"{value:g}"


def format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_irc_request(
    reference: BeatmapReference | int,
    requester_name: str,
    info: BeatmapInfo | None = None,
    modded_stars: float | None = None,
    use_unicode_metadata: bool = False,
) -> str:
    if isinstance(reference, int):
        reference = BeatmapReference("beatmap", reference)
    requester = sanitize_display_name(requester_name)
    if info is not None:
        artist_source = info.artist_unicode if use_unicode_metadata else info.artist
        title_source = info.title_unicode if use_unicode_metadata else info.title
        artist = _truncate_utf8(artist_source or info.artist, 48)
        title = _truncate_utf8(title_source or info.title, 72)
        version = _truncate_utf8(info.version, 48)
        label = f"{artist} - {title} [{version}]"
        rate = 1.5 if ({"DT", "NC"} & set(reference.mods)) else 0.75 if "HT" in reference.mods else 1.0
        bpm = info.bpm * rate
        length = round(info.total_length / rate)
        if reference.mods and modded_stars is not None:
            stars = f"{modded_stars:.2f}*"
        elif reference.mods:
            stars = f"base {info.stars:.2f}*"
        else:
            stars = f"{info.stars:.2f}*"
        details = (
            f"{_format_number(bpm)} BPM, "
            f"{stars}, "
            f"{format_duration(length)}"
        )
        mirrors = ""
        if info.beatmapset_id > 0:
            mirrors = (
                " Sayobot:"
                f"[https://dl.sayobot.cn/beatmaps/download/full/{info.beatmapset_id} Full]"
                f"~[https://dl.sayobot.cn/beatmaps/download/novideo/{info.beatmapset_id} NoVideo]"
            )
        return (
            f"[{requester}] -> [{info.status}] "
            f"[https://osu.ppy.sh/b/{info.beatmap_id} {label}]"
            f" ({details})"
            f"{(' ' + reference.mods_text) if reference.mods else ''}"
            f"{mirrors}"
        )
    if reference.kind == "set":
        return (
            f"[https://osu.ppy.sh/beatmapsets/{reference.id} beatmapset {reference.id}] "
            f"<- osu-BiliRequest: {requester}{(' ' + reference.mods_text) if reference.mods else ''}"
        )
    return (
        f"[https://osu.ppy.sh/b/{reference.id} beatmap {reference.id}] "
        f"<- osu-BiliRequest: {requester}{(' ' + reference.mods_text) if reference.mods else ''}"
    )
