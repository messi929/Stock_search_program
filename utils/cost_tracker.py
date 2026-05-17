"""Axis Claude API 비용 추적.

토큰 사용량을 기반으로 USD/KRW 비용을 계산하고,
사용자별 일별 누적량을 Firestore `users/{uid}/ai_usage/{YYYY-MM-DD}`에 기록합니다.

가격(2026-04 기준, $/MTok):
  Haiku  4.5 — input $1.00 / output $5.00
  Sonnet 4.6 — input $3.00 / output $15.00
  Opus   4.7 — input $15.00 / output $75.00

캐시 가격 (Anthropic 표준):
  cache_read    = input * 0.1   (10%)
  cache_creation = input * 1.25  (25% 추가)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger

from utils.claude_client import MODEL_HAIKU, MODEL_OPUS, MODEL_SONNET

if TYPE_CHECKING:
    from utils.claude_client import ClaudeUsage


# ──────────────────────────────────────────────
# 가격표 ($/MTok = $/1,000,000 tokens)
# ──────────────────────────────────────────────

_PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    MODEL_HAIKU: {"input": 1.00, "output": 5.00},
    MODEL_SONNET: {"input": 3.00, "output": 15.00},
    MODEL_OPUS: {"input": 15.00, "output": 75.00},
}

# 환율 (수동 갱신). Week 3에 fxrate 자동 업데이트 가능.
USD_TO_KRW = 1400.0


@dataclass
class CostBreakdown:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    usd: float
    krw: float


def calculate_cost(model: str, usage: "ClaudeUsage") -> CostBreakdown:
    """토큰 사용량 → USD/KRW 비용."""
    pricing = _PRICING_USD_PER_MTOK.get(model)
    if pricing is None:
        logger.warning(f"가격표 미등록 모델: {model} — 비용 0으로 처리")
        return CostBreakdown(
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            usd=0.0,
            krw=0.0,
        )

    in_rate = pricing["input"]
    out_rate = pricing["output"]

    usd = (
        usage.input_tokens * in_rate
        + usage.output_tokens * out_rate
        + usage.cache_read_tokens * in_rate * 0.1
        + usage.cache_creation_tokens * in_rate * 1.25
    ) / 1_000_000

    return CostBreakdown(
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_creation_tokens=usage.cache_creation_tokens,
        usd=round(usd, 6),
        krw=round(usd * USD_TO_KRW, 2),
    )


def log_to_firestore(uid: str, agent: str, cost: CostBreakdown) -> None:
    """사용자별 일별 비용 누적. uid 없으면 익명 통계로 기록."""
    try:
        from firebase_admin import firestore

        db = firestore.client()
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if uid:
            doc_ref = db.collection("users").document(uid).collection("ai_usage").document(date_key)
        else:
            doc_ref = db.collection("ai_usage_anonymous").document(date_key)

        # 누적 업데이트 (Firestore Increment)
        doc_ref.set(
            {
                "date": date_key,
                f"agents.{agent}.calls": firestore.Increment(1),
                f"agents.{agent}.input_tokens": firestore.Increment(cost.input_tokens),
                f"agents.{agent}.output_tokens": firestore.Increment(cost.output_tokens),
                f"agents.{agent}.cache_read_tokens": firestore.Increment(cost.cache_read_tokens),
                f"agents.{agent}.cache_creation_tokens": firestore.Increment(cost.cache_creation_tokens),
                f"agents.{agent}.usd": firestore.Increment(cost.usd),
                f"agents.{agent}.krw": firestore.Increment(cost.krw),
                "total.usd": firestore.Increment(cost.usd),
                "total.krw": firestore.Increment(cost.krw),
                "last_updated": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    except Exception as e:
        # Firestore 장애가 분석 자체를 막아서는 안 됨
        logger.warning(f"비용 기록 실패 (uid={uid}, agent={agent}): {e}")


def log_usage(uid: str, agent: str, model: str, usage: "ClaudeUsage") -> CostBreakdown:
    """편의 함수: 비용 계산 + Firestore 기록 + 콘솔 로그."""
    cost = calculate_cost(model, usage)
    logger.info(
        f"[Claude:{agent}] {model} "
        f"in={cost.input_tokens} out={cost.output_tokens} "
        f"cache_r={cost.cache_read_tokens} cache_w={cost.cache_creation_tokens} "
        f"= ${cost.usd:.4f} ({cost.krw:.1f}원)"
    )
    log_to_firestore(uid, agent, cost)
    return cost
