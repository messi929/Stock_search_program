# Watchlist API 엔드포인트 스펙

> **Base URL**: `https://stock-screener-119320994983.asia-northeast3.run.app`  
> **인증**: Firebase JWT Bearer Token

---

## 📋 엔드포인트 목록

| Method | Path | 설명 | Plan |
|--------|------|------|------|
| GET | `/api/watchlist` | 관심 종목 전체 조회 | All |
| GET | `/api/watchlist/{ticker}` | 특정 종목 상세 | All |
| POST | `/api/watchlist` | 관심 종목 추가 | All |
| PATCH | `/api/watchlist/{ticker}` | 진입선/메모 수정 | All |
| DELETE | `/api/watchlist/{ticker}` | 관심 종목 삭제 | All |
| POST | `/api/watchlist/{ticker}/alert` | 알림 설정 | All |
| GET | `/api/watchlist/themes` | 큐레이션 테마 9개 | All |

---

## 📥 GET `/api/watchlist`

### 설명
사용자의 관심 종목 전체 목록 + 현재가 + 진입선까지 거리

### Request

```
GET /api/watchlist
Authorization: Bearer {token}

Query Params:
- sort: "added" | "ticker" | "change_pct" | "distance_to_entry" (기본: "added")
- order: "asc" | "desc" (기본: "desc")
- tag: 특정 태그로 필터링 (옵션)
```

### Response

```json
{
  "user_plan": "free",
  "limit": 5,
  "used": 3,
  "remaining": 2,
  
  "items": [
    {
      "ticker": "207940",
      "name": "삼성바이오로직스",
      "sector": "바이오",
      
      "current_price": 1561000,
      "change_pct": -1.70,
      "previous_close": 1588000,
      
      "entry_tier_1": 1405000,
      "entry_tier_2": 1327000,
      "entry_tier_3": 1249000,
      "distance_to_entry_1_pct": -10.0,
      
      "stop_loss": 1249000,
      "take_profit_1": 1953000,
      
      "alert_enabled": true,
      "alert_channels": ["kakao"],
      
      "added_at": "2026-04-22T10:00:00Z",
      "added_via": "ai_recommend",
      "user_memo": "1Q 실적 좋았음",
      "user_tags": ["장기", "바이오"],
      
      "last_alert_triggered": null,
      
      "ai_status_summary": "현재가는 1차 진입선 위 +11% 위치. 4월 랠리 소외 종목."
    }
  ],
  
  "summary": {
    "total_value": 0,
    "average_change_pct": -0.5,
    "near_entry_count": 1
  }
}
```

---

## 🔍 GET `/api/watchlist/{ticker}`

### 설명
특정 관심 종목의 상세 정보 (현재가 + 차트 + 알림 이력)

### Response

```json
{
  "ticker": "207940",
  "name": "삼성바이오로직스",
  
  "watchlist_info": {
    "added_at": "2026-04-22T10:00:00Z",
    "added_via": "ai_recommend",
    "added_context": "AI에게 '바이오 우량주' 추천받음",
    "user_memo": "...",
    "user_tags": [...]
  },
  
  "entry_points": {
    "tier_1": 1405000,
    "tier_2": 1327000,
    "tier_3": 1249000,
    "entry_basis": ["20일 이평선 부근", "3개월 저점"],
    "entry_source": "ai_suggested"
  },
  
  "exit_points": {
    "stop_loss": 1249000,
    "take_profit_1": 1953000,
    "take_profit_final": 2342000
  },
  
  "alert_settings": {
    "enabled": true,
    "channels": ["kakao"],
    "trigger_history": [
      {
        "trigger": "entry_tier_1",
        "at": "2026-04-25T14:00:00Z",
        "price": 1405000
      }
    ]
  },
  
  "current_data": {
    "current_price": 1561000,
    "change_pct": -1.70,
    "volume": 234567,
    "market_cap": 103000000000000,
    "per": 45.2,
    "buy_score": 73.5,
    "rsi": 42.5,
    "vs_high_52w": -12.3
  },
  
  "recent_analyses": [
    {
      "analysis_id": "uuid-xxx",
      "persona": "blackrock",
      "created_at": "2026-04-22T10:00:00Z",
      "validation_status": "PASS",
      "summary_preview": "..."
    }
  ]
}
```

---

## ➕ POST `/api/watchlist`

### 설명
관심 종목 추가. Free 5개 / Pro 30개 제한.

### Request

```json
{
  "ticker": "207940",
  "added_via": "search",
  "added_context": "직접 검색",
  
  "entry_tier_1": 1405000,
  "entry_tier_2": 1327000,
  "entry_tier_3": 1249000,
  "entry_source": "manual",
  "entry_basis": ["사용자 직접 설정"],
  
  "stop_loss": 1249000,
  "take_profit_1": 1953000,
  
  "alert_enabled": true,
  "alert_channels": ["kakao"],
  
  "user_memo": "장기 보유 후보",
  "user_tags": ["장기", "바이오"]
}
```

