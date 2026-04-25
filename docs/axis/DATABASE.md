# Axis Database Schema (Firestore)

> **목적**: 모든 데이터 저장 위치와 구조를 명시  
> **형식**: Firestore document-based (NoSQL)

---

## 📊 컬렉션 개요

```
firestore/
├── 🔄 기존 (유지)
│   ├── stocks/                    # 종목 마스터
│   ├── themes/                    # 테마 분류
│   ├── history/                   # OHLCV 히스토리
│   ├── sync_metadata/             # 수집 상태
│   ├── supply_history/            # 수급 이력
│   └── score_history/             # buy_score 일별
│
└── 🆕 신규 (추가)
    ├── users/                     # 사용자 데이터
    │   └── {uid}/
    │       ├── profile            # 단일 문서
    │       ├── watchlist/         # 서브컬렉션
    │       ├── analyses/          # 서브컬렉션
    │       ├── ai_usage/          # 서브컬렉션
    │       ├── custom_screeners/  # 서브컬렉션
    │       └── alerts/            # 서브컬렉션
    │
    └── ai_recommendations/        # 익명 통계
```

---

## 🔄 기존 컬렉션 (참고용)

### `stocks/{market}` (kr, us, etf)
```python
{
  "ticker": "207940",
  "name": "삼성바이오로직스",
  "name_en": "Samsung Biologics",
  "market": "KOSPI",
  "sector": "바이오",
  "industry": "제약/바이오",
  
  # 가격
  "close": 1561000,
  "change_pct": -1.70,
  "volume": 234567,
  "market_cap": 103000000000000,  # 103조
  
  # 펀더멘털 (네이버 크롤링)
  "per": 45.2,
  "pbr": 5.8,
  "roe": 12.5,
  "div_yield": 0.4,
  
  # 기술 지표 (계산됨)
  "ma_5": 1565000,
  "ma_20": 1620000,
  "ma_60": 1680000,
  "rsi": 42.5,
  "vs_high_52w": -12.3,
  "vs_low_52w": 18.5,
  
  # 시그널 (계산됨)
  "buy_score": 73.5,
  "buy_grade": "매수",
  "is_pre_surge": 0,
  "pre_surge_score": 2,
  "golden_cross": 1,
  
  # 수급 (계산됨)
  "foreign_consecutive": 3,
  "dual_buy": True,
  "target_upside": 15.2,
  
  # 메타
  "updated_at": "2026-04-22T16:10:00+09:00"
}
```

이미 collector.py가 매일 4회 업데이트.

---

## 🆕 신규 컬렉션 (구현 필요)

### `users/{uid}` (메인 문서)

```python
{
  "uid": "firebase_user_id_xxx",  # Firebase Auth UID
  "email": "user@example.com",
  "nickname": "투자자_민준",
  "phone": "+821012345678",  # 카톡 알림용 (옵션)
  
  # 가입 정보
  "created_at": "2026-04-25T10:00:00Z",
  "updated_at": "2026-04-25T10:00:00Z",
  "auth_provider": "kakao",  # "kakao", "google", "email"
  
  # 플랜
  "plan": "free",  # "free", "pro", "premium"
  "plan_started_at": null,
  "plan_expires_at": null,
  
  # 프로필 (온보딩)
  "investing_experience": "1-5y",  # "beginner", "1-5y", "5y+"
  "investment_amount_range": "30M-100M",  # 원
  "holding_period_preference": "1-2y",  # "1m", "6m", "1-2y", "3y+"
  "volatility_tolerance": "20",  # "10", "20", "30"
  "interested_sectors": ["반도체", "바이오", "2차전지"],
  
  # 사용자 원칙 (자유 입력)
  "investment_principles": [
    "이미 오른 것은 피한다",
    "기술적 해자가 있는 종목 선호",
    "분할 매수"
  ],
  
  # 설정
  "preferred_persona": "blackrock",  # "blackrock", "ark", "graham"
  "notification_channels": ["kakao", "email"],
  "language": "ko",
  
  # 통계
  "total_analyses_count": 12,
  "total_validations_count": 8,
  "last_active_at": "2026-04-25T15:30:00Z"
}
```

### `users/{uid}/watchlist/{ticker}`

```python
{
  "ticker": "207940",
  "name": "삼성바이오로직스",
  "added_at": "2026-04-22T10:00:00Z",
  "added_via": "ai_recommend",  # "search", "ai_recommend", "theme", "screener"
  "added_context": "AI에게 '바이오 우량주' 추천받음",
  
  # 진입선
  "entry_tier_1": 1405000,  # -10%
  "entry_tier_2": 1327000,  # -15%
  "entry_tier_3": 1249000,  # -20%
  "entry_source": "ai_suggested",  # "manual", "ai_suggested"
  "entry_basis": [
    "20일 이평선 부근",
    "3개월 저점"
  ],
  "entry_set_at": "2026-04-22T10:05:00Z",
  
  # 손절/익절
  "stop_loss": 1249000,  # -20%
  "take_profit_1": 1953000,  # +25%
  "take_profit_final": 2342000,  # +50%
  
  # 알림
  "alert_enabled": True,
  "alert_channels": ["kakao"],
  "alert_triggered_history": [
    # 도달 이력
    # {"trigger": "entry_tier_1", "at": "...", "price": 1405000}
  ],
  
  # 사용자 메모
  "user_memo": "1Q 실적 +41% 좋았음. 4월 랠리 소외주.",
  "user_tags": ["장기", "관찰중", "바이오"],
  
  # 메타
  "updated_at": "2026-04-25T10:00:00Z"
}
```

