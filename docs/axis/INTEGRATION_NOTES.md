# Axis ↔ v7.5 통합 노트

> ROADMAP.md는 Axis를 신규 프로젝트로 가정하고 작성되었으나,
> 실제로는 기존 v7.5 인프라(Cloud Run, Firebase, FastAPI 앱)를 재사용합니다.
> 이 문서는 ROADMAP의 신규 작업 항목 중 **이미 v7.5에 존재하는 것**을 정리하고,
> Axis가 추가·확장해야 할 부분을 명확히 합니다.

**최종 결정**: 아키텍처 옵션 C (하이브리드) — Axis 코드는 `api/`·`agents/`·`personas/`·`utils/`에 분리하되, 단일 FastAPI 앱(`screener/main.py`)에 마운트하여 운영.

---

## ✅ v7.5에 이미 존재 (재구현 불필요)

| ROADMAP 항목 | 실제 위치 |
|---|---|
| Firebase 프로젝트 | `stock-search-program` (재사용) |
| Firebase Auth (카카오/구글) | Firebase 콘솔 설정됨 |
| 토큰 검증 미들웨어 | `screener/middleware.py:47` `verify_firebase_token()` |
| AuthMiddleware (Starlette) | `screener/middleware.py:72` |
| 티어 시스템 (free/pro) | 동일 미들웨어 + `screener/services/subscription.py` |
| 관리자 자동 승격 | `ADMIN_EMAILS` 환경변수 |
| `users` 컬렉션 | `subscription._users_ref()` 인터페이스 사용 중 |
| `GET/POST /api/user/watchlist` | `screener/api/user_routes.py:141, 161` |
| 메일 발송 (Mailgun) | `screener/services/mailer.py` |
| 결제 (Lemon Squeezy) | `screener/api/lemon_routes.py` |

→ Week 1 Day 3-4의 "Firebase Auth 미들웨어 구현"과 "users 컬렉션 스키마 정의"는 **건드리지 않음**.
→ 카카오 디벨로퍼스 앱 등록도 v7.5에서 이미 완료된 상태로 가정 (`AUTH_ENABLED=true` 운영 중).

---

## 🆕 Axis 신규 추가 (Week 1 스캐폴딩 완료)

```
api/
├── __init__.py
├── routes/
│   ├── __init__.py
│   └── ai.py              ← /api/ai/personas, /analyze (501), /validate (501)
└── middleware/
    └── __init__.py        ← screener.middleware re-export

agents/
├── __init__.py
└── base.py                ← BaseAgent + DISCLAIMER + FORBIDDEN_WORDS (16개)

personas/
└── __init__.py            ← Week 2 Day 5 프롬프트 작성 예정

utils/
├── __init__.py
└── claude_client.py       ← MODEL_HAIKU/SONNET/OPUS 상수, Day 5 본격 구현
```

**`screener/main.py`에 1줄 추가** (axis_ai_router 마운트):
```python
from api.routes.ai import router as axis_ai_router
# ...
app.include_router(axis_ai_router)
```

기존 `AuthMiddleware`가 자동 적용되므로 `/api/ai/*`에도 토큰 검증/티어 체크가 동작합니다.

---

## 🔄 ROADMAP 항목 재해석

### Week 1
- ~~Day 3-4: Firebase Auth 미들웨어 구현~~ → **v7.5에 존재, 재사용 결정**
- Day 5: Anthropic API 키 발급 + `utils/claude_client.py` 본격 구현 + 비용 추적 + 캐시
- 신규: Anthropic API 키를 Cloud Run 시크릿(`anthropic-api-key`)으로 등록 필요

### Week 3
- `/api/ai/analyze` 신규 (Axis): 본 문서의 `api/routes/ai.py` 채움
- `/api/watchlist/*` → **v7.5의 `/api/user/watchlist` 재사용**. 진입선/알림 필드는 기존 watchlist 문서에 추가하는 식으로 확장
- 사용량 카운터: `/users/{uid}/ai_usage` 서브컬렉션 신규 (Axis 전용). v7.5의 trial/subscription 카운터와는 별도

### Week 6
- 카카오 비즈 알림톡: 기존 Mailgun 메일과 함께 `screener/services/mailer.py` 패턴으로 추가
- 법적 검사 스크립트: `BaseAgent.filter_forbidden()` + 별도 `scripts/legal_check.py`

---

## ⚠️ Axis 원칙과 v7.5 운영물의 충돌

`docs/axis/LEGAL.md`는 "추천", "매수 신호", "유망주", "목표가" 등을 **절대 금지**합니다.
그러나 v7.5(main 브랜치)에는 이 원칙과 충돌하는 기능이 운영 중:

- "🏆 오늘의 TOP 픽" 섹션 — 사실상 추천 리스트
- "매수 포인트" 하이라이트 — 매수 신호 표현
- `buy_score` 필드 — 점수화된 추천성 지표

**현재 결정**: `feature/axis-ai-layer` 브랜치 작업 중에는 v7.5 운영물을 건드리지 않음.
**머지 시점 결정 필요**:
1. 리네이밍: "TOP 픽" → "관찰 가치 종목", "매수 포인트" → "관찰 구간"
2. 또는 v7.5 기능을 완전히 Axis 신규 UI로 대체

---

## 📍 환경 변수 추가 사항 (Cloud Run)

기존 `AUTH_ENABLED`, `FIREBASE_*`, `ADMIN_EMAILS`, `LEMONSQUEEZY_*`에 추가:

```bash
ANTHROPIC_API_KEY        # Secret Manager: anthropic-api-key
KAKAO_REST_API_KEY       # 비즈 알림톡 (Week 6, 미발급 OK)
KAKAO_BIZ_TEMPLATE_ID    # 비즈 알림톡 템플릿 (Week 6)
```

`.env.example`에는 Week 1 Day 5 완료 후 일괄 반영합니다.

---

**최종 업데이트**: 2026-04-25 (Week 1 Day 3-4 완료 시점)
