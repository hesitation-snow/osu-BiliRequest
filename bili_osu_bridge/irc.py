from __future__ import annotations

import asyncio
import base64
import logging
import time
from urllib.parse import unquote, urlsplit


logger = logging.getLogger(__name__)


def _irc_name(value: str) -> str:
    return "_".join(value.strip().split())


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


class BanchoIrcClient:
    def __init__(
        self,
        username: str,
        irc_password: str,
        target_username: str,
        *,
        host: str = "irc.ppy.sh",
        port: int = 6667,
        send_interval_seconds: float = 1.0,
        proxy_url: str = "",
    ) -> None:
        self.username = _irc_name(username)
        self.irc_password = irc_password
        self.target_username = _irc_name(target_username)
        self.host = host
        self.port = port
        self.send_interval_seconds = send_interval_seconds
        self.proxy_url = proxy_url

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._connect_error: Exception | None = None
        self._send_lock = asyncio.Lock()
        self._last_send_at = 0.0

    async def connect(self) -> None:
        if self._writer is not None and not self._writer.is_closing() and self._ready.is_set():
            return

        await self.close()
        self._ready = asyncio.Event()
        self._connect_error = None
        logger.info("正在连接 osu! IRC：%s:%d", self.host, self.port)
        self._reader, self._writer = await asyncio.wait_for(
            self._open_connection(), timeout=15
        )
        self._reader_task = asyncio.create_task(self._read_loop())

        await self._write_raw(f"PASS {self.irc_password}", sensitive=True)
        await self._write_raw(f"NICK {self.username}")
        await self._write_raw(f"USER {self.username} 0 * :{self.username}")

        await asyncio.wait_for(self._ready.wait(), timeout=15)
        if self._connect_error is not None:
            error = self._connect_error
            await self.close()
            raise error
        logger.info("osu! IRC 已登录")

    async def _open_connection(
        self,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if not self.proxy_url:
            return await asyncio.open_connection(self.host, self.port)

        proxy = urlsplit(self.proxy_url)
        proxy_port = proxy.port or (443 if proxy.scheme.lower() == "https" else 80)
        reader, writer = await asyncio.open_connection(
            proxy.hostname,
            proxy_port,
            ssl=proxy.scheme.lower() == "https",
            server_hostname=proxy.hostname if proxy.scheme.lower() == "https" else None,
        )
        target = f"{self.host}:{self.port}"
        headers = [
            f"CONNECT {target} HTTP/1.1",
            f"Host: {target}",
            "Proxy-Connection: Keep-Alive",
        ]
        if proxy.username is not None:
            credentials = f"{unquote(proxy.username)}:{unquote(proxy.password or '')}"
            token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
            headers.append(f"Proxy-Authorization: Basic {token}")
        writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
        await writer.drain()

        status_line = (await reader.readline()).decode("iso-8859-1").strip()
        parts = status_line.split(" ", 2)
        if len(parts) < 2 or parts[1] != "200":
            writer.close()
            await writer.wait_closed()
            raise ConnectionError(f"IRC 代理连接失败：{status_line or '无响应'}")
        while True:
            line = await reader.readline()
            if line in {b"\r\n", b"\n", b""}:
                break
        logger.info("Bancho IRC 已通过代理建立隧道")
        return reader, writer

    async def send_privmsg(self, message: str) -> None:
        clean_message = " ".join(message.replace("\x00", "").splitlines()).strip()
        if not clean_message:
            return

        prefix = f"PRIVMSG {self.target_username} :"
        max_message_bytes = 510 - len(prefix.encode("utf-8"))
        clean_message = _truncate_utf8(clean_message, max_message_bytes)

        async with self._send_lock:
            for attempt in range(2):
                try:
                    await self.connect()
                    elapsed = time.monotonic() - self._last_send_at
                    if elapsed < self.send_interval_seconds:
                        await asyncio.sleep(self.send_interval_seconds - elapsed)
                    await self._write_raw(prefix + clean_message)
                    self._last_send_at = time.monotonic()
                    return
                except (ConnectionError, OSError, asyncio.TimeoutError):
                    if attempt == 1:
                        raise
                    logger.warning("IRC 发送失败，正在重连", exc_info=True)
                    await self.close()

    async def close(self) -> None:
        current_task = asyncio.current_task()
        if self._reader_task is not None and self._reader_task is not current_task:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
        self._reader_task = None

        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError):
                pass
        self._reader = None
        self._writer = None
        self._ready.clear()

    async def _write_raw(self, line: str, *, sensitive: bool = False) -> None:
        if self._writer is None or self._writer.is_closing():
            raise ConnectionError("IRC 未连接")
        if not sensitive:
            logger.debug("IRC > %s", line)
        self._writer.write((line + "\r\n").encode("utf-8"))
        await self._writer.drain()

    async def _read_loop(self) -> None:
        assert self._reader is not None
        try:
            while True:
                raw_line = await self._reader.readline()
                if not raw_line:
                    raise ConnectionError("IRC 连接已关闭")
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                logger.debug("IRC < %s", line)

                if line.startswith("PING "):
                    await self._write_raw("PONG " + line[5:])
                    continue

                parts = line.split()
                if len(parts) >= 2 and parts[1] == "001":
                    self._ready.set()
                elif line.startswith("ERROR ") or (
                    len(parts) >= 2 and parts[1] in {"433", "464", "465"}
                ):
                    raise ConnectionError("Bancho IRC 登录失败：" + line)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._connect_error = exc
            self._ready.set()
            logger.warning("IRC 连接中断：%s", exc)
        finally:
            if self._writer is not None:
                self._writer.close()