### `users/{uid}/analyses/{analysis_id}`

```python
{
  "analysis_id": "uuid-xxx",
  "user_uid": "firebase_uid",
  "ticker": "207940",
  "query": "삼성바이오로직스 어때?",
  "persona": "blackrock",
  
  # 각 에이전트 결과 (JSON)
  "research_output": {...},
  "analyst_output": {...},
  "validator_output": {...},
  "strategist_output": {...},
  
  # 메타
  "total_tokens_used": 12345,
  "total_cost_krw": 215,
  "elapsed_seconds": 8.5,
  "validation_status": "PASS",  # "PASS", "WARN", "FAIL"
  
  # 사용자 행동
  "is_validated_again": False,  # 재검증 여부
  "is_persona_switched": False,
  "saved_to_watchlist": True,
  
  # 시점
  "created_at": "2026-04-25T15:30:00Z",
  "expires_at": "2026-07-25T15:30:00Z"  # 90일 보관
}
```

**과거 분석 추적 기능에 사용** — 3개월 후 자동 삭제

### `users/{uid}/ai_usage/{YYYY-MM}`

```python
{
  "month": "2026-04",
  "user_uid": "firebase_uid",
  
  # 사용량 카운터
  "analyses_count": 18,  # Free: 20회 제한
  "validations_count": 7,  # Free: 10회 제한
  "ai_recommendations_count": 3,  # AI 자연어 추천
  "ai_entry_suggestions_count": 2,  # AI 참고 진입선 (Pro: 5회)
  "persona_switches_count": 12,  # Free: 5회 제한
  
  # 비용
  "total_tokens_used": 234567,
  "total_cost_krw": 4500,
  
  # 페르소나별 사용
  "persona_blackrock_count": 15,
  "persona_ark_count": 3,
  "persona_graham_count": 0,
  
  # 메타
  "first_request_at": "2026-04-01T09:00:00Z",
  "last_request_at": "2026-04-25T15:30:00Z"
}
```

**매월 자동 생성, Free Tier 한도 체크에 사용**

### `users/{uid}/custom_screeners/{screener_id}`

```python
{
  "screener_id": "uuid-xxx",
  "name": "내 배당주 전략",
  "description": "PER 낮고 배당 좋은 우량주",
  
  # 조건 (JSONB)
  "conditions": {
    "per": {"min": 5, "max": 15},
    "pbr": {"min": 0.5, "max": 2.0},
    "roe": {"min": 10, "max": null},
    "div_yield": {"min": 3, "max": null},
    "market_cap": {"min": 1000000000000, "max": 10000000000000},  # 1조-10조
    "technical_filters": [
      "above_ma20",  # 20일 이평선 위
      "rsi_below_70"
    ],
    "sectors": ["금융", "유틸리티"],
    "markets": ["KOSPI"]
  },
  
  # 알림 설정
  "alert_enabled": True,
  "alert_channels": ["kakao"],
  "alert_frequency": "daily",  # "realtime", "daily", "weekly"
  
  # 실행 이력
  "last_run_at": "2026-04-25T15:00:00Z",
  "last_match_count": 12,
  "matched_tickers_history": [
    # 최근 30일
  ],
  
  # 메타
  "created_at": "2026-04-22T10:00:00Z",
  "updated_at": "2026-04-25T15:00:00Z"
}
```

**Pro 전용 기능**

### `users/{uid}/alerts/{alert_id}`

```python
{
  "alert_id": "uuid-xxx",
  "alert_type": "entry_point",  # "entry_point", "stop_loss", "screener_match", "daily_briefing"
  "ticker": "207940",  # 종목 알림인 경우
  "screener_id": null,  # 스크리너 알림인 경우
  
  # 트리거 조건
  "condition": {
    "type": "price_below",
    "threshold": 1405000,
    "field": "current_price"
  },
  
  # 발송 정보
  "channel": "kakao",  # "kakao", "email", "telegram", "push"
  "sent_at": "2026-04-25T14:00:00Z",
  "delivered": True,
  "delivery_id": "kakao_msg_id_xxx",
  
  # 사용자 반응
  "user_clicked": True,
  "user_clicked_at": "2026-04-25T14:05:00Z",
  
  # 메타
  "created_at": "2026-04-25T14:00:00Z"
}
```

---

## 📊 익명 통계 컬렉션

### `ai_recommendations/{rec_id}`

