"""Axis 응답 캐싱 — 2단(L1 메모리 + L2 Firestore) TTL 캐시.

동일 (model, system, messages) 쿼리에 대한 Claude API 응답을 캐싱하여
중복 호출 비용을 절감합니다.

신선도: 캐시 키가 messages(현재가·MA·"기준 시각" 등 시점 데이터 포함)를
해싱하므로, 데이터가 갱신되면 키가 바뀌어 자동으로 캐시 miss → 재분석됩니다.
즉 "동일 데이터 스냅샷"에서만 hit하므로 분석 신선도가 구조적으로 보장됩니다.

- L1: 프로세스 메모리 (빠름, 콜드스타트/재배포 시 소멸)
- L2: Firestore (영속, 콜드스타트 후에도 재사용). 장애 시 graceful — 캐시 없이 진행.

저장 형식은 JSON-safe dict여야 합니다(Firestore 직렬화). usage 등 객체는
호출부(claude_client)에서 dict로 변환해 넘깁니다 — 순환 import 방지.

사용:
    cache = default_cache
    key = cache.make_key(model, system, messages)
    cached = cache.get(key)          # L1 → L2 순
    if cached is None:
        result = await api_call(...)
        cache.set(key, result)       # L1 + L2
        cached = result
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class _Entry:
    value: Any
    expires_at: float


class ResponseCache:
    """2단 TTL 캐시. L1=메모리(프로세스), L2=Firestore(영속)."""

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_entries: int = 1024,
        firestore_ttl_seconds: int = 21600,  # 6h — 데이터 스냅샷 단위 키라 신선도 안전
        use_firestore: bool = True,
        collection: str = "ai_response_cache",
    ):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, _Entry] = {}
        self._lock = asyncio.Lock()
        self._fs_ttl = firestore_ttl_seconds
        self._use_fs = use_firestore
        self._collection = collection

    @staticmethod
    def make_key(
        model: str, system: str, messages: list[dict], extra: dict | None = None
    ) -> str:
        """캐시 키 생성. 동일 입력은 동일 SHA256 hex.

        extra: 호출 형태를 바꾸는 부가 파라미터(예: thinking_budget)를 키에 포함.
        thinking을 켠 응답이 끈 응답의 캐시에 히트해 A/B가 오염되는 것을 방지.
        """
        body: dict = {"model": model, "system": system, "messages": messages}
        if extra:
            body["extra"] = extra
        payload = json.dumps(body, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        # L1 메모리
        entry = self._store.get(key)
        if entry is not None:
            if entry.expires_at >= time.time():
                return entry.value
            self._store.pop(key, None)
        # L2 Firestore
        if self._use_fs:
            val = self._fs_get(key)
            if val is not None:
                # L1 승격 — 다음 조회는 메모리에서
                self._set_l1(key, val)
                return val
        return None

    def set(self, key: str, value: Any) -> None:
        self._set_l1(key, value)
        if self._use_fs:
            self._fs_set(key, value)

    def _set_l1(self, key: str, value: Any) -> None:
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

    # ── L2: Firestore (graceful — 장애가 분석을 막지 않음) ──

    def _fs_get(self, key: str) -> Any | None:
        try:
            from screener.db.firebase_client import get_db

            doc = get_db().collection(self._collection).document(key).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            if float(data.get("expires_at", 0)) < time.time():
                return None
            return data.get("value")
        except Exception as e:
            logger.debug(f"[cache] Firestore get 실패 (graceful): {e}")
            return None

    def _fs_set(self, key: str, value: Any) -> None:
        try:
            from screener.db.firebase_client import get_db

            get_db().collection(self._collection).document(key).set(
                {
                    "value": value,
                    "expires_at": time.time() + self._fs_ttl,
                    "created_at": time.time(),
                }
            )
        except Exception as e:
            logger.debug(f"[cache] Firestore set 실패 (graceful): {e}")


# 프로세스 단위 싱글톤 (utils.claude_client에서 import)
default_cache = ResponseCache(ttl_seconds=3600)
