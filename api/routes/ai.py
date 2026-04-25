"""Axis AI 분석 라우트 — Week 3 본격 구현.

엔드포인트:
  GET  /api/ai/personas       — 페르소나 목록 (Free/Pro 권한 표시)
  POST /api/ai/analyze        — 4 에이전트 LangGraph 파이프라인 (SSE 스트리밍 옵션)
  POST /api/ai/validate/{ticker} — Validator 단독 재실행

상세 스펙: docs/axis/api/ai.md
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ai", tags=["axis-ai"])


# ──────────────────────────────────────────────
# 요청/응답 스키마
# ──────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="6자리 종목 코드")
    query: str = Field("", description="자연어 쿼리 (옵션)")
    persona: str = Field("blackrock", description="blackrock | ark | graham")
    stream: bool = Field(True, description="SSE 스트리밍 여부")
    user_profile: Optional[dict] = Field(None, description="UserProfile dict (옵션)")


class ValidateRequest(BaseModel):
    ticker: str
    # 클라이언트가 캐시한 직전 분석 결과를 통째로 전달 (analysis_id 기반 영속화는 Week 3 후반)
    analyst_output: Optional[dict] = None
    research_output: Optional[dict] = None


class Persona(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    available_to_free: bool


# ──────────────────────────────────────────────
# 페르소나 목록
# ──────────────────────────────────────────────

_PERSONAS: list[Persona] = [
    Persona(
        id="blackrock",
        name="BlackRock 애널리스트",
        description="리스크 우선, 장기 가치 중심 분석",
        icon="🏛",
        available_to_free=True,
    ),
    Persona(
        id="ark",
        name="ARK 혁신 분석가",
        description="파괴적 혁신, 5년 시계 분석",
        icon="🚀",
        available_to_free=False,
    ),
    Persona(
        id="graham",
        name="Benjamin Graham 가치투자",
        description="안전마진, 저평가 발굴",
        icon="📚",
        available_to_free=False,
    ),
]


@router.get("/personas")
async def list_personas(request: Request) -> dict:
    """페르소나 목록 + 사용자 플랜에 따른 접근 권한."""
    user = getattr(request.state, "user", None) or {}
    user_plan = user.get("tier", "free")
    user_default = "blackrock"
    return {
        "personas": [p.model_dump() for p in _PERSONAS],
        "user_plan": user_plan,
        "user_default_persona": user_default,
    }


# ──────────────────────────────────────────────
# /api/ai/analyze — 4 에이전트 LangGraph 실행
# ──────────────────────────────────────────────

@router.post("/analyze")
async def analyze(req: AnalyzeRequest, request: Request):
    """LangGraph 4 에이전트 종목 분석. stream=True면 SSE.

    인증/티어 체크는 screener.middleware.AuthMiddleware가 처리. 여기선 페르소나 권한만 추가 검사.
    """
    # 페르소나 권한 (Free는 blackrock만)
    user = getattr(request.state, "user", None) or {}
    tier = user.get("tier", "free")
    uid = user.get("uid", "")

    persona_obj = next((p for p in _PERSONAS if p.id == req.persona), None)
    if persona_obj is None:
        raise HTTPException(400, f"Unknown persona: {req.persona}")
    if not persona_obj.available_to_free and tier == "free":
        raise HTTPException(
            402,
            {
                "code": "PERSONA_LOCKED",
                "message": f"'{persona_obj.name}'는 Pro 페르소나입니다.",
                "upgrade_url": "/pricing",
            },
        )

    # 종목 코드 형식 (KR 6자리 또는 알파벳 US)
    if not req.ticker or len(req.ticker) > 10:
        raise HTTPException(400, {"code": "INVALID_TICKER", "message": "유효한 종목 코드 필요"})

    # UserProfile 변환
    from agents.strategist import UserProfile

    try:
        user_profile = UserProfile(**(req.user_profile or {}))
    except Exception as e:
        raise HTTPException(400, f"잘못된 user_profile: {e}")

    if req.stream:
        return StreamingResponse(
            _stream_analysis(
                ticker=req.ticker,
                query=req.query,
                persona=req.persona,
                user_profile=user_profile,
                user_uid=uid,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # nginx 버퍼링 방지
            },
        )

    # Non-streaming
    from agents.graph import run_analysis

    t0 = time.time()
    final = await run_analysis(
        ticker=req.ticker,
        query=req.query,
        persona=req.persona,
        user_profile=user_profile,
        user_uid=uid,
    )
    elapsed = round(time.time() - t0, 2)

    return _build_full_response(final, elapsed)


def _build_full_response(final: dict, elapsed: float) -> dict:
    """non-streaming 모드 응답 dict 구성."""
    from agents.base import DISCLAIMER

    research = final.get("research_output")
    analyst = final.get("analyst_output")
    validator = final.get("validator_output")
    strategist = final.get("strategist_output")

    return {
        "ticker": final.get("ticker"),
        "persona": final.get("persona"),
        "research": research.model_dump() if research else None,
        "analyst": analyst.model_dump() if analyst else None,
        "validator": validator.model_dump() if validator else None,
        "strategist": strategist.model_dump() if strategist else None,
        "metadata": {
            "total_elapsed": elapsed,
            "retry_count": final.get("retry_count", 0),
            "validation_status": validator.overall_status if validator else None,
        },
        "disclaimer": DISCLAIMER,
    }


def _sse(event: str, data: dict) -> str:
    """SSE 단일 이벤트 직렬화."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _stream_analysis(
    *,
    ticker: str,
    query: str,
    persona: str,
    user_profile,
    user_uid: str,
) -> AsyncGenerator[str, None]:
    """LangGraph astream을 SSE로 변환.

    각 노드 완료 시 `{node}_complete` 이벤트 emit.
    """
    from agents.graph import create_analysis_graph

    t0 = time.time()
    graph = create_analysis_graph()

    initial = {
        "ticker": ticker,
        "query": query,
        "persona": persona,
        "user_uid": user_uid,
        "user_profile": user_profile,
        "retry_count": 0,
    }

    yield _sse(
        "start",
        {
            "ticker": ticker,
            "persona": persona,
            "estimated_seconds": 12,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    final_state: dict = {}
    try:
        async for chunk in graph.astream(initial):
            # chunk: {node_name: state_diff}
            for node_name, state_diff in chunk.items():
                if not isinstance(state_diff, dict):
                    continue
                final_state.update(state_diff)

                # 에이전트 결과별 이벤트
                if "research_output" in state_diff and state_diff["research_output"]:
                    yield _sse(
                        "research_complete",
                        {
                            "agent": "research",
                            "result": state_diff["research_output"].model_dump(),
                            "elapsed": round(time.time() - t0, 2),
                        },
                    )
                if "analyst_output" in state_diff and state_diff["analyst_output"]:
                    yield _sse(
                        "analyst_complete",
                        {
                            "agent": "analyst",
                            "result": state_diff["analyst_output"].model_dump(),
                            "elapsed": round(time.time() - t0, 2),
                        },
                    )
                if "validator_output" in state_diff and state_diff["validator_output"]:
                    yield _sse(
                        "validator_complete",
                        {
                            "agent": "validator",
                            "result": state_diff["validator_output"].model_dump(),
                            "elapsed": round(time.time() - t0, 2),
                            "retry_count": final_state.get("retry_count", 0),
                        },
                    )
                if "strategist_output" in state_diff and state_diff["strategist_output"]:
                    yield _sse(
                        "strategist_complete",
                        {
                            "agent": "strategist",
                            "result": state_diff["strategist_output"].model_dump(),
                            "elapsed": round(time.time() - t0, 2),
                        },
                    )
    except Exception as e:
        logger.exception(f"[ai/analyze stream] 실행 실패: {e}")
        yield _sse("error", {"code": "AI_ERROR", "message": str(e)})
        return

    yield _sse(
        "complete",
        {
            "total_elapsed": round(time.time() - t0, 2),
            "retry_count": final_state.get("retry_count", 0),
            "validation_status": (
                final_state["validator_output"].overall_status
                if final_state.get("validator_output")
                else None
            ),
        },
    )


# ──────────────────────────────────────────────
# /api/ai/validate/{ticker} — Validator 단독 재실행
# ──────────────────────────────────────────────

@router.post("/validate/{ticker}")
async def validate(ticker: str, req: ValidateRequest, request: Request):
    """기존 분석 결과의 수치를 실시간 재검증. 클라이언트가 직전 결과를 함께 전달."""
    from agents.analyst import AnalystResult
    from agents.research import ResearchResult
    from agents.validator import ValidatorAgent, ValidatorInput

    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")

    if not ticker or len(ticker) > 10:
        raise HTTPException(400, {"code": "INVALID_TICKER", "message": "유효한 종목 코드 필요"})

    # 클라이언트 dict → Pydantic 복원
    research_obj = ResearchResult.model_validate(req.research_output) if req.research_output else None
    analyst_obj = AnalystResult.model_validate(req.analyst_output) if req.analyst_output else None

    if analyst_obj is None:
        raise HTTPException(
            400,
            {"code": "MISSING_ANALYST", "message": "analyst_output이 필요합니다 (직전 분석 결과를 전달하세요)."},
        )

    t0 = time.time()
    result = await ValidatorAgent().run(
        ValidatorInput(
            ticker=ticker,
            research_output=research_obj,
            analyst_output=analyst_obj,
        ),
        uid=uid,
    )

    return {
        "ticker": ticker,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.time() - t0, 2),
        **result.model_dump(),
    }
