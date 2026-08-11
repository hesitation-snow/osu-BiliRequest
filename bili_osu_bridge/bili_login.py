from __future__ import annotations

import asyncio
import base64
import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import qrcode

from .network import apply_http_proxy


_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
_USER_URL = "https://api.bilibili.com/x/web-interface/nav"
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bilibili.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/136 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class BilibiliLoginResult:
    sessdata: str
    username: str


@dataclass(frozen=True)
class BilibiliQrTicket:
    key: str
    image_data_url: str


@dataclass(frozen=True)
class BilibiliQrPollResult:
    status: str
    message: str
    sessdata: str = ""
    username: str = ""


async def _get_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, str] | None = None,
    proxy: str | None = None,
) -> tuple[dict, dict[str, str]]:
    async with session.get(
        url,
        params=params,
        headers=_HEADERS,
        proxy=proxy,
    ) as response:
        response.raise_for_status()
        data = await response.json(content_type=None)
        cookies = {name: morsel.value for name, morsel in response.cookies.items()}
    if data.get("code") != 0:
        raise RuntimeError(data.get("message") or data.get("msg") or "bilibili接口返回错误")
    return data, cookies


async def generate_qr_ticket(proxy_url: str = "") -> BilibiliQrTicket:
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        generated, _ = await _get_json(
            session,
            _GENERATE_URL,
            proxy=proxy_url or None,
        )
    payload = generated.get("data") or {}
    qr_url = str(payload.get("url") or "")
    qr_key = str(payload.get("qrcode_key") or "")
    if not qr_url or not qr_key:
        raise RuntimeError("bilibili没有返回登录二维码")
    buffer = io.BytesIO()
    qrcode.make(qr_url).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return BilibiliQrTicket(qr_key, f"data:image/png;base64,{encoded}")


async def poll_qr_ticket(
    qr_key: str,
    proxy_url: str = "",
) -> BilibiliQrPollResult:
    if not qr_key or len(qr_key) > 256:
        raise ValueError("二维码登录 Key 无效")
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        result, response_cookies = await _get_json(
            session,
            _POLL_URL,
            params={"qrcode_key": qr_key},
            proxy=proxy_url or None,
        )
        data = result.get("data") or {}
        code = int(data.get("code", -1))
        if code == 0:
            sessdata = response_cookies.get("SESSDATA", "")
            if not sessdata:
                raise RuntimeError("登录成功，但响应中没有 SESSDATA")
            username = await _fetch_username(
                session,
                sessdata,
                proxy_url=proxy_url,
            )
            return BilibiliQrPollResult(
                "success",
                "登录成功",
                sessdata,
                username,
            )
        if code == 86101:
            return BilibiliQrPollResult("waiting", "等待扫码")
        if code == 86090:
            return BilibiliQrPollResult("confirm", "已扫码，请在手机上确认")
        if code == 86038:
            return BilibiliQrPollResult("expired", "二维码已过期")
        message = str(data.get("message") or "二维码登录失败")
        return BilibiliQrPollResult("error", f"{message}（{code}）")


def _open_qr_image(url: str) -> Path:
    path = Path(tempfile.gettempdir()) / "bili-osu-login-qr.png"
    image = qrcode.make(url)
    image.save(path)
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        print(f"无法自动打开二维码图片，请手动打开：{path}")
    return path


async def login_with_qr(
    proxy_url: str = "",
    *,
    timeout_seconds: float = 180,
) -> BilibiliLoginResult:
    apply_http_proxy(proxy_url)
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(
        timeout=timeout,
        trust_env=bool(proxy_url),
    ) as session:
        generated, _ = await _get_json(session, _GENERATE_URL)
        payload = generated.get("data") or {}
        qr_url = str(payload.get("url") or "")
        qr_key = str(payload.get("qrcode_key") or "")
        if not qr_url or not qr_key:
            raise RuntimeError("bilibili没有返回登录二维码")

        qr_path = _open_qr_image(qr_url)
        print("二维码已打开，请使用哔哩哔哩手机客户端扫码并确认登录。")

        deadline = asyncio.get_running_loop().time() + timeout_seconds
        last_code: int | None = None
        try:
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(2)
                result, response_cookies = await _get_json(
                    session,
                    _POLL_URL,
                    params={"qrcode_key": qr_key},
                )
                data = result.get("data") or {}
                code = int(data.get("code", -1))
                if code == 0:
                    sessdata = response_cookies.get("SESSDATA", "")
                    if not sessdata:
                        raise RuntimeError("登录成功，但响应中没有 SESSDATA")
                    username = await _fetch_username(session, sessdata)
                    return BilibiliLoginResult(sessdata, username)
                if code == 86038:
                    raise RuntimeError("二维码已过期，请重新运行配置")
                if code == 86090 and code != last_code:
                    print("已扫码，请在手机上确认登录……")
                elif code not in {86101, 86090}:
                    message = str(data.get("message") or "未知状态")
                    raise RuntimeError(f"二维码登录失败：{message}（{code}）")
                last_code = code
        finally:
            try:
                qr_path.unlink(missing_ok=True)
            except OSError:
                pass

    raise TimeoutError("等待扫码超时，请重新运行配置")


async def _fetch_username(
    session: aiohttp.ClientSession,
    sessdata: str,
    *,
    proxy_url: str = "",
) -> str:
    try:
        async with session.get(
            _USER_URL,
            headers=_HEADERS,
            cookies={"SESSDATA": sessdata},
            proxy=proxy_url or None,
        ) as response:
            payload = await response.json(content_type=None)
        if payload.get("code") == 0:
            return str((payload.get("data") or {}).get("uname") or "")
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        pass
    return ""


def run_qr_login(proxy_url: str = "") -> BilibiliLoginResult:
    return asyncio.run(login_with_qr(proxy_url))
