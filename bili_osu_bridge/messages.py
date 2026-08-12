from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestMessage:
    """A platform-neutral incoming chat message."""

    source: str
    user_id: str
    username: str
    content: str
    avatar_url: str = ""
    scope_id: str = ""
    is_private: bool = False
    reply: Callable[[str], Awaitable[None]] | None = None

    @property
    def user_key(self) -> str:
        identity = self.user_id or self.username or "anonymous"
        return f"{self.source}:{identity}"
