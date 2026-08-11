from __future__ import annotations

import time
from collections.abc import Callable


class RequestLimiter:
    def __init__(
        self,
        user_cooldown_seconds: float,
        map_dedupe_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_cooldown_seconds = max(0.0, user_cooldown_seconds)
        self.map_dedupe_seconds = max(0.0, map_dedupe_seconds)
        self._clock = clock
        self._last_user_request: dict[str, float] = {}
        self._last_map_request: dict[str | int, float] = {}

    def accept(self, user_key: str, map_key: str | int) -> tuple[bool, str]:
        now = self._clock()
        self._purge(now)

        last_user = self._last_user_request.get(user_key)
        if last_user is not None and now - last_user < self.user_cooldown_seconds:
            remaining = self.user_cooldown_seconds - (now - last_user)
            return False, f"用户冷却中（约 {remaining:.0f} 秒）"

        last_map = self._last_map_request.get(map_key)
        if last_map is not None and now - last_map < self.map_dedupe_seconds:
            remaining = self.map_dedupe_seconds - (now - last_map)
            return False, f"谱面去重中（约 {remaining:.0f} 秒）"

        self._last_user_request[user_key] = now
        self._last_map_request[map_key] = now
        return True, ""

    def _purge(self, now: float) -> None:
        user_cutoff = now - self.user_cooldown_seconds
        map_cutoff = now - self.map_dedupe_seconds
        self._last_user_request = {
            key: value
            for key, value in self._last_user_request.items()
            if value >= user_cutoff
        }
        self._last_map_request = {
            key: value
            for key, value in self._last_map_request.items()
            if value >= map_cutoff
        }
