# Axis 진행 기록 — 2026-05-26 ~ 2026-05-27 (KIS 도입 + UI 풀스택)

> 한국투자증권 OpenAPI 도입(Phase 0~3) + UI 풀스택 통합 + 운영 마무리. 2일간 commit 3건, prod 4회 재배포.
> 이전 기록: [`PROGRESS_2026-05.md`](./PROGRESS_2026-05.md) (5/21~24)

---

## 0. 현재 production 상태 (2026-05-27 기준)

| 영역 | 상태 |
|---|---|
| 도메인 | `axislytics.com` 라이브 (Cloudflare Proxy + Cloud Run SNI 우회) |
| 로그인 | Firebase Google OAuth 정상 |
| 프론트 | Vercel `axis-web` 최신 `axis-zmw5oi4op-*` |
| 백엔드 | Cloud Run `stock-screener` rev **00046-88p** (asia-northeast3, **min=1/max=1**) |
| Cloud Run Jobs (6) | 기존 그대로 (backfill / daily-korea / daily-macro / daily-options / weekly-events / monthly-regime) |
| 데이터 | KR 외인/기관 4 카테고리 5년 백필 완료 + **KIS REST 6 endpoint + WS** 라이브 |
| 결제 | LS 미연결 (여전히 차단 항목) |

---

## 1. 날짜별 완료 작업

### 2026-05-26 — KIS Phase 0~3 백엔드 + 프론트 헤더

| 영역 | 작업 | 커밋 |
|---|---|---|
| Phase 0 | `utils/data_collectors/kis_client.py` 신규 — REST + access_token 24h 캐시 (메모리 + `/tmp/kis_token_real.json`), 1분 1회 정책 자동 준수, 키/시크릿/Bearer 마스킹 | df6b7ae |
| Phase 1A | `kis_client`에 호가/분봉/투자자별 매매동향 메서드 | df6b7ae |
| Phase 1B | `screener/core/data_fetcher.py` 외인/기관 3단 폴백: pykrx → KIS → 네이버 (KIS 키 없으면 자동 skip) | df6b7ae |
| Phase 2 | `utils/data_collectors/kis_websocket.py` 신규 — approval_key + PINGPONG echo + 재접속 backoff + 동시 종목 한도 41 | df6b7ae |
| Phase 3A | `api/routes/kis.py` 신규 — 5 endpoint + health, in-memory TTL 캐시 (가격·호가 5s / 분봉 30s / 일봉·투자자 5m) | df6b7ae |
| Phase 3D | `api/routes/kis_ws.py` 신규 — 단일 KIS WS → N 클라이언트 fan-out 매니저 | df6b7ae |
| 운영 | `screener/main.py` dotenv 자동 로드 + KIS 라우터 등록 / `requirements.txt`에 `websockets>=14.0` | df6b7ae |
| 프론트 | `web/lib/kis.ts` + `web/lib/kis-ws.ts` + `web/types/kis.ts` + `web/hooks/useKisPrice.ts` (5 React Query 훅) | 2ba9ba6 |
| 프론트 | `AnalyzeView` 헤더 가격 fallback에 KIS 라이브 가격 + 등락률 컬러 | 2ba9ba6 |
| prod | Secret Manager `kis-app-key`/`kis-app-secret` 등록 + IAM accessor / Cloud Run env `KIS_ENV=real` / **max-instances=1 강제** (KIS 토큰 정책 보호) / cloudbuild로 새 이미지 배포 | (gcloud) |
| 테스트 | unit 25개 (17 REST + 8 WS) PASS / 라이브 smoke (`scripts/check_kis_*`) 3건 PASS | — |

### 2026-05-27 — KIS UI 풀스택 + 운영 마무리

| 영역 | 작업 | 커밋 |
|---|---|---|
| 차트 | `KisCandleChart` 신규 — lightweight-charts 5.x, 일/주/월/분봉 토글, 한국식 컬러(🔴상승/🔵하락) + 거래량 히스토그램 | 43f9ce9 |
| 호가 | `KisOrderbook` 신규 — 10호가 + 잔량 막대 + 매수/매도 우세 %p | 43f9ce9 |
| 수급 | `KisInvestorFlow` 신규 — 14일 외인/기관 매매 흐름 막대 + 14일 누적 요약 (외인/기관/개인) | 43f9ce9 |
| 통합 | `AnalyzeView`에 KIS UI 섹션 추가 (KR 종목 한정, AI 분석 진행 중에도 즉시 노출) | 43f9ce9 |
| WS 활성화 | `useKisLivePrices` 훅 신규 (여러 ticker 동시 subscribe) + `WatchlistPreview`에 WS 실시간 가격/등락률 push | 43f9ce9 |
| from_cache 메타 | `api/routes/ai.py` SSE complete에 `likely_cached`(elapsed<5s 휴리스틱) 추가 → 프론트가 elapsed 직접 추정 대신 백엔드 명시 메타 사용 | 43f9ce9 |
| 모바일 nav | 5번째 항목 "🔔 알림 설정" → "⚙️ 설정"(/settings/profile), settings prefix active 매칭, profile 헤더에 알림 링크 | 43f9ce9 |
| OG | `app/opengraph-image.tsx` 신규 — Next 동적 OG 생성 (Axis 브랜드 + 면책), 1200×630 PNG ~100KB | 43f9ce9 |
| prod | 백엔드 cloudbuild 재배포 + Vercel `axis-zmw5oi4op` 배포 + axislytics.com alias 자동 적용 | (자동) |
| 검증 | chrome-devtools로 prod console error 0 / OG image 200 PNG / KIS cross-origin 200 | — |

