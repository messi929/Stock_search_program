"""Axis 응답 캐싱 — 메모리 기반 TTL 캐시.

동일 (model, system, messages) 쿼리에 대한 Claude API 응답을 1시간 캐싱하여
중복 호출 비용을 절감합니다. Week 3에서 Firestore-backed로 업그레이드 예정.

사용:
    cache = ResponseCache(ttl_seconds=3600)
    key = cache.make_key(model, system, messages)
    cached = cache.get(key)
    if cached is None:
        result = await api_call(...)
        cache.set(key, result)
        cached = result
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    value: Any
    expires_at: float


class ResponseCache:
    """간단한 메모리 TTL 캐시. 프로세스 단위로만 공유됨."""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 1024):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, _Entry] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def make_key(model: str, system: str, messages: list[dict]) -> str:
        """캐시 키 생성. 동일 입력은 동일 SHA256 hex."""
        payload = json.dumps(
            {"model": model, "system": system, "messages": messages},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._max:
            self._evict_oldest()
        self._store[key] = _Entry(value=value, expires_at=time.time() + self._ttl)

    def _evict_oldest(self) -> None:
        if not self._store:
            return
        oldest = min(self._store.items(), key=lambda kv: kv[1].expires_at)
        self._store.pop(oldest[0], None)

    def clear(self) -> None:
        self._store.clear()


# 프로세스 단위 싱글톤 (utils.claude_client에서 import)
default_cache = ResponseCache(ttl_seconds=3600)
