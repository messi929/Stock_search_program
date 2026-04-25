# AI API 엔드포인트 스펙

> **Base URL**: `https://stock-screener-119320994983.asia-northeast3.run.app`  
> **인증**: Firebase JWT Bearer Token

---

## 📋 엔드포인트 목록

| Method | Path | 설명 | Plan |
|--------|------|------|------|
| POST | `/api/ai/analyze` | 종목 분석 (4개 에이전트) | All |
| POST | `/api/ai/validate/{analysis_id}` | 분석 결과 재검증 | All |
| GET | `/api/ai/personas` | 페르소나 목록 | All |
| POST | `/api/ai/recommend` | 자연어 종목 추천 | All |
| POST | `/api/ai/entry-suggest` | AI 참고 진입선 제안 | Pro |
| GET | `/api/ai/usage` | 사용량 조회 | All |

---

## 🚀 POST `/api/ai/analyze` (메인)

### 설명
4개 에이전트가 종목을 종합 분석. SSE 스트리밍 지원.

### Request

**Headers**
```
Authorization: Bearer {firebase_id_token}
Content-Type: application/json
Accept: text/event-stream  # SSE 스트리밍
```

**Body**
```json
{
  "ticker": "207940",
  "query": "삼성바이오로직스 어때?",
  "persona": "blackrock",
  "use_cache": true,
  "stream": true
}
```

**Field 설명**
- `ticker` (required): 6자리 종목 코드
- `query` (optional): 자연어 쿼리 (없으면 표준 분석)
- `persona`: "blackrock" | "ark" | "graham" (기본: blackrock)
- `use_cache`: 30분 캐시 활용 (기본: true)
- `stream`: SSE 스트리밍 (기본: true)

### Response (Streaming)

```
event: start
data: {"analysis_id": "uuid-xxx", "estimated_seconds": 8}

event: research_start
data: {"agent": "research"}

event: research_complete
data: {
  "agent": "research",
  "result": {
    "market_sentiment": "낙관적",
    "relevant_news": [...],
    "macro_context": {...},
    "summary": "..."
  },
  "elapsed": 2.8
}

event: analyst_start
data: {"agent": "analyst"}

event: analyst_complete
data: {
  "agent": "analyst",
  "result": {...},
  "elapsed": 3.5
}

event: validator_start
data: {"agent": "validator"}

event: validator_complete
data: {
  "agent": "validator",
  "result": {
    "overall_status": "PASS",
    "checks": [...],
    "contrarian_scenarios": [...],
    "confidence_score": 0.92
  },
  "elapsed": 2.3
}

event: strategist_start
data: {"agent": "strategist"}

event: strategist_complete
data: {
  "agent": "strategist",
  "result": {
    "persona_used": "blackrock",
    "summary": "...",
    "entry_points": {...},
    "alert_conditions": [...]
  },
  "elapsed": 4.7
}

event: complete
data: {
  "analysis_id": "uuid-xxx",
  "total_elapsed": 8.5,
  "total_cost_krw": 215,
  "saved_to_history": true
}

event: error
data: {"error": "...", "code": "VALIDATION_FAILED"}
```

### Response (Non-Streaming)

```json
{
  "analysis_id": "uuid-xxx",
  "ticker": "207940",
  "persona": "blackrock",
  
  "research": {...},
  "analyst": {...},
  "validator": {...},
  "strategist": {...},
  
  "metadata": {
    "total_elapsed": 8.5,
    "total_cost_krw": 215,
    "total_tokens": 12345,
    "validation_status": "PASS"
  },
  
  "disclaimer": "📌 본 분석은 투자 권유가 아닌 정보 제공입니다..."
}
```

### Error Codes

| Code | Status | 의미 |
|------|--------|------|
| 400 | INVALID_TICKER | 종목 코드 형식 오류 |
| 401 | UNAUTHORIZED | 토큰 없음/유효하지 않음 |
| 402 | QUOTA_EXCEEDED | Free 한도 초과 |
| 404 | TICKER_NOT_FOUND | 존재하지 않는 종목 |
| 429 | RATE_LIMITED | 분당 요청 한도 초과 |
| 500 | AI_ERROR | Claude API 실패 |
| 503 | DATA_UNAVAILABLE | Firestore 데이터 없음 |

