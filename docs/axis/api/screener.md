# Screener API 엔드포인트 스펙

> **Base URL**: `https://stock-screener-119320994983.asia-northeast3.run.app`  
> **인증**: Firebase JWT Bearer Token

---

## 📋 엔드포인트 목록

| Method | Path | 설명 | Plan |
|--------|------|------|------|
| GET | `/api/screener/smart-lists` | 스마트 리스트 카테고리 | All |
| GET | `/api/screener/smart-lists/{category_id}` | 카테고리 종목 | All |
| POST | `/api/screener/custom` | 커스텀 스크리너 실행 | Pro |
| GET | `/api/screener/saved` | 저장된 스크리너 | Pro |
| POST | `/api/screener/save` | 스크리너 저장 | Pro |
| DELETE | `/api/screener/saved/{id}` | 스크리너 삭제 | Pro |

---

## 📊 GET `/api/screener/smart-lists`

### 설명
기존 `screener/core/screener.py`의 CATEGORIES를 활용한 스마트 리스트

### Response

```json
{
  "categories": [
    {
      "id": "buy_signals",
      "name": "매수 시그널",
      "icon": "📈",
      "description": "Buy Score, 수급, 기술적 종합",
      "lists": [
        {
          "id": "buy_score_top",
          "name": "Buy Score 상위 30",
          "description": "buy_score >= 70",
          "match_count": 28,
          "preview_tickers": ["207940", "000660", "005935"]
        },
        {
          "id": "top_tier",
          "name": "상위 구간",
          "description": "buy_grade == '상위'",
          "match_count": 12
        },
        {
          "id": "dual_buy",
          "name": "외국인+기관 동시 매수",
          "description": "5일 이상 동시 순매수",
          "match_count": 18
        },
        {
          "id": "pre_surge",
          "name": "급등 전 시그널",
          "description": "RSI 회복 + 수급 유입",
          "match_count": 7
        }
      ]
    },
    {
      "id": "value",
      "name": "가치주",
      "icon": "💎",
      "description": "PER, PBR 저평가",
      "lists": [
        {
          "id": "low_per_high_roe",
          "name": "저PER 고ROE",
          "description": "PER<10 & ROE>15%"
        },
        {
          "id": "low_pbr",
          "name": "저PBR (1배 미만)",
          "description": "PBR < 1.0"
        },
        {
          "id": "dividend_aristocrat",
          "name": "고배당 안정",
          "description": "배당 4%+ & 5년 연속"
        }
      ]
    },
    {
      "id": "momentum",
      "name": "모멘텀",
      "icon": "🚀",
      "lists": [
        {
          "id": "golden_cross",
          "name": "골든크로스",
          "description": "5일이 20일 상향 돌파"
        },
        {
          "id": "near_high_52w",
          "name": "52주 신고가 임박",
          "description": "최고가 -5% 이내"
        },
        {
          "id": "rsi_recovery",
          "name": "과매도 → 회복",
          "description": "RSI 30→40 회복"
        }
      ]
    },
    {
      "id": "contrarian",
      "name": "역발상",
      "icon": "🔄",
      "lists": [
        {
          "id": "near_low_52w",
          "name": "52주 신저가 부근",
          "description": "최저가 +10% 이내"
        },
        {
          "id": "high_per_growth",
          "name": "고PER 고성장",
          "description": "PER>30 & 매출 성장 30%+"
        },
        {
          "id": "rally_outsider",
          "name": "랠리 소외주",
          "description": "지수 상승 중 -10%+ 부진"
        }
      ]
    },
    {
      "id": "size",
      "name": "시총별",
      "icon": "📐",
      "lists": [
        {
          "id": "large_cap",
          "name": "대형주 (시총 10조+)",
          "description": "안정 우량주"
        },
        {
          "id": "mid_cap",
          "name": "중형주 (1-10조)",
          "description": "성장 후보"
        },
        {
          "id": "small_cap",
          "name": "소형주 (5천억-1조)",
          "description": "고변동성"
        },
        {
          "id": "micro_cap",
          "name": "초소형주 (5천억 미만)",
          "description": "10배 후보 (고위험)"
        }
      ]
    },
    {
      "id": "sector",
      "name": "섹터별 강세",
      "icon": "🎯",
      "description": "외국인/기관 매수 상위 섹터",
      "lists": [
        {
          "id": "sector_semiconductor",
          "name": "반도체 강세 종목",
          "description": "외국인 5일 이상 순매수"
        }
      ]
    }
  ]
}
```

**6 카테고리 × 4-5 리스트 = 24-30개 스마트 리스트**

---

## 📈 GET `/api/screener/smart-lists/{category_id}/{list_id}`

### 설명
특정 스마트 리스트의 종목 결과

### Request

```
GET /api/screener/smart-lists/buy_signals/buy_score_top?page=1&size=30
```

### Response

```json
{
  "list_id": "buy_score_top",
  "name": "Buy Score 상위 30",
  "description": "buy_score >= 70",
  "filter_criteria": {
    "buy_score": {"min": 70}
  },
  
  "total_match": 28,
  "page": 1,
  "page_size": 30,
  
  "stocks": [
    {
      "ticker": "207940",
      "name": "삼성바이오로직스",
      "market": "KOSPI",
      "sector": "바이오",
      "current_price": 1561000,
      "change_pct": -1.70,
      "market_cap_kr": "103.0조",
      
      "buy_score": 88.5,
      "buy_grade": "상위",
      
      "per": 45.2,
      "pbr": 5.8,
      "roe": 12.5,
      
      "rsi": 42.5,
      "vs_high_52w": -12.3,
      
      "foreign_consecutive": 3,
      "dual_buy": true,
      
      "ai_summary": "1Q 실적 +41% 서프라이즈. 4월 랠리 소외 종목."
    }
  ],
  
  "metadata": {
    "data_updated_at": "2026-04-25T16:00:00+09:00",
    "ai_summary_enabled": false
  }
}
```