### Response (201 Created)

```json
{
  "ticker": "207940",
  "name": "삼성바이오로직스",
  "added_at": "2026-04-25T15:30:00Z",
  
  "watchlist_info": {...},
  
  "user_quota": {
    "used": 4,
    "limit": 5,
    "remaining": 1
  }
}
```

### Error Codes

| Code | Status | 의미 |
|------|--------|------|
| 400 | INVALID_TICKER | 종목 코드 형식 오류 |
| 402 | QUOTA_EXCEEDED | 관심 종목 한도 초과 |
| 404 | TICKER_NOT_FOUND | 존재하지 않는 종목 |
| 409 | ALREADY_EXISTS | 이미 관심 종목에 있음 |

---

## 🔧 PATCH `/api/watchlist/{ticker}`

### 설명
진입선, 손절/익절, 메모, 태그 수정

### Request

```json
{
  "entry_tier_1": 1400000,  // 변경
  "stop_loss": 1200000,
  "user_memo": "1Q 실적 발표 후 재검토",
  "user_tags": ["장기", "바이오", "실적주"]
}
```

### Response

```json
{
  "ticker": "207940",
  "updated_fields": ["entry_tier_1", "stop_loss", "user_memo", "user_tags"],
  "updated_at": "2026-04-25T16:00:00Z"
}
```

---

## 🗑 DELETE `/api/watchlist/{ticker}`

### Request

```
DELETE /api/watchlist/207940
Authorization: Bearer {token}
```

### Response (204 No Content)

```
{}
```

---

## 🔔 POST `/api/watchlist/{ticker}/alert`

### 설명
알림 설정 변경

### Request

```json
{
  "enabled": true,
  "channels": ["kakao", "email"],
  "triggers": [
    {
      "type": "price_below",
      "threshold": 1405000
    },
    {
      "type": "rsi_below",
      "threshold": 30
    }
  ]
}
```

### Response

```json
{
  "ticker": "207940",
  "alert_settings": {...},
  "updated_at": "2026-04-25T16:00:00Z"
}
```

---

## 🎨 GET `/api/watchlist/themes` (큐레이션 9개)

### 설명
관심 종목 추가 화면에서 보여줄 큐레이션 테마

### Response

```json
{
  "themes": [
    {
      "id": "ai_semi",
      "name": "AI/반도체",
      "icon": "🤖",
      "description": "생성AI 시대의 인프라 수혜주",
      "tags": ["반도체", "데이터센터", "전력인프라"],
      "stocks_preview": [
        {"ticker": "000660", "name": "SK하이닉스"},
        {"ticker": "010120", "name": "LS일렉트릭"},
        {"ticker": "007660", "name": "이수페타시스"}
      ],
      "stocks_count": 24
    },
    {
      "id": "battery_secondary",
      "name": "2차전지/배터리",
      "icon": "🔋",
      "description": "전기차·ESS 핵심 소재 및 셀 제조",
      "tags": ["배터리", "양극재", "음극재"],
      "stocks_preview": [
        {"ticker": "373220", "name": "LG에너지솔루션"},
        {"ticker": "006400", "name": "삼성SDI"},
        {"ticker": "003670", "name": "포스코퓨처엠"}
      ],
      "stocks_count": 18
    },
    {
      "id": "biologics",
      "name": "바이오/제약",
      "icon": "💊",
      "description": "글로벌 CDMO·신약·바이오시밀러",
      "tags": ["CDMO", "바이오시밀러", "신약"],
      "stocks_count": 32
    },
    {
      "id": "robotics_physical_ai",
      "name": "로봇/피지컬AI",
      "icon": "🦾",
      "description": "휴머노이드·산업용 로봇 모멘텀",
      "tags": ["로봇", "휴머노이드", "감속기"],
      "stocks_count": 15
    },
    {
      "id": "nuclear_power",
      "name": "원전/전력",
      "icon": "⚡",
      "description": "AI 데이터센터 전력 수요 폭증 수혜",
      "tags": ["원전", "전력", "변압기"],
      "stocks_count": 12
    },
    {
      "id": "shipbuilding_defense",
      "name": "조선/방산",
      "icon": "🚢",
      "description": "K-방산 및 LNG선 슈퍼사이클",
      "tags": ["조선", "방산", "LNG"],
      "stocks_count": 16
    },
    {
      "id": "k_food_beauty",
      "name": "K-푸드/뷰티",
      "icon": "🍜",
      "description": "글로벌 한류 콘텐츠 + 소비재",
      "tags": ["식품", "화장품", "K컬처"],
      "stocks_count": 21
    },
    {
      "id": "finance_value_up",
      "name": "금융/밸류업",
      "icon": "💰",
      "description": "정부 밸류업 정책 + 주주환원",
      "tags": ["은행", "보험", "밸류업"],
      "stocks_count": 14
    },
    {
      "id": "reit_dividend",
      "name": "리츠/배당주",
      "icon": "🏢",
      "description": "안정적 배당 + 인플레이션 헤지",
      "tags": ["리츠", "배당", "고배당"],
      "stocks_count": 19
    }
  ]
}
```

