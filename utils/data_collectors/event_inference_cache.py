"""LLM 유사 이벤트 추론 + 캐싱 모듈.

WEEK_C.md Day 4 산출물 (Event Analyst 페르소나용, 옵션 C Phase 1).

핵심 아이디어:
  자체 이벤트 통계 DB 구축은 5주 내 불가 → Claude API로 유사 사례 추정.

⚠️ LLM Fabrication 위험 — 다음 정책으로 대응:
  1. 응답에 "LLM 학습 데이터 기반 추정" 자동 첨부.
  2. 표본 수에 따라 신뢰도 단계 자동 표기:
     - sample_size < 5  → "통계 미제시 — 정성 분석만 사용"
     - 5 ≤ sample_size < 10 → "표본 부족 — 참고용"
     - sample_size ≥ 10 → "통계 신뢰 가능 (단, fabrication 경고 유지)"
  3. data_confidence 필드로 사례별 신뢰도 표시 (LLM이 직접 self-rate).
  4. 24시간 TTL 캐시 — 같은 이벤트는 자주 분석되지 않음.

LEGAL:
  - "추천", "사세요", "매수 신호" 등 단정 단어 절대 사용 금지.
  - 응답에 verification_needed 필드 강제 추가.
  - no_recommendation_disclaimer 자동 첨부.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger


CACHE_TTL_SEC = 86400  # 24시간
SAMPLE_SIZE_LOW = 5  # 미만이면 "통계 미제시"
SAMPLE_SIZE_OK = 10  # 이상이면 "통계 신뢰 가능"

# LEGAL: 단정 표현 차단 정책 (Validator-style)
FORBIDDEN_TERMS_KO = (
    "추천합니다",
    "추천드립니다",
    "사세요",
    "매수 신호",
    "매도 신호",
    "매수하세요",
    "매도하세요",
    "목표가",
    "손절가",
    "매수가",
)


SIMILAR_EVENT_PROMPT = """\
당신은 이벤트 트레이딩 분석가입니다.
다음 이벤트와 유사한 과거 사례를 학습 데이터에서 식별하고, 통계를 추정하세요.

**현재 이벤트**:
- 종류: {event_type}
- 대상: {event_target}
- 1차 수혜: {primary}
- 2차 수혜 분석 대상: {secondary_ticker}

**작업 규칙**:
1. 비슷한 카테고리의 과거 5~15개 사례를 학습 데이터에서 식별.
2. 각 사례의 D-30 ~ D-day 평균 수익률을 추정.
3. 표본 수가 5개 미만이면 "통계 미제시"로 응답.
4. 단정/추천 표현 금지. "관찰 구간", "참고 수치" 등 중립 표현만 사용.
5. 각 사례마다 data_confidence (high|medium|low) 자체 평가.

