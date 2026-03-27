# Stock Screener Pro v4.1.0 — Changelog

> 2026-03-21 | Firestore DB + 중앙서버 아키텍처 + 성능 개선 + UX 개선

---

## 변경 요약

### 1. 중앙 서버 / 클라이언트 아키텍처 전환

**문제**: 기존 구조는 고객 PC마다 서버+크롤링+Firestore를 독립 실행 → 2,000명이면 Firestore 읽기 900만/일, 비용 폭탄

**해결**: server/client 모드 분리

```
[중앙 서버 1대 (Cloud)]           [고객 2,000명]
  ├─ 크롤링 (30분마다)              └─ StockScreenerPro.exe (84MB)
  ├─ Firestore 읽기/쓰기                └─ pywebview → 서버 URL 접속
  └─ FastAPI API + WebSocket             └─ Firestore 접근 없음
```

**변경 파일:**

| 파일 | 변경 내용 |
|------|----------|
| `screener/config.py` | `RUN_MODE` (server/client), `SERVER_URL`, `ADMIN_KEY`, `client_config.json` 로더 추가 |
| `desktop.py` | client 모드: 로컬 서버 안 띄우고 원격 URL로 직접 접속. server 모드: 기존 동작 유지 |
| `screener/main.py` | CORS 미들웨어 추가, `/api/refresh` 관리자 키 보호 |
| `client_config.json` | 클라이언트 설정 (server_url, run_mode) |
| `client.spec` | 경량 클라이언트 PyInstaller 빌드 (서버 의존성 제외) |
| `server.bat` | 서버 모드 실행 스크립트 |
| `build.bat` | Client/Server 빌드 선택 메뉴 |

**빌드 비교:**

| | Server 빌드 | Client 빌드 (배포용) |
|--|------------|-------------------|
| 용량 | 289MB | **84MB** (71% 감소) |
| exe 크기 | 34MB | **6MB** |
| 포함 내용 | 전체 (pandas, firebase, 크롤러) | pywebview + config만 |
| Firestore | 직접 접근 | 없음 |
| 크롤링 | 실행 | 없음 |

---

### 2. Firestore DB 연동 (서버 측)

**문제**: 앱 시작 시 매번 전체 크롤링 → 12~15분 소요
**해결**: Google Firestore를 영구 캐시로 사용, 차등 갱신 전략 적용

**신규 파일:**
- `screener/db/__init__.py`
- `screener/db/firebase_client.py` — Firestore 클라이언트 싱글톤
- `screener/db/repository.py` — 데이터 CRUD (stocks, themes, history, sync_metadata)

**Firestore 컬렉션 구조:**
```
stocks/{ticker}        — 종목 마스터 + 시세 + 펀더멘탈 + 기술지표
themes/{theme_id}      — 테마명 + 상위 그룹
theme_groups/{group}   — 테마 그룹별 소속 테마 목록
history/{ticker}       — 최근 60일 OHLCV (배열)
sync_metadata/status   — 데이터 소스별 마지막 동기화 시각
```

**서버 시작 흐름 (빈 화면 방지):**
```
lifespan 시작
  ├─ await load_from_firestore()   ← 서버 시작 전에 완료 (블로킹)
  │   └─ Firestore에서 종목/테마/기술지표 로드 (~2초)
  ├─ 서버 시작 (이미 데이터 있는 상태)
  └─ create_task(refresh_stale_data)  ← 백그라운드 갱신
```

**차등 갱신 주기 (장중/장외 구분):**

| 데이터 | KR 장중 (09~15:30) | US 장중 (23:30~06:00) | 장외 |
|--------|-------------------|---------------------|------|
| KR 스냅샷 | 매 갱신 (30분) | 매 갱신 | 매 갱신 |
| US 시세 | 6시간 | **1시간** | 6시간 |
| 펀더멘탈 | 24시간 | 24시간 | 24시간 |
| 테마 매핑 | 7일 | 7일 | 7일 |
| 외국인/기관 | **1시간** | 12시간 | 12시간 |
| 배당 지속성 | 7일 | 7일 | 7일 |
| 히스토리+기술지표 | **매 갱신** | 24시간 | 24시간 |

자동 갱신 루프: KR 장중 30분, US 장중 60분, 장외 대기

**성능 비교:**

| | Before | After |
|--|--------|-------|
| 첫 기동 (캐시 없음) | 12~15분 | ~2분 (크롤링 후 Firestore 저장) |
| 재기동 (캐시 있음) | 12~15분 (parquet 당일만) | **~2초** (Firestore 로드) |
| 고객 첫 화면 | 빈 테이블 | **즉시 데이터 표시** |

---

### 3. NASDAQ 데이터 수집 개선

**문제:** `fdr.DataReader()` 개별 700+회, `market_cap: 99999` 더미값, 에러 무시

**해결:**
- `yfinance.download()` 배치 수집 (100종목씩, ~8회)
- `yfinance.Ticker.fast_info`로 실제 시가총액/PER
- 시가총액 USD→억원 환산 (1USD ≈ 1,400KRW)

**수정:** `screener/core/data_fetcher.py` — `fetch_us_snapshot()` 전면 재작성

---

### 4. 테마 카테고리 재분류

**문제:** 264개 테마 플랫 리스트 → 사용자가 원하는 테마 찾기 어려움

