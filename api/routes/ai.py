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
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ai", tags=["axis-ai"])


# ──────────────────────────────────────────────
# 요금제 한도
# ──────────────────────────────────────────────

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"analyses": 20, "validations": 10, "discoveries": 5},
    "pro": {"analyses": -1, "validations": -1, "discoveries": -1},
    "premium": {"analyses": -1, "validations": -1, "discoveries": -1},
}


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
    """non-streaming 모드 응답 dict 구성. LEGAL: 모든 문자열 필터 통과."""
    from agents.base import DISCLAIMER

    research = final.get("research_output")
    analyst = final.get("analyst_output")
    validator = final.get("validator_output")
    strategist = final.get("strategist_output")

    payload = {
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
    return _wrap_legal(payload, "/api/ai/analyze")


def _sanitize_response(obj, _findings: Optional[list[str]] = None):
    """LEGAL: 응답 직렬화 직전 모든 string 필드를 filter_forbidden 통과.

    재귀: dict, list, str → 처리. 그 외 타입 (int/float/bool/None)은 그대로.
    Caller가 _findings 리스트를 넘기면 발견된 단어 누적 (로깅 용도).
    """
    from agents.base import BaseAgent

    if isinstance(obj, str):
        cleaned, found = BaseAgent.filter_forbidden(obj)
        if found and _findings is not None:
            _findings.extend(found)
        return cleaned
    if isinstance(obj, dict):
        return {k: _sanitize_response(v, _findings) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_response(item, _findings) for item in obj]
    return obj


def _wrap_legal(payload: dict, route: str) -> dict:
    """non-streaming 응답을 LEGAL 필터 통과 후 반환. 필터링 발생 시 warning 로그."""
    findings: list[str] = []
    cleaned = _sanitize_response(payload, findings)
    if findings:
        logger.warning(
            f"[LEGAL] route={route} forbidden words filtered: {sorted(set(findings))}"
        )
    return cleaned


def _sse(event: str, data: dict) -> str:
    """SSE 단일 이벤트 직렬화 — LEGAL 필터 자동 적용."""
    findings: list[str] = []
    cleaned = _sanitize_response(data, findings)
    if findings:
        logger.warning(
            f"[LEGAL] sse event={event} forbidden words filtered: {sorted(set(findings))}"
        )
    return f"event: {event}\ndata: {json.dumps(cleaned, ensure_ascii=False, default=str)}\n\n"


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

    return _wrap_legal(
        {
            "ticker": ticker,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.time() - t0, 2),
            **result.model_dump(),
        },
        "/api/ai/validate",
    )


# ──────────────────────────────────────────────
# /api/ai/watchlist/{ticker}/entry-points — 진입선/메타 영속화
# ──────────────────────────────────────────────

class EntryPointsPayload(BaseModel):
    tier_1: int = Field(..., description="1차 관찰 구간 (원)")
    tier_2: int = Field(..., description="2차 관찰 구간 (원)")
    tier_3: int = Field(..., description="3차 관찰 구간 (원)")
    technical_basis: list[str] = Field(default_factory=list)
    persona_used: str = Field("manual", description="blackrock/ark/graham/manual")
    source: str = Field("manual", description="manual | strategist")


def _watchlist_meta_doc(uid: str, ticker: str):
    """users/{uid}/watchlist_meta/{ticker} 문서 참조."""
    from screener.db.firebase_client import get_db

    return (
        get_db()
        .collection("users")
        .document(uid)
        .collection("watchlist_meta")
        .document(ticker)
    )