**출력 형식 (반드시 JSON only, 다른 설명 X)**:
{{
  "comparable_events": [
    {{
      "event": "Uber IPO 2019.05",
      "primary": "UBER",
      "secondary": "LYFT",
      "secondary_d_minus_60_to_d_day_return_pct": "+22%",
      "data_confidence": "high"
    }}
  ],
  "sample_size": 11,
  "qualitative_summary": "동종업계 IPO 시 비교 종목 멀티플 리레이팅 관찰 사례 다수.",
  "key_caveats": [
    "각 사례 외부 데이터로 재검증 권장",
    "표본 수가 적을수록 통계 신뢰도 감소"
  ]
}}
"""


# ──────────────────────────────────────────────
# 모듈 캐시
# ──────────────────────────────────────────────


@dataclass
class _Entry:
    value: dict[str, Any]
    expires_at: float


_cache: dict[str, _Entry] = {}


def _cache_key(event_type: str, event_target: str, primary: str, secondary_ticker: str) -> str:
    """이벤트 4-tuple → SHA256 (대소문자 무시, 공백 제거)."""
    payload = "|".join(
        s.strip().upper() for s in (event_type, event_target, primary, secondary_ticker)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    e = _cache.get(key)
    if e is None:
        return None
    if e.expires_at < time.time():
        _cache.pop(key, None)
        return None
    return e.value


def _cache_set(key: str, value: dict[str, Any]) -> None:
    _cache[key] = _Entry(value=value, expires_at=time.time() + CACHE_TTL_SEC)


def clear_cache() -> None:
    _cache.clear()


# ──────────────────────────────────────────────
# 응답 파싱 + 사후 안전망
# ──────────────────────────────────────────────


def _classify_sample_reliability(sample_size: int) -> str:
    if sample_size < SAMPLE_SIZE_LOW:
        return "통계 미제시 — 정성 분석만 사용"
    if sample_size < SAMPLE_SIZE_OK:
        return "표본 부족 — 참고용"
    return "통계 신뢰 가능 (단, LLM 추정 한계 유지)"


def _strip_to_json(text: str) -> str:
    """LLM 응답에서 JSON 블록만 추출.

    ```json ... ``` 또는 ``` ... ``` 코드펜스를 제거하고, 첫 { ~ 마지막 } 구간 추출.
    """
    if not text:
        return "{}"
    s = text.strip()
    # 코드펜스 제거
    fence = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
    s = fence.sub("", s).strip()
    # 첫 { ~ 마지막 }
    first = s.find("{")
    last = s.rfind("}")
    if first == -1 or last == -1 or last < first:
        return "{}"
    return s[first : last + 1]


def _scrub_forbidden(text: str) -> tuple[str, list[str]]:
    """LLM 응답에서 단정 표현 발견 시 마스킹 + 발견 목록 반환."""
    found: list[str] = []
    out = text
    for term in FORBIDDEN_TERMS_KO:
        if term in out:
            found.append(term)
            out = out.replace(term, "[중립표현 필요]")
    return out, found


def _attach_safety(parsed: dict[str, Any]) -> dict[str, Any]:
    """LEGAL/Fabrication 안전망 자동 첨부."""
    sample_size = int(parsed.get("sample_size") or 0)
    parsed.setdefault("comparable_events", [])
    parsed["sample_size"] = sample_size
    parsed["sample_reliability"] = _classify_sample_reliability(sample_size)
    parsed["fabrication_warning"] = (
        "위 사례/통계는 LLM 학습 데이터 기반 추정값이며, 실제 수치와 차이가 있을 수 있습니다. "
        "사례별 외부 데이터 재검증 후 활용 권장."
    )
    parsed.setdefault(
        "verification_needed",
        [
            "각 사례의 실제 수익률 외부 데이터 검증 권장",
            "표본 수가 적을수록 통계 신뢰도 낮음",
            "LLM이 사례를 fabricate(가짜로 만들)할 가능성 존재",
        ],
    )
    parsed["no_recommendation_disclaimer"] = (
        "본 분석은 정보 제공이며 매수/매도 추천이 아닙니다. "
        "최종 판단은 사용자 본인의 책임입니다."
    )

    # 표본 미달 시 통계 강제 비표시
    if sample_size < SAMPLE_SIZE_LOW:
        parsed["statistical_summary_suppressed"] = True
    return parsed


def _post_process(raw_text: str) -> dict[str, Any]:
    """LLM 응답 raw → 안전망 적용된 dict."""
    cleaned, forbidden_found = _scrub_forbidden(raw_text)
    json_text = _strip_to_json(cleaned)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.warning(f"event_inference JSON 파싱 실패: {e}")
        parsed = {
            "comparable_events": [],
            "sample_size": 0,
            "qualitative_summary": "",
            "parse_error": True,
        }

    parsed = _attach_safety(parsed)
    if forbidden_found:
        parsed["forbidden_terms_scrubbed"] = forbidden_found
    return parsed


# ──────────────────────────────────────────────
# 공개 함수
# ──────────────────────────────────────────────


async def get_similar_events_cached(
    event_type: str,
    event_target: str,
    primary: str,
    secondary_ticker: str,
    *,
    claude_client: Any | None = None,
    skip_cache: bool = False,
) -> dict[str, Any]:
    """유사 이벤트 추론 (24h 캐시).

    Args:
        event_type: 예: "IPO", "FOMC", "M&A".
        event_target: 예: "SpaceX IPO 2026 Q4".
        primary: 1차 수혜 티커.
        secondary_ticker: 분석 대상 2차 수혜 티커.
        claude_client: utils.claude_client.ClaudeClient 인스턴스 (None 시 lazy init).
        skip_cache: True면 캐시 무시.

    Returns:
        안전망 적용된 dict — comparable_events, sample_size, sample_reliability,
        fabrication_warning, verification_needed, no_recommendation_disclaimer 포함.
    """
    key = _cache_key(event_type, event_target, primary, secondary_ticker)
    if not skip_cache:
        cached = _cache_get(key)
        if cached is not None:
            return {**cached, "from_cache": True}

    # Claude client 준비
    if claude_client is None:
        from utils.claude_client import ClaudeClient

        claude_client = ClaudeClient()

    prompt = SIMILAR_EVENT_PROMPT.format(
        event_type=event_type,
        event_target=event_target,
        primary=primary,
        secondary_ticker=secondary_ticker,
    )

    try:
        from utils.claude_client import MODEL_HAIKU

        result = await claude_client.complete(
            agent="event_inference",
            model=MODEL_HAIKU,
            system="당신은 이벤트 트레이딩 분석가입니다. JSON only로 응답하세요.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
    except Exception as e:
        logger.warning(
            f"event_inference Claude 호출 실패: {type(e).__name__}: {str(e)[:160]}"
        )
        # 호출 실패 — 안전망만 적용한 최소 응답
        fallback = _attach_safety(
            {
                "comparable_events": [],
                "sample_size": 0,
                "qualitative_summary": "",
                "api_error": f"{type(e).__name__}",
            }
        )
        return fallback

    raw = (result or {}).get("content", "") or ""
    parsed = _post_process(raw)
    parsed["model"] = MODEL_HAIKU
    parsed["from_cache"] = False

    _cache_set(key, parsed)
    return parsed


# 동기 호환 래퍼 (Job/CLI 환경에서 비동기 컨텍스트 없을 때)
def get_similar_events_sync(
    event_type: str,
    event_target: str,
    primary: str,
    secondary_ticker: str,
    *,
    claude_client: Any | None = None,
    skip_cache: bool = False,
) -> dict[str, Any]:
    return asyncio.run(
        get_similar_events_cached(
            event_type,
            event_target,
            primary,
            secondary_ticker,
            claude_client=claude_client,
            skip_cache=skip_cache,
        )
    )