### 사용량 제한

```
Free Tier:
- 월 20회
- 분당 2회

Pro Tier:
- 무제한
- 분당 10회

Premium Tier:
- 무제한
- 분당 20회
- 우선 큐 (Cloud Run 인스턴스 우선 배정)
```

---

## 🔍 POST `/api/ai/validate/{analysis_id}`

### 설명
이전 분석 결과의 모든 수치를 실시간 재검증

### Request

```
POST /api/ai/validate/uuid-xxx
Authorization: Bearer {token}
```

### Response

```json
{
  "analysis_id": "uuid-xxx",
  "validated_at": "2026-04-25T15:30:00Z",
  "original_analyzed_at": "2026-04-25T14:30:00Z",
  "elapsed_minutes": 60,
  
  "overall_status": "WARN",  // PASS / WARN / FAIL
  
  "checks": [
    {
      "item": "삼성바이오 현재가",
      "claimed": 1561000,
      "verified": 1545000,
      "diff_pct": -1.03,
      "status": "OK",
      "last_data_update": "2026-04-25T15:29:30Z"
    },
    {
      "item": "RSI",
      "claimed": 42.5,
      "verified": 41.8,
      "diff_pct": -1.65,
      "status": "OK",
      "last_data_update": "2026-04-25T15:29:30Z"
    }
  ],
  
  "stale_data_count": 0,
  "fresh_data_count": 8,
  "confidence_score": 0.95,
  "requires_reanalysis": false,
  
  "recommendation": "신선한 데이터로 분석되었습니다. 재분석 불필요."
}
```

### 사용량 제한

```
Free: 월 10회
Pro: 무제한
```

---

## 🎭 GET `/api/ai/personas`

### 설명
사용 가능한 페르소나 목록 + 사용자 플랜에 따른 접근 권한

### Response

```json
{
  "personas": [
    {
      "id": "blackrock",
      "name": "BlackRock 애널리스트",
      "description": "리스크 우선, 장기 가치 중심 분석",
      "icon": "🏛",
      "available_to_free": true
    },
    {
      "id": "ark",
      "name": "ARK 혁신 분석가",
      "description": "파괴적 혁신, 5년 시계 분석",
      "icon": "🚀",
      "available_to_free": false
    },
    {
      "id": "graham",
      "name": "Benjamin Graham 가치투자",
      "description": "안전마진, 저평가 발굴",
      "icon": "📚",
      "available_to_free": false
    }
  ],
  "user_plan": "free",
  "user_default_persona": "blackrock"
}
```

---

## 💬 POST `/api/ai/recommend`

### 설명
자연어 쿼리로 종목 추천 (관심 종목 추가 화면에서 사용)

### Request

```json
{
  "query": "AI 2차 수혜주 찾아줘",
  "max_results": 5,
  "exclude_tickers": ["005930"],
  "filters": {
    "market": ["KOSPI", "KOSDAQ"],
    "min_market_cap": 1000000000000,
    "max_market_cap": null
  }
}
```

### Response

```json
{
  "query": "AI 2차 수혜주 찾아줘",
  "interpretation": "AI 1차 수혜주(엔비디아, 메모리)는 이미 프라이싱되어, 2차 수혜주인 전력 인프라·PCB·소재 영역을 분석했습니다.",
  
  "stocks": [
    {
      "ticker": "010120",
      "name": "LS일렉트릭",
      "market": "KOSPI",
      "cap_category": "large",
      "sector": "전력인프라",
      "current_price": 78500,
      "reason": "북미 AI 데이터센터 전력 수요 직접 수혜. 1분기 매출 +32% YoY."
    },
    {
      "ticker": "007660",
      "name": "이수페타시스",
      "market": "KOSDAQ",
      "cap_category": "mid",
      "sector": "PCB",
      "current_price": 23400,
      "reason": "AI 서버용 고다층 PCB 국산화 대표. 고부가 비중 확대 중."
    }
  ],
  
  "metadata": {
    "elapsed_seconds": 4.2,
    "tokens_used": 3456,
    "cost_krw": 35
  },
  
  "disclaimer": "📌 본 분석은 투자 권유가 아닌 정보 제공입니다..."
}
```