@router.get("/watchlist/{ticker}/entry-points")
async def get_entry_points(ticker: str, request: Request):
    """저장된 진입선 조회. 없으면 entry_points=null."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    if not ticker or len(ticker) > 10:
        raise HTTPException(400, {"code": "INVALID_TICKER", "message": "유효한 종목 코드 필요"})

    try:
        doc = _watchlist_meta_doc(uid, ticker).get()
        if not doc.exists:
            return {"ticker": ticker, "entry_points": None}
        data = doc.to_dict() or {}
        return {
            "ticker": ticker,
            "entry_points": data.get("entry_points"),
            "persona_used": data.get("persona_used", "manual"),
            "source": data.get("source", "manual"),
            "saved_at": data.get("saved_at"),
        }
    except Exception as e:
        logger.warning(f"entry_points 조회 실패 (uid={uid}, ticker={ticker}): {e}")
        return {"ticker": ticker, "entry_points": None, "error": str(e)}


@router.put("/watchlist/{ticker}/entry-points")
async def save_entry_points(ticker: str, payload: EntryPointsPayload, request: Request):
    """진입선 저장 (Strategist 결과 또는 사용자 수동 설정)."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    if not ticker or len(ticker) > 10:
        raise HTTPException(400, {"code": "INVALID_TICKER", "message": "유효한 종목 코드 필요"})

    if payload.source not in ("manual", "strategist"):
        raise HTTPException(400, {"code": "INVALID_SOURCE", "message": "source는 manual|strategist"})

    try:
        from firebase_admin import firestore

        _watchlist_meta_doc(uid, ticker).set(
            {
                "ticker": ticker,
                "entry_points": {
                    "tier_1": payload.tier_1,
                    "tier_2": payload.tier_2,
                    "tier_3": payload.tier_3,
                    "technical_basis": payload.technical_basis,
                },
                "persona_used": payload.persona_used,
                "source": payload.source,
                "saved_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return {"ok": True, "ticker": ticker}
    except Exception as e:
        logger.exception(f"entry_points 저장 실패: {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


@router.delete("/watchlist/{ticker}/entry-points")
async def delete_entry_points(ticker: str, request: Request):
    """진입선 삭제 (관심 종목에서 빼지 않고 진입선 메타만 삭제)."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    try:
        _watchlist_meta_doc(uid, ticker).delete()
        return {"ok": True, "ticker": ticker}
    except Exception as e:
        logger.warning(f"entry_points 삭제 실패: {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


# ──────────────────────────────────────────────
# /api/ai/usage — 월 사용량 조회
# ──────────────────────────────────────────────

@router.get("/usage")
async def get_usage(request: Request):
    """현재 월의 Axis AI 사용량 + 플랜 한도 비교.

    cost_tracker가 기록한 users/{uid}/ai_usage/{YYYY-MM-DD} 문서를 합산.
    Strategist 호출수 = analyses, Validator(단독) 호출 = validations, discoverer = discoveries.
    """
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    tier = (user.get("tier") or "free").lower()

    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    month_prefix = datetime.now().strftime("%Y-%m")
    used = {"analyses": 0, "validations": 0, "discoveries": 0}

    try:
        from screener.db.firebase_client import get_db

        usage_col = (
            get_db()
            .collection("users")
            .document(uid)
            .collection("ai_usage")
        )
        # YYYY-MM-DD 문서 ID라 간단한 prefix 비교
        for doc in usage_col.stream():
            if not doc.id.startswith(month_prefix):
                continue
            data = doc.to_dict() or {}
            agents = data.get("agents", {})
            # Strategist 호출이 분석 1회를 의미 (Strategist는 파이프라인 끝)
            used["analyses"] += int(agents.get("strategist", {}).get("calls", 0) or 0)
            used["validations"] += int(agents.get("validator", {}).get("calls", 0) or 0)
            used["discoveries"] += int(agents.get("discoverer", {}).get("calls", 0) or 0)
    except Exception as e:
        logger.warning(f"사용량 조회 실패 (uid={uid}): {e}")

    limits = PLAN_LIMITS.get(tier, PLAN_LIMITS["free"])

    def _summary(used_n: int, limit: int) -> dict:
        if limit == -1:
            return {"used": used_n, "limit": -1, "remaining": -1}
        return {"used": used_n, "limit": limit, "remaining": max(0, limit - used_n)}

    # 다음 달 1일 KST 기준 reset
    now_utc = datetime.now(timezone.utc)
    next_year = now_utc.year + (1 if now_utc.month == 12 else 0)
    next_month = 1 if now_utc.month == 12 else now_utc.month + 1
    reset_at = datetime(next_year, next_month, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()

    return {
        "user_uid": uid,
        "plan": tier,
        "month": month_prefix,
        "usage": {
            "analyses": _summary(used["analyses"], limits["analyses"]),
            "validations": _summary(used["validations"], limits["validations"]),
            "discoveries": _summary(used["discoveries"], limits["discoveries"]),
        },
        "reset_at": reset_at,
        "upgrade_url": "/pricing",
    }


# ──────────────────────────────────────────────
# /api/ai/discover — 자연어 종목 발견 (rename of /recommend)
# ──────────────────────────────────────────────

class DiscoverFiltersBody(BaseModel):
    market: Optional[list[str]] = None
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    sectors: Optional[list[str]] = None


class DiscoverRequestBody(BaseModel):
    query: str = Field(..., min_length=2)
    max_results: int = Field(5, ge=1, le=10)
    exclude_tickers: list[str] = Field(default_factory=list)
    filters: Optional[DiscoverFiltersBody] = None


@router.post("/discover")
async def discover(req: DiscoverRequestBody, request: Request):
    """자연어 쿼리 → 관찰 가치 종목 (Claude Sonnet, ~35원/호출).

    LEGAL: 응답에 "추천" 단어 사용 금지. "관찰 가치", "참고" 표현으로.
    """
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")

    # 컨텍스트 dict → DiscovererInput
    from agents.discoverer import (
        DiscoverFilters,
        DiscovererAgent,
        DiscovererInput,
    )

    filters = None
    if req.filters:
        filters = DiscoverFilters(**req.filters.model_dump(exclude_none=True))

    try:
        agent_input = DiscovererInput(
            query=req.query,
            max_results=req.max_results,
            exclude_tickers=req.exclude_tickers,
            filters=filters,
        )
    except Exception as e:
        raise HTTPException(400, {"code": "INVALID_INPUT", "message": str(e)})

    t0 = time.time()
    try:
        result = await DiscovererAgent().run(agent_input, uid=uid)
    except Exception as e:
        logger.exception(f"[ai/discover] 실패: {e}")
        raise HTTPException(500, {"code": "AI_ERROR", "message": str(e)})

    return _wrap_legal(
        {
            "elapsed_seconds": round(time.time() - t0, 2),
            **result.model_dump(),
        },
        "/api/ai/discover",
    )


# ──────────────────────────────────────────────
# /api/ai/profile — Axis 사용자 프로파일 (온보딩)
# ──────────────────────────────────────────────

class AxisProfileBody(BaseModel):
    investing_experience: Optional[str] = None  # "beginner" | "1-5y" | "5y+"
    holding_period: Optional[str] = None  # "1m" | "6m" | "1-2y" | "3y+"
    volatility_tolerance: Optional[str] = None  # "10" | "20" | "30"
    interested_sectors: list[str] = Field(default_factory=list)
    investment_principles: list[str] = Field(default_factory=list)
    preferred_persona: Optional[str] = None  # "blackrock" | "ark" | "graham"


@router.get("/profile")
async def get_axis_profile(request: Request):
    """현재 사용자의 Axis 프로파일 조회. 온보딩 완료 여부도 반환."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    try:
        from screener.db.firebase_client import get_db

        doc = get_db().collection("users").document(uid).get()
        if not doc.exists:
            return {"profile": None, "onboarded": False}
        data = doc.to_dict() or {}
        profile = data.get("axis_profile")
        return {
            "profile": profile,
            "onboarded": bool(profile and profile.get("onboarded_at")),
        }
    except Exception as e:
        logger.warning(f"profile 조회 실패 (uid={uid}): {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


@router.put("/profile")
async def save_axis_profile(payload: AxisProfileBody, request: Request):
    """Axis 프로파일 저장. 입력값을 화이트리스트 검증 후 admin SDK로 영속화."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    valid_experience = {"beginner", "1-5y", "5y+", None}
    valid_period = {"1m", "6m", "1-2y", "3y+", None}
    valid_volatility = {"10", "20", "30", None}
    valid_persona = {"blackrock", "ark", "graham", None}

    if payload.investing_experience not in valid_experience:
        raise HTTPException(400, {"code": "INVALID_EXPERIENCE", "message": "investing_experience 값 오류"})
    if payload.holding_period not in valid_period:
        raise HTTPException(400, {"code": "INVALID_PERIOD", "message": "holding_period 값 오류"})
    if payload.volatility_tolerance not in valid_volatility:
        raise HTTPException(400, {"code": "INVALID_VOLATILITY", "message": "volatility_tolerance 값 오류"})
    if payload.preferred_persona not in valid_persona:
        raise HTTPException(400, {"code": "INVALID_PERSONA", "message": "preferred_persona 값 오류"})

    # 길이 제한 (DOS 방지)
    sectors = [str(s)[:40] for s in payload.interested_sectors[:20]]
    principles = [str(p)[:200] for p in payload.investment_principles[:10]]

    try:
        from firebase_admin import firestore as fb_firestore

        from screener.db.firebase_client import get_db

        get_db().collection("users").document(uid).set(
            {
                "axis_profile": {
                    "investing_experience": payload.investing_experience,
                    "holding_period": payload.holding_period,
                    "volatility_tolerance": payload.volatility_tolerance,
                    "interested_sectors": sectors,
                    "investment_principles": principles,
                    "preferred_persona": payload.preferred_persona,
                    "onboarded_at": fb_firestore.SERVER_TIMESTAMP,
                }
            },
            merge=True,
        )
        return {"ok": True}
    except Exception as e:
        logger.exception(f"profile 저장 실패: {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


# ──────────────────────────────────────────────
# /api/ai/screeners/custom — 커스텀 스크리너 CRUD (Pro 전용)
# ──────────────────────────────────────────────

# 화이트리스트: 사용자가 저장 가능한 필터 키 + 타입.
# v7.5 ScreenerFilter dataclass 필드 중 안전한 서브셋만 허용.
# (LEGAL: surge_only/pre_surge_only 등 권유성 의미가 강한 플래그는 제외)
CUSTOM_FILTER_SCHEMA: dict[str, type] = {
    "market": str,           # "ALL" | "KR" | "US"
    "per_min": float,
    "per_max": float,
    "pbr_min": float,
    "pbr_max": float,
    "div_yield_min": float,
    "roe_min": float,
    "roe_max": float,
    "market_cap_min": float,
    "market_cap_max": float,
    "volume_ratio_min": float,
    "trading_value_min": float,
    "change_pct_min": float,
    "change_pct_max": float,
    "rsi_min": float,
    "rsi_max": float,
    "golden_cross": bool,
    "ma_aligned": bool,
}

ALLOWED_SORT_KEYS = {
    "buy_score", "change_pct", "volume_ratio", "rsi", "per", "pbr", "roe",
    "market_cap", "div_yield", "vs_high_52w", "trading_value",
}


class CustomScreenerPayload(BaseModel):
    """저장/업데이트 페이로드."""
    name: str = Field(..., min_length=1, max_length=40)
    filters: dict = Field(default_factory=dict)
    sort_by: str = Field("buy_score")
    sort_asc: bool = Field(False)


def _custom_screeners_col(uid: str):
    """users/{uid}/custom_screeners collection."""
    from screener.db.firebase_client import get_db

    return (
        get_db()
        .collection("users")
        .document(uid)
        .collection("custom_screeners")
    )


def _require_pro(request: Request) -> str:
    """uid 추출 + Pro/Premium 확인. 실패 시 HTTPException."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})
    tier = (user.get("tier") or "free").lower()
    if tier not in ("pro", "premium"):
        raise HTTPException(
            402,
            {"code": "PRO_REQUIRED", "message": "커스텀 스크리너는 Pro 이상 전용입니다."},
        )
    return uid


def _validate_filters(filters: dict) -> dict:
    """화이트리스트 키 + 타입 검증. 잘못된 키/타입은 422 응답."""
    if not isinstance(filters, dict):
        raise HTTPException(
            422, {"code": "INVALID_FILTERS", "message": "filters는 객체여야 합니다."}
        )

    # 알 수 없는 키 거부 (저장 화이트리스트 외 항목 차단)
    unknown = [k for k in filters.keys() if k not in CUSTOM_FILTER_SCHEMA]
    if unknown:
        raise HTTPException(
            422,
            {
                "code": "UNKNOWN_FILTER",
                "message": f"허용되지 않은 필터: {', '.join(unknown)}",
            },
        )

    cleaned: dict = {}
    for key, expected_type in CUSTOM_FILTER_SCHEMA.items():
        if key not in filters:
            continue
        v = filters[key]
        if v is None:
            continue
        try:
            if expected_type is bool:
                if isinstance(v, str):
                    cleaned[key] = v.lower() == "true"
                else:
                    cleaned[key] = bool(v)
            elif expected_type is float:
                cleaned[key] = float(v)
            elif expected_type is int:
                cleaned[key] = int(v)
            elif expected_type is str:
                s = str(v).strip()
                if s:
                    cleaned[key] = s
        except (ValueError, TypeError):
            raise HTTPException(
                422,
                {
                    "code": "INVALID_FILTER_VALUE",
                    "message": f"'{key}' 값 형식이 잘못되었습니다.",
                },
            )

    # 범위 역전 검증 (min > max)
    range_pairs = [
        ("per_min", "per_max", "PER"),
        ("pbr_min", "pbr_max", "PBR"),
        ("roe_min", "roe_max", "ROE"),
        ("market_cap_min", "market_cap_max", "시총"),
        ("change_pct_min", "change_pct_max", "등락률"),
        ("rsi_min", "rsi_max", "RSI"),
    ]
    for min_k, max_k, label in range_pairs:
        if min_k in cleaned and max_k in cleaned:
            if cleaned[min_k] > cleaned[max_k]:
                raise HTTPException(
                    422,
                    {
                        "code": "INVERTED_RANGE",
                        "message": f"{label} 최소값이 최대값보다 큽니다.",
                    },
                )
    return cleaned


def _doc_to_screener(doc) -> dict:
    data = doc.to_dict() or {}
    created = data.get("created_at")
    updated = data.get("updated_at")
    return {
        "id": doc.id,
        "name": data.get("name", ""),
        "filters": data.get("filters") or {},
        "sort_by": data.get("sort_by", "buy_score"),
        "sort_asc": bool(data.get("sort_asc", False)),
        "created_at": (
            created.isoformat() if hasattr(created, "isoformat") else None
        ),
        "updated_at": (
            updated.isoformat() if hasattr(updated, "isoformat") else None
        ),
    }


@router.get("/screeners/custom")
async def list_custom_screeners(request: Request):
    """사용자가 저장한 커스텀 스크리너 목록."""
    uid = _require_pro(request)
    try:
        docs = _custom_screeners_col(uid).order_by("updated_at", direction="DESCENDING").stream()
        screeners = [_doc_to_screener(d) for d in docs]
        return {"screeners": screeners}
    except Exception as e:
        logger.exception(f"커스텀 스크리너 목록 조회 실패: {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


@router.post("/screeners/custom")
async def create_custom_screener(payload: CustomScreenerPayload, request: Request):
    """신규 저장. 사용자당 최대 20개. 동시 POST 차단을 위해 Firestore 트랜잭션 사용."""
    uid = _require_pro(request)

    if payload.sort_by not in ALLOWED_SORT_KEYS:
        raise HTTPException(
            422,
            {"code": "INVALID_SORT", "message": f"'{payload.sort_by}' 정렬 키는 허용되지 않습니다."},
        )
    cleaned_filters = _validate_filters(payload.filters)

    try:
        from firebase_admin import firestore as fb_firestore
        from screener.db.firebase_client import get_db

        col = _custom_screeners_col(uid)
        doc_ref = col.document()
        doc_data = {
            "name": payload.name.strip(),
            "filters": cleaned_filters,
            "sort_by": payload.sort_by,
            "sort_asc": bool(payload.sort_asc),
            "created_at": fb_firestore.SERVER_TIMESTAMP,
            "updated_at": fb_firestore.SERVER_TIMESTAMP,
        }

        @fb_firestore.transactional
        def _save_with_quota_check(transaction):
            # 트랜잭션 내에서 카운트 + 쓰기 → 동시 호출 시 race 차단
            existing = list(col.limit(21).stream(transaction=transaction))
            if len(existing) >= 20:
                raise HTTPException(
                    409,
                    {"code": "QUOTA_EXCEEDED", "message": "최대 20개까지 저장 가능합니다."},
                )
            transaction.set(doc_ref, doc_data)

        transaction = get_db().transaction()
        _save_with_quota_check(transaction)
        return {"ok": True, "id": doc_ref.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"커스텀 스크리너 저장 실패: {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


@router.delete("/screeners/custom/{screener_id}")
async def delete_custom_screener(screener_id: str, request: Request):
    """삭제."""
    uid = _require_pro(request)
    if not screener_id or len(screener_id) > 64:
        raise HTTPException(400, {"code": "INVALID_ID", "message": "유효한 ID 필요"})
    try:
        _custom_screeners_col(uid).document(screener_id).delete()
        return {"ok": True}
    except Exception as e:
        logger.exception(f"커스텀 스크리너 삭제 실패: {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


# ──────────────────────────────────────────────
# /api/ai/notifications/preferences — 알림 설정 (MVP)
# ──────────────────────────────────────────────
# v1.1 발송 잡(Mailgun + Cloud Scheduler) 도입 전, 사용자 opt-in만 미리 수집.
# 토글 데이터는 users/{uid}.notification_preferences 필드에 저장.

class NotificationPreferences(BaseModel):
    """알림 채널별 토글. 모두 default false (opt-in)."""
    daily_briefing_enabled: bool = Field(False, description="매일 07:00 KST 시황 브리핑")
    entry_point_alerts_enabled: bool = Field(False, description="watchlist 진입선 도달 알림")
    email_override: Optional[str] = Field(None, description="기본 Firebase email 외 수신 주소 (옵션)")


def _default_preferences() -> dict:
    return {
        "daily_briefing_enabled": False,
        "entry_point_alerts_enabled": False,
        "email_override": None,
    }


@router.get("/notifications/preferences")
async def get_notification_preferences(request: Request):
    """알림 설정 조회. 미설정이면 기본값(전부 off)."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    try:
        from screener.db.firebase_client import get_db

        doc = get_db().collection("users").document(uid).get()
        prefs = (doc.to_dict() or {}).get("notification_preferences") if doc.exists else None
        return {
            "preferences": prefs or _default_preferences(),
            "user_email": user.get("email"),
        }
    except Exception as e:
        logger.warning(f"notification preferences 조회 실패 (uid={uid}): {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})


@router.put("/notifications/preferences")
async def save_notification_preferences(
    payload: NotificationPreferences, request: Request
):
    """알림 설정 저장. email_override는 형식 검증만 (실제 발송은 v1.1)."""
    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "로그인 필요"})

    # 간단한 이메일 형식 검증
    email_override: Optional[str] = None
    if payload.email_override is not None:
        s = payload.email_override.strip()
        if s:
            if "@" not in s or "." not in s.split("@")[-1] or len(s) > 200:
                raise HTTPException(
                    422,
                    {"code": "INVALID_EMAIL", "message": "이메일 형식이 올바르지 않습니다."},
                )
            email_override = s

    try:
        from firebase_admin import firestore as fb_firestore
        from screener.db.firebase_client import get_db

        get_db().collection("users").document(uid).set(
            {
                "notification_preferences": {
                    "daily_briefing_enabled": bool(payload.daily_briefing_enabled),
                    "entry_point_alerts_enabled": bool(payload.entry_point_alerts_enabled),
                    "email_override": email_override,
                    "updated_at": fb_firestore.SERVER_TIMESTAMP,
                }
            },
            merge=True,
        )
        return {"ok": True}
    except Exception as e:
        logger.exception(f"notification preferences 저장 실패: {e}")
        raise HTTPException(500, {"code": "STORAGE_ERROR", "message": str(e)})