**해결:** 키워드 매칭 기반 11개 상위 그룹 자동 분류 (264개 중 기타 1개만)

| 그룹 | 테마 수 | 예시 |
|------|--------|------|
| IT·소프트웨어 | 39 | 플랫폼, 핀테크, 블록체인, 게임 |
| AI·반도체 | 37 | 인공지능, GPU, HBM, 데이터센터 |
| 2차전지·에너지 | 33 | 배터리, 리튬, 태양광, 수소 |
| 산업·소재 | 32 | 철강, 화학, 조선, 방산 |
| 소비재·유통 | 32 | 화장품, 식품, 이커머스 |
| 바이오·헬스케어 | 29 | 제약, 신약, 의료기기 |
| 정책·테마 | 22 | 탄소중립, 스마트팩토리 |
| 자동차·모빌리티 | 19 | 전기차, 자율주행, 로봇 |
| 금융·부동산 | 15 | 은행, 증권, 리츠 |
| 통신·미디어 | 5 | 5G, 엔터, K-POP |
| 기타 | 1 | 미분류 |

**프론트엔드:** 2단 선택 UI (그룹 탭 → 테마 칩), 필터 드롭다운도 optgroup으로 그룹화

---

### 5. UX 개선

#### 다중 컬럼 정렬 (1차 + 2차)
- **클릭** → 1차 정렬 (①▼ 파란색)
- **Shift + 클릭** → 2차 정렬 (②▼ 보라색)
- 예: 급등예보점수 ↓ → 같은 점수 내에서 ROE ↓
- 정렬 상태가 결과 헤더에 텍스트로 표시
- 백엔드: `sort_by2`, `sort_asc2` 파라미터 추가

#### 카테고리 설명 표시
- 카테고리 선택 시 칩 아래에 한 줄 설명 표시
- 내부 필터 기준(시총, 거래대금, RSI 임계값 등)은 비공개
- 예: "곧 급등할 가능성이 높은 종목을 포착합니다"

#### 카테고리 전환 시 즉시 초기화
- 테이블을 "불러오는 중..." 으로 즉시 교체 → 이전 데이터 잔류 방지

---

### 6. 데스크톱 앱 (pywebview)

- **pywebview** 네이티브 창 (Edge WebView2)
- **시스템 트레이** 아이콘 (pystray) — 열기/종료 메뉴
- **앱 아이콘** — 차트 모양 .ico (16~256px 멀티 해상도)
- **favicon** 추가
- client 모드: 원격 서버 접속 시 연결 실패 에러 화면 표시

---

### 7. 기타 변경

- `.gitignore` 생성 — Firebase 키, 캐시, 빌드 파일 보호
- `requirements.txt` — `firebase-admin>=6.0.0`, `yfinance>=0.2.0` 추가
- `routes.py` — `set_data()`에 `theme_groups` 파라미터 추가, `/api/themes`에 `groups` 포함
- `screener.py` — `ScreenerFilter`에 `sort_by2`, `sort_asc2` 추가, 다중 정렬 로직

---

## 신규/변경 파일 목록

| 파일 | 상태 | 설명 |
|------|------|------|
| `screener/config.py` | 수정 | RUN_MODE, SERVER_URL, ADMIN_KEY 추가 |
| `screener/main.py` | 수정 | lifespan await, CORS, 관리자 보호, 장중/장외 갱신 |
| `screener/core/data_fetcher.py` | 수정 | US 종목 yfinance 배치 전환 |
| `screener/core/screener.py` | 수정 | 다중 정렬, 카테고리 설명 수정 |
| `screener/api/routes.py` | 수정 | sort_by2, theme_groups, CORS |
| `screener/static/index.html` | 수정 | 다중 정렬 UI, 테마 그룹 UI, 카테고리 설명, favicon |
| `screener/db/__init__.py` | 신규 | DB 패키지 |
| `screener/db/firebase_client.py` | 신규 | Firestore 클라이언트 |
| `screener/db/repository.py` | 신규 | CRUD + 테마 그룹 분류 (264→11그룹) |
| `desktop.py` | 수정 | client/server 모드 분기, pywebview |
| `client_config.json` | 신규 | 클라이언트 설정 |
| `client.spec` | 신규 | 경량 클라이언트 빌드 |
| `screener_pro.spec` | 수정 | 서버 빌드 (신규 의존성 반영) |
| `build.bat` | 수정 | Client/Server 빌드 선택 |
| `server.bat` | 신규 | 서버 모드 실행 |
| `desktop.bat` | 수정 | conda 의존 제거 |
| `assets/icon.ico` | 신규 | 앱 아이콘 |
| `assets/icon.png` | 신규 | 트레이 아이콘 |
| `.gitignore` | 신규 | 보안 파일 보호 |

## 실행 방법

| 용도 | 명령 |
|------|------|
| 서버 실행 | `server.bat` 또는 `RUN_MODE=server py -m uvicorn screener.main:app --host 0.0.0.0 --port 8501` |
| 클라이언트 개발 | `desktop.bat` (client_config.json의 server_url에 접속) |
| 클라이언트 빌드 | `build.bat` → 1번 (84MB) |
| 서버 빌드 | `build.bat` → 2번 (289MB) |
| 배포 | `dist/StockScreenerPro/` 폴더 zip → 고객 배포, `client_config.json`의 server_url을 실서버로 변경 |
