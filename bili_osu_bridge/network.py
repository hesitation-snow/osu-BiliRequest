from __future__ import annotations

import os


def apply_http_proxy(proxy_url: str) -> None:
    """Apply one HTTP CONNECT proxy to aiohttp HTTP and WebSocket requests."""
    if not proxy_url:
        return
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["ALL_PROXY"] = proxy_url