---

## 🎛 POST `/api/screener/custom` (Pro)

### 설명
사용자가 직접 조건을 정의해서 스크리닝

### Request

```json
{
  "name": "내 가치주 전략",
  "conditions": {
    "fundamental": {
      "per": {"min": 5, "max": 15},
      "pbr": {"min": 0.5, "max": 2.0},
      "roe": {"min": 10},
      "div_yield": {"min": 3}
    },
    "technical": {
      "rsi": {"min": 30, "max": 70},
      "vs_high_52w": {"max": -10},
      "above_ma20": true
    },
    "supply_demand": {
      "foreign_consecutive": {"min": 3},
      "dual_buy": true
    },
    "sectors": ["금융", "유틸리티"],
    "markets": ["KOSPI"],
    "market_cap": {
      "min": 1000000000000,
      "max": 10000000000000
    },
    "exclude_tickers": ["005930"]
  },
  "save_for_later": false,
  "include_ai_summary": false
}
```

### Response

```json
{
  "match_count": 12,
  "stocks": [...],
  
  "explanation": "조건에 맞는 종목 12개를 찾았습니다.",
  
  "metadata": {
    "elapsed_ms": 145,
    "data_updated_at": "..."
  }
}
```

---

## 💾 POST `/api/screener/save` (Pro)

### 설명
커스텀 스크리너를 저장 (이후 알림 가능)

### Request

```json
{
  "name": "내 가치주 전략",
  "description": "PER 낮고 배당 좋은 우량주",
  "conditions": {...},
  "alert_enabled": true,
  "alert_channels": ["kakao"],
  "alert_frequency": "daily"
}
```

### Response

```json
{
  "screener_id": "uuid-xxx",
  "created_at": "2026-04-25T16:00:00Z"
}
```

---

## 🛠 구현 예시

### `api/routes/screener.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import pandas as pd

from api.middleware.firebase_auth import get_current_user
from screener.db.repository import load_stocks
from screener.core.screener import CATEGORIES  # 기존 자산
from screener.core.metrics import compute_buy_score


router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/smart-lists")
async def get_smart_lists(uid: str = Depends(get_current_user)):
    """스마트 리스트 카테고리"""
    
    # 기존 CATEGORIES 활용 + 신규 메타데이터
    categories = []
    
    # buy_signals 카테고리
    kr_stocks = load_stocks("kr")
    
    categories.append({
        "id": "buy_signals",
        "name": "매수 시그널",
        "icon": "📈",
        "lists": [
            {
                "id": "buy_score_top",
                "name": "Buy Score 상위 30",
                "match_count": int((kr_stocks["buy_score"] >= 70).sum()),
            },
            {
                "id": "dual_buy",
                "name": "외국인+기관 동시 매수",
                "match_count": int(kr_stocks["dual_buy"].sum()),
            },
            # ...
        ]
    })
    
    # 다른 카테고리들도 동적으로 생성
    # ...
    
    return {"categories": categories}


@router.get("/smart-lists/{category_id}/{list_id}")
async def get_smart_list_stocks(
    category_id: str,
    list_id: str,
    uid: str = Depends(get_current_user),
    page: int = 1,
    size: int = 30,
):
    """스마트 리스트의 종목 결과"""
    
    kr_stocks = load_stocks("kr")
    
    # list_id별 필터링
    if list_id == "buy_score_top":
        filtered = kr_stocks[kr_stocks["buy_score"] >= 70]\
            .sort_values("buy_score", ascending=False)
    elif list_id == "dual_buy":
        filtered = kr_stocks[kr_stocks["dual_buy"] == True]
    elif list_id == "low_per_high_roe":
        filtered = kr_stocks[
            (kr_stocks["per"] < 10) & (kr_stocks["roe"] > 15)
        ]
    # ...
    
    # 페이지네이션
    start = (page - 1) * size
    end = start + size
    page_stocks = filtered.iloc[start:end].to_dict("records")
    
    return {
        "list_id": list_id,
        "total_match": len(filtered),
        "page": page,
        "page_size": size,
        "stocks": page_stocks,
    }


class CustomScreenRequest(BaseModel):
    conditions: Dict
    save_for_later: bool = False
    name: Optional[str] = None


@router.post("/custom")
async def custom_screen(
    request: CustomScreenRequest,
    uid: str = Depends(get_current_user),
):
    """커스텀 스크리닝 (Pro 전용)"""
    
    # Pro 권한 체크
    user = await get_user(uid)
    if user.plan == "free":
        raise HTTPException(403, "Pro 전용 기능입니다")
    
    kr_stocks = load_stocks("kr")
    
    # 조건 적용
    filtered = kr_stocks.copy()
    
    fundamental = request.conditions.get("fundamental", {})
    if "per" in fundamental:
        per_cond = fundamental["per"]
        if "min" in per_cond:
            filtered = filtered[filtered["per"] >= per_cond["min"]]
        if "max" in per_cond:
            filtered = filtered[filtered["per"] <= per_cond["max"]]
    
    # ... 다른 조건들
    
    return {
        "match_count": len(filtered),
        "stocks": filtered.to_dict("records"),
    }
```

---

**다음 문서**: `docs/frontend/pages.md`