### 사용량 제한

```
Free: 월 5회
Pro: 무제한
```

---

## 🎯 POST `/api/ai/entry-suggest` (Pro 전용)

### 설명
AI가 기술적 분석 기반으로 진입선 참고 수치 제안

### Request

```json
{
  "ticker": "207940",
  "investment_horizon": "1-2y",
  "user_volatility_tolerance": "20"
}
```

### Response

```json
{
  "ticker": "207940",
  "current_price": 1561000,
  
  "tiers": [
    {
      "level": "1차",
      "price": 1405000,
      "pct_from_current": -10.0,
      "technical_basis": [
        "20일 이평선 (1,420,000원) 부근",
        "3개월 저점 (1,398,000원)",
        "심리적 지지선 1,400,000원"
      ]
    },
    {
      "level": "2차",
      "price": 1327000,
      "pct_from_current": -15.0,
      "technical_basis": [
        "60일 이평선 부근",
        "2025년 12월 저점 근처"
      ]
    },
    {
      "level": "3차",
      "price": 1249000,
      "pct_from_current": -20.0,
      "technical_basis": [
        "PBR 2.5배 밸류에이션 저점",
        "52주 저점 부근"
      ]
    }
  ],
  
  "stop_loss_suggestion": {
    "price": 1249000,
    "pct": -20.0,
    "basis": "사용자 변동성 감내 -20% 적용"
  },
  
  "take_profit_suggestion": {
    "tier_1": 1953000,  // +25%
    "final": 2342000    // +50%
  },
  
  "disclaimer": "📌 AI 참고 수치는 투자 권유가 아닌 분석 결과입니다..."
}
```

### 사용량 제한

```
Pro: 월 5회 (종목당)
Premium: 무제한
```

---

## 📊 GET `/api/ai/usage`

### 설명
현재 월 사용량 조회

### Response

```json
{
  "user_uid": "firebase_uid",
  "plan": "free",
  "month": "2026-04",
  
  "usage": {
    "analyses": {
      "used": 18,
      "limit": 20,
      "remaining": 2
    },
    "validations": {
      "used": 7,
      "limit": 10,
      "remaining": 3
    },
    "ai_recommendations": {
      "used": 3,
      "limit": 5,
      "remaining": 2
    },
    "ai_entry_suggestions": {
      "used": 0,
      "limit": 0,
      "remaining": 0  // Free에는 없음
    }
  },
  
  "reset_at": "2026-05-01T00:00:00+09:00",
  
  "upgrade_url": "https://axis.kr/pricing"
}
```

---

## 🛠 구현 예시 (FastAPI)

### `api/routes/ai.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from typing import Optional, AsyncGenerator

from agents.graph import create_analysis_graph
from api.middleware.firebase_auth import get_current_user
from utils.usage_tracker import check_quota, increment_usage

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    ticker: str
    query: Optional[str] = None
    persona: str = "blackrock"
    use_cache: bool = True
    stream: bool = True


@router.post("/analyze")
async def analyze(
    request: AnalyzeRequest,
    uid: str = Depends(get_current_user)
):
    """4개 에이전트 종목 분석"""
    
    # 1. 한도 체크
    quota_ok, quota_info = await check_quota(uid, "analyses")
    if not quota_ok:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "QUOTA_EXCEEDED",
                "message": "월 분석 한도 초과",
                "usage": quota_info,
                "upgrade_url": "/pricing"
            }
        )
    
    # 2. LangGraph 실행
    graph = create_analysis_graph()
    
    if request.stream:
        # SSE 스트리밍
        return StreamingResponse(
            stream_analysis(graph, request, uid),
            media_type="text/event-stream"
        )
    else:
        # 전체 결과 한 번에
        result = await graph.ainvoke({
            "ticker": request.ticker,
            "query": request.query,
            "persona": request.persona,
            "user_uid": uid,
        })
        
        # 사용량 카운트
        await increment_usage(uid, "analyses")
        
        return result


