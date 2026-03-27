# Stock Screener Pro — 작업 이력

> v4.1.0 | 15개 카테고리 | 국내+해외 | 매수 추천 시스템 | 중앙서버 아키텍처

---

## ✅ 완료된 작업

### Step 0: 버그 수정
- [x] **B-01** Phase별 카테고리 활성화/비활성화 → 전체 Phase 1 즉시 활성화로 전환
- [x] **B-02** ETF market_cap 억원 단위 정규화
- [x] **B-03** 테마 크롤링 페이지네이션 확장 (9→50)
- [x] **B-04** scan API `locals()` 버그 수정 (`required_phase` 등 불필요 변수 전달)

### Step 1: 데이터 보강
- [x] **D-01** 거래대금 필터 활성화 (MIN_TRADING_VALUE)
- [x] **D-02** 테마 검색 드롭다운 + 테마 칩 셀렉터
- [x] **D-03** 외국인/기관 순매수 크롤링
- [x] **D-04** PER/PBR 상위 500 병렬 수집 (8스레드)
- [x] **D-05** 배당 지속성 데이터 (div_years, div_growth)
- [x] **D-06** NASDAQ/S&P500 시세 수집 (10스레드, ~700종목)

### Step 2: 기능 고도화
- [x] **F-01** CSV/Excel 내보내기
- [x] **F-02** 관심종목 (Watchlist)
- [x] **F-03** 종목 상세 팝업 + 캔들차트
- [x] **F-04** 자동 갱신 (장중 30분)
- [x] **F-05** 알림 기능 (Browser Notification)
- [x] **F-06** WebSocket 실시간 업데이트

### Step 3: 매수 추천 시스템 전환
- [x] **R-01** 카테고리 전면 재설계 (결과→예측 시그널)
- [x] **R-02** 예측 지표 추가 (pre_surge_score, accumulation, breakout_score 등)
- [x] **R-03** Phase 1 즉시 활성화 (데이터 없으면 필터 자동 스킵)

### Step 4: UI/UX 재설계
- [x] **U-01** 다크 테마 + 칩 UI + Pretendard 폰트
- [x] **U-02** 세그먼트 컨트롤 + 카테고리 칩 바
- [x] **U-03** 국내/해외 토글 (🇰🇷/🇺🇸)
- [x] **U-04** 테마주 서브 셀렉터 (칩 바)
- [x] **U-05** NASDAQ 달러 표기 + US 거래대금 필터 제외
- [x] **U-06** 모달 슬라이드업 애니메이션

### Step 5: 인프라
- [x] **I-01** 데이터 수집 병렬화 (펀더멘탈 8스레드, 히스토리 5스레드, US 10스레드)
- [x] **I-02** 데스크톱 앱 (desktop.py + desktop.bat)
- [x] **I-03** PyInstaller 빌드 설정 (screener_pro.spec)
- [x] **I-04** 티어 접근 제어 미들웨어 (middleware.py)

### Step 6: Firestore DB + 성능 개선
- [x] **DB-01** Firebase/Firestore 연동 (서비스 계정 키, firebase_client.py)
- [x] **DB-02** Firestore 데이터 레이어 (repository.py — stocks/themes/history/sync_metadata)
- [x] **DB-03** DB 우선 로드 전략 (Firestore 캐시 → 즉시 표시 → 백그라운드 갱신)
- [x] **DB-04** 차등 갱신 — 장중/장외 구분 (기술지표 장중 매 갱신, 외국인/기관 1시간)
- [x] **DB-05** US 데이터 yfinance 배치 전환 (개별 700회→배치 8회, 시가총액/PER 실제값)
- [x] **DB-06** 테마 상위 그룹 분류 (264테마 → 11그룹, 기타 1개만)
- [x] **DB-07** .gitignore 추가 (Firebase 키, 캐시, 빌드 파일 보호)
- [x] **DB-08** 서버 시작 전 Firestore 로드 완료 대기 (빈 화면 방지)

### Step 7: 중앙서버 아키텍처 전환
- [x] **A-01** RUN_MODE (server/client) 설정 체계 (config.py + client_config.json)
- [x] **A-02** desktop.py client 모드 (로컬 서버 없이 원격 URL 접속)
- [x] **A-03** CORS 미들웨어 (원격 클라이언트 접속 허용)
- [x] **A-04** /api/refresh 관리자 키 보호 (ADMIN_KEY)
- [x] **A-05** 경량 client PyInstaller 빌드 (84MB, 서버 의존성 제외)
- [x] **A-06** 연결 실패 시 에러 화면 표시

### Step 8: UX 개선
- [x] **UX-01** 다중 컬럼 정렬 (1차 클릭 + 2차 Shift+클릭)
- [x] **UX-02** 정렬 상태 시각 표시 (①②인디케이터 + 결과 헤더 텍스트)
- [x] **UX-03** 카테고리 간략 설명 표시 (내부 기준 비공개)
- [x] **UX-04** 카테고리 전환 시 테이블 즉시 초기화 (이전 데이터 잔류 방지)
- [x] **UX-05** 테마 2단 선택 UI (그룹 탭 → 테마 칩)
- [x] **UX-06** 테마 필터 드롭다운 optgroup 그룹화
- [x] **UX-07** pywebview 네이티브 창 + 시스템 트레이 + 앱 아이콘