```python
{
  "rec_id": "uuid-xxx",
  "user_uid_hash": "hashed_uid",  # 개인정보 보호
  
  # 쿼리 (개선용)
  "query": "AI 2차 수혜주 찾아줘",
  "query_intent": "sector_recommendation",  # 의도 분류
  
  # 결과
  "recommended_tickers": ["010120", "007660", "403870"],
  "selected_tickers": ["010120", "007660"],  # 사용자가 선택한 것
  
  # 메타
  "persona": "blackrock",
  "elapsed_seconds": 4.2,
  "tokens_used": 3456,
  "created_at": "2026-04-25T15:00:00Z"
}
```

**용도**: 추천 알고리즘 개선용 데이터 수집 (개인정보 X)

---

## 🔐 Firestore 보안 규칙 (Rules)

```javascript
// firestore.rules
rules_version = '2';

service cloud.firestore {
  match /databases/{database}/documents {
    
    // 종목 데이터 - 모두 읽기 가능
    match /stocks/{document} {
      allow read: if request.auth != null;
      allow write: if false;  // collector.py만 (Admin SDK)
    }
    
    // 테마, 히스토리 - 인증된 사용자만
    match /themes/{document} {
      allow read: if request.auth != null;
      allow write: if false;
    }
    
    match /history/{document} {
      allow read: if request.auth != null;
      allow write: if false;
    }
    
    // 사용자 데이터 - 본인만
    match /users/{uid}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
    
    // AI 추천 통계 - 쓰기는 백엔드만, 읽기 X
    match /ai_recommendations/{document} {
      allow read, write: if false;  // Admin SDK만
    }
  }
}
```

---

## 📈 인덱스 설정 (Composite Index)

자주 사용할 쿼리를 위한 복합 인덱스:

```yaml
# firestore.indexes.json
indexes:
  # 사용자별 분석 이력 (최신순)
  - collection: users/{uid}/analyses
    fields:
      - field: created_at
        order: DESCENDING
  
  # 사용자별 관심 종목 (추가일 순)
  - collection: users/{uid}/watchlist
    fields:
      - field: added_at
        order: DESCENDING
  
  # 알림 미발송 조회
  - collection: users/{uid}/alerts
    fields:
      - field: alert_type
        order: ASCENDING
      - field: delivered
        order: ASCENDING
      - field: created_at
        order: DESCENDING
  
  # 종목 검색 최적화
  - collection: stocks
    fields:
      - field: market
        order: ASCENDING
      - field: market_cap
        order: DESCENDING
```

---

## 🛠 마이그레이션 계획

### 기존 → 신규 (Week 1)

```python
# scripts/migrate_to_axis.py

def migrate():
    """기존 Stock_search_program → Axis 마이그레이션"""
    
    # 1. users/ 컬렉션 생성 (빈 상태)
    # → 신규 가입자부터 자동 생성
    
    # 2. stocks/ 컬렉션 - 그대로 유지
    # 변경 사항 없음
    
    # 3. ai_recommendations/ 컬렉션 생성
    # 빈 상태로 시작
    
    # 4. 기존 collector.py - 그대로 유지
    # 변경 사항 없음
    
    print("✅ 마이그레이션 완료. 기존 데이터 보존, 신규 컬렉션 추가됨.")
```

**기존 데이터 손실 0%, 100% 호환**

---

## 💰 비용 추정 (Firestore)

### 100명 활성 유저 가정

```
일일 작업:
├─ 분석 요청: 100명 × 5회 = 500회
│   - 읽기: 500 × 5 = 2,500 (stock data, themes, news)
│   - 쓰기: 500 × 1 = 500 (analyses 저장)
├─ 검증 요청: 500 × 0.3 = 150회
│   - 읽기: 150 × 2 = 300
└─ 관심 종목 조회: 100 × 10 = 1,000회
    - 읽기: 1,000

일일 합계:
- 읽기: ~5,000회
- 쓰기: ~600회

월간 (30일):
- 읽기: 150,000회 → $0.06
- 쓰기: 18,000회 → $0.07

저장 용량:
- ~100MB → $0.18/월
```

**총 Firestore 비용**: 약 $0.31/월 (~400원) — 거의 무료 티어 내

---

## 🚨 주의사항

### 1. 문서 크기 제한
- Firestore 단일 문서 최대 **1MB**
- `analyses` 문서가 클 수 있음 (4개 에이전트 결과 모두 포함)
- 1MB 초과 시: 별도 컬렉션으로 분리

### 2. 서브컬렉션 vs 배열
- 관심 종목은 **서브컬렉션**으로 (배열 X)
- 이유: 개별 업데이트 효율
- 단점: 쿼리 시 N+1 문제 (한 번에 최대 30개)

### 3. 인덱스 비용
- 복합 인덱스 추가 시 쓰기 비용 증가
- 꼭 필요한 인덱스만

### 4. 백업
- Firestore 자동 백업: GCP 콘솔에서 활성화
- 주 1회 권장

---

## 📚 참고 자료

- Firestore 가격: https://firebase.google.com/pricing
- 데이터 모델링: https://firebase.google.com/docs/firestore/data-model
- 보안 규칙: https://firebase.google.com/docs/firestore/security/rules-conditions

---

**다음 문서**: `docs/api/ai.md`, `docs/LEGAL.md`
