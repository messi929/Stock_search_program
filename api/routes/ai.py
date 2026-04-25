"""Axis AI 분석 라우트 — Week 1 스캐폴딩.

엔드포인트는 모두 501 Not Implemented 상태로 정의만 되어 있으며,
실제 로직은 Week 2~3 (4 에이전트 + LangGraph 통합) 단계에서 채워집니다.

상세 스펙: docs/axis/api/ai.md
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ai", tags=["axis-ai"])


# ──────────────────────────────────────────────
# 요청/응답 스키마 (placeholder)
# ──────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str = Field(..., description="자연어 질의 또는 종목명")
    ticker: Optional[str] = Field(None, description="명시적 종목 코드 (옵션)")
    persona: str = Field("blackrock", description="blackrock | ark | graham")


class ValidateRequest(BaseModel):
    analysis_id: str = Field(..., description="재검증할 분석 이력 ID")


class Persona(BaseModel):
    id: str
    name: str
    description: str
    available_for_free: bool


# ──────────────────────────────────────────────
# 페르소나 목록 — Week 2 페르소나 프롬프트 작성 후 활성화
# ──────────────────────────────────────────────

_PERSONAS: list[Persona] = [
    Persona(
        id="blackrock",
        name="블랙록",
        description="리스크 프레임 중심, 장기 가치",
        available_for_free=True,
    ),
    Persona(
        id="ark",
        name="ARK",
        description="파괴적 혁신 서사, 고성장",
        available_for_free=False,
    ),
    Persona(
        id="graham",
        name="그레이엄",
        description="안전마진, 저평가",
        available_for_free=False,
    ),
]


@router.get("/personas")
async def list_personas() -> dict:
    """페르소나 목록 반환. Free 사용자는 블랙록만 사용 가능."""
    return {"personas": [p.model_dump() for p in _PERSONAS]}


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, request: Request):
    """4-Agent LangGraph 분석. Week 3에서 구현."""
    raise HTTPException(
        status_code=501,
        detail="Axis AI 분석은 Week 3 LangGraph 통합 후 활성화됩니다.",
    )


@router.post("/validate")
async def validate(req: ValidateRequest, request: Request):
    """기존 분석 재검증. Week 2 Validator 에이전트 구현 후 활성화."""
    raise HTTPException(
        status_code=501,
        detail="Validator 에이전트는 Week 2에 구현됩니다.",
    )