---

## 📋 향후 과제

### Step 9: 크롤링/서빙 분리 + 데이터 정밀화 (2026-03-26~27)
- [x] 독립 데이터 수집기 (collector.py) — 크롤링/서빙 아키텍처 분리
- [x] Cloud Run 읽기전용 모드 (COLLECT_MODE=readonly)
- [x] US 종목 시가총액/PER/PBR/ROE/배당 실제 값 (yfinance ticker.info 병렬)
- [x] US 종목 히스토리 수집 → 기술지표 적용 (fetch_us_historical_ohlcv)
- [x] 차트 API Firestore 연동 (로컬 캐시 → Firestore)
- [x] Firestore 쓰기 최적화 — 변경분만 저장, 펀더멘탈 0 보존
- [x] Yahoo v7 API 차단 대응 — yfinance ticker.info로 전환
- [x] metrics.py 방어 코드 (KeyError 수정)
- [x] Cloud Run 재배포 + E2E 검증 완료
- [ ] 외국인/기관 연속 순매수일 추적

### 기능 추가
- [ ] KIS API 연동 (실시간 호가/체결)
- [ ] 종목 비교 기능 (2~3종목 나란히)
- [ ] 포트폴리오 시뮬레이션
- [ ] 뉴스/공시 연동

### 상용화 배포
- [x] 클라우드 서버 배포 (Cloud Run)
- [ ] 도메인 + HTTPS 설정
- [ ] 사용자 인증 (Firebase Auth / JWT)
- [ ] 인스톨러 (Inno Setup / NSIS)
- [ ] 자동 업데이트 체계
- [ ] Firestore Blaze 플랜 전환 (종량제)

---

## 아키텍처 (v4.2 — 크롤링/서빙 분리)

```
[데이터 수집기] collector.py (로컬 PC)
  ├─ 크롤링 (FDR, 네이버, yfinance ticker.info)
  ├─ 기술지표 계산 (MA, RSI, 52주, 급등예보)
  ├─ Firestore 쓰기 (변경분만, 펀더멘탈 보존)
  └─ --schedule: 장중 30분 / 장외 대기 자동 루프
        ↓
[Firestore] (Google Cloud)
        ↓
[Cloud Run 서버] (COLLECT_MODE=readonly)
  ├─ Firestore 읽기 (장중 5분 / 장외 30분)
  ├─ FastAPI + WebSocket API 서빙
  ├─ 15개 카테고리 필터 + 다중 정렬
  └─ 크롤링 없음 (CPU/메모리 절약)
        ↓
[데스크톱 클라이언트] (RUN_MODE=client, 84MB)
  └─ pywebview → Cloud Run URL 접속
      ├─ 서버 연결 실패 시 에러 화면
      └─ 시스템 트레이 상주
```

### 운영 모드
| 모드 | COLLECT_MODE | 설명 |
|------|-------------|------|
| 로컬 개발 | full | 크롤링 + Firestore 쓰기 + API 서빙 |
| Cloud Run | readonly | Firestore 읽기 + API 서빙 (크롤링 없음) |
| 수집기 | - | collector.py 독립 실행 (크롤링 + Firestore 쓰기) |

## 디폴트 카테고리 필터 요약

| 카테고리 | 시총 | 거래대금 | 핵심 조건 | 정렬 |
|---------|------|---------|---------|------|
| 급등 예보 | ≥500억 | ≥10억 | - | 급등예보점수↓ |
| 성장주 | ≥1000억 | ≥10억 | ROE≥15%, PER 0.1~30 | ROE↓ |
| 저평가 | ≥1000억 | ≥10억 | PER 0.1~10, PBR 0.1~1.0 | PER↑ |
| 배당주 | ≥1000억 | ≥10억 | 배당률≥3% | 배당률↓ |
| 추세 진입 | ≥500억 | ≥10억 | 골든크로스 | 돌파점수↓ |
| 반등 매수 | ≥500억 | ≥10억 | RSI≤35, 거래량비≥1.5x, PBR≤1.5 | RSI↑ |
| ETF | - | - | ETF만 | 거래량↓ |
| 대형주 | ≥50000억 | - | - | 시총↓ |
| 중소형주 | 500~5000억 | - | - | 거래량비↓ |
| 테마주 | ≥300억 | - | 테마 선택 가능 | 거래량비↓ |
| 관심종목 | - | - | 사용자 저장 | 등락률↓ |
| 매집 의심 | ≥500억 | ≥10억 | - | 거래량비↓ |
| 스마트머니 | ≥1000억 | ≥10억 | - | 외국인순매수↓ |
| 돌파 임박 | ≥500억 | ≥10억 | 52주고가 5%이내 | 돌파점수↓ |
| 과매도 반등 | ≥500억 | ≥10억 | RSI≤35 | RSI↑ |