### 테마별 종목 조회

```
GET /api/watchlist/themes/{theme_id}/stocks?limit=20

Response:
{
  "theme": {...},
  "stocks": [
    {
      "ticker": "010120",
      "name": "LS일렉트릭",
      "current_price": 78500,
      "change_pct": 1.2,
      "buy_score": 72,
      "buy_grade": "매수"
    }
  ]
}
```

---

## 🛠 구현 예시

### `api/routes/watchlist.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from api.middleware.firebase_auth import get_current_user
from screener.db.repository import get_firestore_client


router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

PLAN_WATCHLIST_LIMITS = {
    "free": 5,
    "pro": 30,
    "premium": 30,
}


class WatchlistItem(BaseModel):
    ticker: str
    added_via: str = "manual"
    added_context: Optional[str] = None
    
    entry_tier_1: Optional[int] = None
    entry_tier_2: Optional[int] = None
    entry_tier_3: Optional[int] = None
    entry_source: str = "manual"
    
    stop_loss: Optional[int] = None
    take_profit_1: Optional[int] = None
    
    alert_enabled: bool = True
    alert_channels: List[str] = []
    
    user_memo: Optional[str] = None
    user_tags: List[str] = []


@router.get("")
async def list_watchlist(
    uid: str = Depends(get_current_user),
    sort: str = "added",
    order: str = "desc",
    tag: Optional[str] = None
):
    """관심 종목 목록"""
    db = get_firestore_client()
    
    # 사용자 플랜
    user_doc = await db.collection("users").document(uid).get()
    plan = user_doc.to_dict().get("plan", "free")
    limit = PLAN_WATCHLIST_LIMITS[plan]
    
    # 관심 종목 조회
    watchlist_ref = db.collection("users").document(uid).collection("watchlist")
    docs = await watchlist_ref.get()
    items = []
    
    for doc in docs:
        item = doc.to_dict()
        
        # 현재가 추가 (stocks 컬렉션에서)
        stock_doc = await db.collection("stocks").document("kr").get()
        stock_data = next(
            (s for s in stock_doc.to_dict()["data"] if s["ticker"] == item["ticker"]),
            None
        )
        
        if stock_data:
            item["current_price"] = stock_data["close"]
            item["change_pct"] = stock_data["change_pct"]
            
            if item.get("entry_tier_1"):
                distance = (stock_data["close"] - item["entry_tier_1"]) / item["entry_tier_1"] * 100
                item["distance_to_entry_1_pct"] = round(distance, 2)
        
        items.append(item)
    
    # 정렬
    if sort == "distance_to_entry":
        items.sort(
            key=lambda x: x.get("distance_to_entry_1_pct", 999),
            reverse=(order == "desc")
        )
    
    return {
        "user_plan": plan,
        "limit": limit,
        "used": len(items),
        "remaining": limit - len(items),
        "items": items,
    }


@router.post("", status_code=201)
async def add_watchlist(
    item: WatchlistItem,
    uid: str = Depends(get_current_user)
):
    """관심 종목 추가"""
    db = get_firestore_client()
    
    # 한도 체크
    user_doc = await db.collection("users").document(uid).get()
    plan = user_doc.to_dict().get("plan", "free")
    limit = PLAN_WATCHLIST_LIMITS[plan]
    
    watchlist_ref = db.collection("users").document(uid).collection("watchlist")
    current_count = (await watchlist_ref.get()).__len__()
    
    if current_count >= limit:
        raise HTTPException(402, {
            "code": "QUOTA_EXCEEDED",
            "message": f"관심 종목 한도 ({limit}개) 초과",
            "upgrade_url": "/pricing"
        })
    
    # 중복 체크
    existing = await watchlist_ref.document(item.ticker).get()
    if existing.exists:
        raise HTTPException(409, "이미 관심 종목에 있습니다")
    
    # 종목 존재 확인
    stock_doc = await db.collection("stocks").document("kr").get()
    stock_data = next(
        (s for s in stock_doc.to_dict()["data"] if s["ticker"] == item.ticker),
        None
    )
    if not stock_data:
        raise HTTPException(404, "존재하지 않는 종목")
    
    # 저장
    data = item.model_dump()
    data["added_at"] = datetime.now().isoformat()
    data["name"] = stock_data["name"]
    
    await watchlist_ref.document(item.ticker).set(data)
    
    return {
        "ticker": item.ticker,
        "name": stock_data["name"],
        "added_at": data["added_at"],
        "user_quota": {
            "used": current_count + 1,
            "limit": limit,
            "remaining": limit - current_count - 1
        }
    }
```

---

**다음 문서**: `docs/api/screener.md`
