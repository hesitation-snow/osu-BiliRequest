from __future__ import annotations

import re
import string
from urllib.parse import urlsplit

from .beatmap import BeatmapInfo, BeatmapReference


_REQUEST_PATTERN = re.compile(
    r"^\s*(?:([bBsS])\s*/?\s*)?([0-9]{1,10})(.*?)\s*$"
)

_VALID_MODS = {
    "NF", "EZ", "TD", "HD", "HR", "SD", "DT", "RX", "HT",
    "NC", "FL", "AT", "SO", "AP", "PF",
}

DEFAULT_IRC_MESSAGE_TEMPLATE = (
    "[{requester}] -> [{status}] {beatmap_link} "
    "({bpm} BPM, {stars}, {duration}){mods_suffix} {sayobot}"
)
DEFAULT_IRC_FALLBACK_TEMPLATE = (
    "{reference_link} <- osu-BiliRequest: {requester}{mods_suffix}"
)
IRC_TEMPLATE_FIELDS = frozenset(
    {
        "requester",
        "platform",
        "status",
        "artist",
        "title",
        "difficulty",
        "map_label",
        "details",
        "bpm",
        "stars",
        "duration",
        "mods",
        "mods_suffix",
        "beatmap_id",
        "beatmapset_id",
        "beatmap_url",
        "beatmap_link",
        "reference",
        "reference_url",
        "reference_link",
        "full_url",
        "novideo_url",
        "sayobot",
    }
)


def validate_irc_template(value: str, key: str = "osuIrc.messageTemplate") -> None:
    if not value.strip():
        raise ValueError(f"{key} 不能为空")
    if len(value) > 2000:
        raise ValueError(f"{key} 不能超过 2000 个字符")
    try:
        fields = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(value)
            if field_name is not None
        }
    except ValueError as exc:
        raise ValueError(f"{key} 的大括号格式不正确") from exc
    invalid = sorted(field for field in fields if field not in IRC_TEMPLATE_FIELDS)
    if invalid:
        raise ValueError(f"{key} 包含未知占位符：" + ", ".join(invalid))


def _render_irc_template(template: str, values: dict[str, object]) -> str:
    rendered = template.format_map(values)
    return " ".join(rendered.replace("\x00", "").split())


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
    message_template: str = DEFAULT_IRC_MESSAGE_TEMPLATE,
    fallback_template: str = DEFAULT_IRC_FALLBACK_TEMPLATE,
    platform: str = "",
) -> str:
    if isinstance(reference, int):
        reference = BeatmapReference("beatmap", reference)
    requester = sanitize_display_name(requester_name)
    mods = reference.mods_text if reference.mods else ""
    mods_suffix = f" {mods}" if mods else ""
    reference_url = (
        f"https://osu.ppy.sh/beatmapsets/{reference.id}"
        if reference.kind == "set"
        else f"https://osu.ppy.sh/b/{reference.id}"
    )
    reference_label = (
        f"beatmapset {reference.id}"
        if reference.kind == "set"
        else f"beatmap {reference.id}"
    )
    common_values: dict[str, object] = {
        "requester": requester,
        "platform": sanitize_display_name(platform, 16) if platform else "",
        "status": "",
        "artist": "",
        "title": "",
        "difficulty": "",
        "map_label": "",
        "details": "",
        "bpm": "",
        "stars": "",
        "duration": "",
        "mods": mods,
        "mods_suffix": mods_suffix,
        "beatmap_id": reference.id if reference.kind == "beatmap" else "",
        "beatmapset_id": reference.id if reference.kind == "set" else "",
        "beatmap_url": reference_url,
        "beatmap_link": f"[{reference_url} {reference_label}]",
        "reference": reference.label,
        "reference_url": reference_url,
        "reference_link": f"[{reference_url} {reference_label}]",
        "full_url": "",
        "novideo_url": "",
        "sayobot": "",
    }
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
        full_url = ""
        novideo_url = ""
        sayobot = ""
        if info.beatmapset_id > 0:
            full_url = (
                "https://dl.sayobot.cn/beatmaps/download/full/"
                f"{info.beatmapset_id}"
            )
            novideo_url = (
                "https://dl.sayobot.cn/beatmaps/download/novideo/"
                f"{info.beatmapset_id}"
            )
            sayobot = (
                "Sayobot:"
                f"[{full_url} Full]"
                f"~[https://dl.sayobot.cn/beatmaps/download/novideo/{info.beatmapset_id} NoVideo]"
            )
        beatmap_url = f"https://osu.ppy.sh/b/{info.beatmap_id}"
        values = {
            **common_values,
            "status": info.status,
            "artist": artist,
            "title": title,
            "difficulty": version,
            "map_label": label,
            "details": (
                f"{_format_number(bpm)} BPM, {stars}, "
                f"{format_duration(length)}"
            ),
            "bpm": _format_number(bpm),
            "stars": stars,
            "duration": format_duration(length),
            "beatmap_id": info.beatmap_id,
            "beatmapset_id": info.beatmapset_id or "",
            "beatmap_url": beatmap_url,
            "beatmap_link": f"[{beatmap_url} {label}]",
            "full_url": full_url,
            "novideo_url": novideo_url,
            "sayobot": sayobot,
        }
        return _render_irc_template(message_template, values)
    return _render_irc_template(fallback_template, common_values)