---

## 2. 핵심 검증 결과

### KIS Phase 0~3 라이브 (005930, 2026-05-26)

| 항목 | 결과 |
|---|---|
| Token 발급 | 24h TTL, 파일 캐시 정상 (재실행 시 발급 0회) |
| 현재가 | ₩299,000 / +2.22% / 거래량 23,441,371 |
| 일봉 | 94개 (영업일 ~140일분) |
| 호가 | 매도1 ₩299,500 / 매수1 ₩299,000 (스프레드 500) |
| 투자자 | 5/26 외인 +1,891,734 / 기관 +1,513,469 / 개인 -3,263,161 |
| WS | connect → subscribe ack → PINGPONG echo 1회, 장 마감 후라 ticks=0 (정상) |

### prod 검증 (Cloud Run 새 컨테이너, 2026-05-26)

| 시나리오 | 결과 |
|---|---|
| 5 REST endpoint 일괄 | calls=6 ok=6 fail=0, **token_issues=1**, cache_hits=4 |
| 브라우저 cross-origin | axislytics.com → Cloud Run KIS API status=200, source=kis |
| max=1 적용 후 새 컨테이너 | 토큰 1회만 발급, EGW00133 락 위험 0 |

### prod 검증 (2026-05-27 풀스택)

| 시나리오 | 결과 |
|---|---|
| axislytics.com 랜딩 | console error 0, network 200 |
| OG 동적 생성 | `axislytics.com/opengraph-image?...` → 200 PNG 102KB |
| KIS API cross-origin 재확인 | status=200, price=299000, source=kis |
| TypeScript 전체 | `tsc --noEmit` EXIT=0 (각 묶음마다 검증) |

---

## 3. 도입한 아키텍처 요약

### KIS REST (백엔드 in-memory TTL 캐시)
- `/api/kis/price/{ticker}` — 5초
- `/api/kis/orderbook/{ticker}` — 5초
- `/api/kis/chart/{ticker}/minute` — 30초
- `/api/kis/chart/{ticker}/daily` — 5분
- `/api/kis/investor/{ticker}` — 5분
- `/api/kis/health` — 운영 점검

### KIS WebSocket
- `/api/kis/ws/stream` (KisFanout — 단일 KIS WS → N 클라이언트 fan-out)
- 프로토콜: `{action: "subscribe"|"unsubscribe"|"ping", tickers: [...]}`
- 서버 → 클라: `{type: "tick"|"subscribed"|"pong", ticker, data}`
- 한 계정당 KIS WS 1개 → **Cloud Run min/max=1 강제 필수**
- 동시 등록 종목: 실전 41 한도 (전 클라이언트 합산)

### 데이터 소스 매트릭스
| 영역 | 소스 | 비고 |
|---|---|---|
| 일별 현재가/시고저 | **KIS** | 5초 캐시 |
| 일봉/주봉/월봉/년봉 | **KIS** (수정주가) | 5분 캐시 |
| 분봉 | **KIS** | 30초 캐시, 30개씩 |
| 10호가 + 잔량 | **KIS** | 5초 캐시 |
| 외인/기관/개인 일별 매매동향 | **KIS** | 5분 캐시 |
| 외인/기관 전종목 일괄 | pykrx (1차) | KRX 공식 |
| 외인/기관 종목별 폴백 | KIS (2차) → 네이버 (3차) | 안전망 |
| PER/PBR/배당률/업종 | pykrx/네이버 | KIS는 분기 단위만 제공 |
| 테마 분류 | 네이버 | KIS 미제공 |
| 한국 거시 | ECOS (한국은행) | 기존 |
| 미국 거시 | FRED (연준) | 기존 |
| 자사주 공시 | DART | 기존 |

---

## 4. 남은 과제

### 🔴 Critical — 수익화/출시 차단
- **LS 결제 미연결** — 여전히 dead path. 본인(admin grant)은 영향 0이지만 외부 사용자 Pro 전환 0.
  - 결정 필요: (a) LS 재신청 (b) Toss Payments 전환 (c) 정식 오픈 더 연기

### 🟡 Moderate — 운영 안정성
- Anthropic 자동 충전 한도 — 5/24 잔액 부족 2회 → console.anthropic.com 한도 확인 권장 (사용자 본인 작업)
- daily-korea-collect 응답 일관성 며칠 더 모니터링
- KIS EGW00133 락 발생 시 알림 — 텔레그램 봇 연결 시 자동화 가능

