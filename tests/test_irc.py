import asyncio
import unittest

from bili_osu_bridge.irc import BanchoIrcClient


class IrcTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_ping_and_privmsg(self):
        received = []

        async def handle(reader, writer):
            try:
                for _ in range(3):
                    received.append((await reader.readline()).decode().strip())
                writer.write(b":cho.ppy.sh 001 sender :Welcome\r\n")
                writer.write(b"PING :test-token\r\n")
                await writer.drain()
                received.append((await reader.readline()).decode().strip())
                received.append((await reader.readline()).decode().strip())
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = BanchoIrcClient(
            "sender name",
            "secret",
            "target name",
            host="127.0.0.1",
            port=port,
            send_interval_seconds=0,
        )
        try:
            await client.send_privmsg("hello")
            await asyncio.sleep(0.05)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

        self.assertEqual(received[0], "PASS secret")
        self.assertEqual(received[1], "NICK sender_name")
        self.assertEqual(received[2], "USER sender_name 0 * :sender_name")
        self.assertIn("PONG :test-token", received)
        self.assertIn("PRIVMSG target_name :hello", received)

    async def test_http_connect_proxy(self):
        received = []

        async def handle_proxy(reader, writer):
            try:
                received.append((await reader.readline()).decode().strip())
                while (await reader.readline()) not in {b"\r\n", b"\n", b""}:
                    pass
                writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                await writer.drain()
                for _ in range(3):
                    received.append((await reader.readline()).decode().strip())
                writer.write(b":cho.ppy.sh 001 sender :Welcome\r\n")
                await writer.drain()
                received.append((await reader.readline()).decode().strip())
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle_proxy, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = BanchoIrcClient(
            "sender",
            "secret",
            "target",
            host="irc.ppy.sh",
            port=6667,
            proxy_url=f"http://127.0.0.1:{port}",
            send_interval_seconds=0,
        )
        try:
            await client.send_privmsg("via proxy")
            await asyncio.sleep(0.05)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

        self.assertEqual(received[0], "CONNECT irc.ppy.sh:6667 HTTP/1.1")
        self.assertIn("PRIVMSG target :via proxy", received)


if __name__ == "__main__":
    unittest.main()
