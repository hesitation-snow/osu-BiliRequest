import asyncio
import os
import unittest

import aiohttp

from bili_osu_bridge.network import apply_http_proxy


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_aiohttp_uses_configured_http_proxy(self):
        requests = []

        async def handle(reader, writer):
            try:
                requests.append((await reader.readline()).decode().strip())
                while (await reader.readline()) not in {b"\r\n", b"\n", b""}:
                    pass
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        old_values = {key: os.environ.get(key) for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")}
        try:
            apply_http_proxy(f"http://127.0.0.1:{port}")
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get("http://not-real.invalid/test") as response:
                    self.assertEqual(await response.text(), "OK")
        finally:
            server.close()
            await server.wait_closed()
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(requests[0], "GET http://not-real.invalid/test HTTP/1.1")


if __name__ == "__main__":
    unittest.main()