### 🟢 Nice-to-have / 향후 검토
- macro_indicators 누적 충분 후 매크로 카드 정량 사이클 재검증
- KIS Pro 차등 정책 (Free/Pro 호출 한도 차등) — 현재 무제한
- KIS WS Firebase Auth 검증 — 현재 endpoint open, prod 트래픽 본격화 전 추가 권장
- 검색 한글 종목명 — 5/27 prod 검증 완료 (삼성/바이오 각 5건 hit)

### ✅ 2026-05-27 완료
- ~~og:image PNG~~ → Next 동적 OG로 대체 (더 깔끔)
- ~~SaveEntryPointsButton 라이브 검증~~ → 코드 무결 확인
- ~~분석 결과 캐시 hit/miss 명확화~~ → SSE complete에 `likely_cached` 추가
- ~~모바일 nav "⚙️ 설정"~~ → 5번째 항목 라벨/href 통합
- ~~한글 검색 검증~~ → prod에서 정상 hit

---

## 5. 핵심 파일 (KIS 도입)

### 백엔드
```
utils/data_collectors/
  kis_client.py          # REST + token 캐시
  kis_websocket.py       # WS + approval_key + fan-out 가능 구조

api/routes/
  kis.py                 # REST 6 endpoint
  kis_ws.py              # WS fan-out endpoint

screener/
  main.py                # dotenv 자동 로드 + KIS 라우터 등록
  core/data_fetcher.py   # 외인/기관 3단 폴백 (pykrx → KIS → 네이버)

scripts/
  check_kis_smoke.py     # REST 라이브 smoke
  check_kis_ws_smoke.py  # 클라이언트 직접 WS 검증
  check_kis_ws_endpoint.py # /api/kis/ws/stream endpoint smoke

tests/data_collectors/
  test_kis_client.py     # 17 unit
  test_kis_websocket.py  # 8 unit
```

### 프론트
```
web/types/kis.ts                            # KIS 응답 타입
web/lib/kis.ts                              # 5 REST 클라이언트 + 포맷 유틸
web/lib/kis-ws.ts                           # WS 클라이언트 (재접속 + 구독 복원)
web/hooks/useKisPrice.ts                    # 5 React Query 훅 (REST)
web/hooks/useKisLivePrices.ts               # 여러 ticker WS subscribe 훅

web/components/analyze/
  KisCandleChart.tsx                        # 일/주/월/분봉 토글 + 거래량
  KisOrderbook.tsx                          # 10호가 + 잔량 막대 + 우세 %
  KisInvestorFlow.tsx                       # 14일 외인/기관 흐름
  AnalyzeView.tsx                           # 통합 + likely_cached 사용

web/components/dashboard/
  WatchlistPreview.tsx                      # WS 실시간 가격 표시

web/app/opengraph-image.tsx                 # Next 동적 OG 카드
```

---

## 6. 자주 쓰는 운영 명령 (KIS 관련 추가)

```powershell
# KIS Secret 갱신 (키 회전 시)
$tmp = New-TemporaryFile
Set-Content -NoNewline -Encoding ascii -Path $tmp -Value '새_app_key'
gcloud secrets versions add kis-app-key --data-file=$tmp --project=all-of-asset
Remove-Item $tmp

# Cloud Run KIS env 변경 (paper ↔ real)
gcloud run services update stock-screener --region=asia-northeast3 `
  --project=all-of-asset --update-env-vars=KIS_ENV=real

# max-instances 확인 (KIS WS는 반드시 1)
gcloud run services describe stock-screener --region=asia-northeast3 `
  --project=all-of-asset --format="value(spec.template.metadata.annotations)" |
  Select-String "Scale"

# 로컬 KIS 라이브 smoke (token cache는 /tmp/kis_token_real.json)
py scripts/check_kis_smoke.py        # REST 5 + token cache
py scripts/check_kis_ws_smoke.py 15  # 백엔드 모듈 직접 WS 15초

# prod KIS health 빠른 확인
curl https://stock-screener-1043976673827.asia-northeast3.run.app/api/kis/health
```

---

## 7. 비용/리스크 메모

- **KIS API 호출 한도**: 종목당 분당 20회 (시세) + 초당 5회 (전반). 백엔드 캐시(5s~5m)로 보호 → 일반 사용 패턴에선 충분.
- **token 발급 1분 1회**: 메모리 + 파일 캐시 + max=1로 위반 위험 0.
- **WS 동시 종목 41**: 한 계정 한도. 사용자별 키 분리 없이 공유 → 향후 사용자 수 늘면 결정 필요.
- **Cloud Run 비용**: min/max=1 강제 → 24h 가동 약 $30/월 추가 (기존 min=1 패턴과 동일, max 줄인 것뿐).
- **Anthropic 비용**: 변화 없음 (KIS는 Claude 호출 X).

---

**마지막 업데이트**: 2026-05-27
**작성자**: JEON + Claude (KIS 도입 대화)
**관련 메모리**: `project_kis_phase.md`