async def stream_analysis(
    graph, request: AnalyzeRequest, uid: str
) -> AsyncGenerator[str, None]:
    """SSE 스트림 생성"""
    
    yield f"event: start\ndata: {json.dumps({'analysis_id': 'xxx'})}\n\n"
    
    async for event in graph.astream({...}):
        agent_name = event["agent"]
        agent_result = event["result"]
        
        yield f"event: {agent_name}_complete\n"
        yield f"data: {json.dumps(agent_result, ensure_ascii=False)}\n\n"
    
    yield f"event: complete\ndata: {{\"saved\": true}}\n\n"


@router.post("/validate/{analysis_id}")
async def validate(
    analysis_id: str,
    uid: str = Depends(get_current_user)
):
    """분석 결과 재검증"""
    
    # 한도 체크
    quota_ok, _ = await check_quota(uid, "validations")
    if not quota_ok:
        raise HTTPException(402, "Validation quota exceeded")
    
    # 원본 분석 로드
    analysis = await load_analysis(uid, analysis_id)
    
    # Validator만 재실행
    from agents.validator import ValidatorAgent
    validator = ValidatorAgent()
    result = await validator.run(...)
    
    await increment_usage(uid, "validations")
    
    return result


@router.get("/personas")
async def get_personas(uid: str = Depends(get_current_user)):
    """페르소나 목록"""
    user = await get_user(uid)
    
    return {
        "personas": [
            {
                "id": "blackrock",
                "name": "BlackRock 애널리스트",
                "available_to_free": True,
            },
            # ...
        ],
        "user_plan": user.plan,
    }
```

---

## 🔐 인증 미들웨어

### `api/middleware/firebase_auth.py`

```python
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, Request, Depends
from typing import Optional


# 초기화
cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)


async def verify_firebase_token(request: Request) -> dict:
    """Authorization 헤더에서 Firebase 토큰 검증"""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    
    token = auth_header.split(" ")[1]
    
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except auth.InvalidIdTokenError:
        raise HTTPException(401, "Invalid token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(401, "Token expired")


async def get_current_user(request: Request) -> str:
    """현재 사용자의 UID 반환"""
    decoded = await verify_firebase_token(request)
    return decoded["uid"]


# 사용 예
@router.get("/protected")
async def protected_endpoint(uid: str = Depends(get_current_user)):
    return {"uid": uid}
```

---

## 📊 사용량 추적

### `utils/usage_tracker.py`

```python
from datetime import datetime
from screener.db.repository import get_firestore_client


PLAN_LIMITS = {
    "free": {
        "analyses": 20,
        "validations": 10,
        "ai_recommendations": 5,
        "ai_entry_suggestions": 0,
    },
    "pro": {
        "analyses": -1,  # 무제한
        "validations": -1,
        "ai_recommendations": -1,
        "ai_entry_suggestions": 5,
    },
    "premium": {
        "analyses": -1,
        "validations": -1,
        "ai_recommendations": -1,
        "ai_entry_suggestions": -1,
    },
}


async def check_quota(uid: str, usage_type: str) -> tuple[bool, dict]:
    """한도 체크"""
    db = get_firestore_client()
    
    # 사용자 플랜
    user_doc = await db.collection("users").document(uid).get()
    user_data = user_doc.to_dict()
    plan = user_data.get("plan", "free")
    
    # 이번 달 사용량
    month = datetime.now().strftime("%Y-%m")
    usage_doc = await db.collection("users").document(uid)\
        .collection("ai_usage").document(month).get()
    
    used = 0
    if usage_doc.exists:
        used = usage_doc.to_dict().get(f"{usage_type}_count", 0)
    
    # 한도 비교
    limit = PLAN_LIMITS[plan][usage_type]
    if limit == -1:  # 무제한
        return True, {"used": used, "limit": -1, "remaining": -1}
    
    if used >= limit:
        return False, {"used": used, "limit": limit, "remaining": 0}
    
    return True, {"used": used, "limit": limit, "remaining": limit - used}


async def increment_usage(uid: str, usage_type: str):
    """사용량 증가"""
    db = get_firestore_client()
    month = datetime.now().strftime("%Y-%m")
    
    await db.collection("users").document(uid)\
        .collection("ai_usage").document(month).set(
            {f"{usage_type}_count": firestore.Increment(1)},
            merge=True
        )
```

---

**다음 문서**:
- `docs/api/watchlist.md`
- `docs/api/screener.md`
- `docs/frontend/pages.md`
