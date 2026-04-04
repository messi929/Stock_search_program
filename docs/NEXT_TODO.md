# 다음 작업 목록

> 업데이트: 2026-04-04 (v5.4.1)

---

## 완료 (v4.2: 크롤링/서빙 분리)

- [x] **T-A1** 독립 데이터 수집기 `collector.py` 생성
- [x] **T-A2** Cloud Run 읽기전용 모드 (`COLLECT_MODE=readonly`)
- [x] **T-A3** 차트 API Firestore 연동 (`load_history_single`)
- [x] **T-A4** US 히스토리 수집 + 기술지표
- [x] **T-A5** Firestore 쓰기 최적화 (변경분만 저장, 펀더멘탈 0 skip)
- [x] **T-A6** Yahoo v7 API 차단 → yfinance ticker.info 병렬 수집 전환
- [x] **T-A7** metrics.py 방어 코드 (KeyError 수정)
- [x] **T-A8** Cloud Run 재배포 — E2E 검증 완료

## 완료 (v5.0: 고도화)

### 안정화
- [x] **T-B1** 카테고리 필터 강화 — 급등예보 1,061→42건, bypass 제거
- [x] **T-B2** 테마 피커 UI — 개별 테마 칩 렌더링 버그 수정
- [x] **T-B3** 데이터 검증 시스템 (`validate_data()`, `--validate`)
- [x] **T-B4** 텔레그램 알림 (`_send_alert()`)
- [x] **T-B5** Windows 작업 스케줄러 (`setup_scheduler.bat`)

### 기능 고도화
- [x] **T-B6** AI 매수 추천 종합점수 (0~100, `calculate_buy_score()`)
- [x] **T-B7** 백테스트 엔진 (`backtest.py`, `/api/backtest`)
- [x] **T-B8** 조건 알림 (`_send_signal_alerts()`)
- [x] **T-B9** 포트폴리오 트래커 (`POST /api/portfolio`)
- [x] **T-B10** US 섹터 분류 (`sector`, `industry`, `/api/sectors`)

### 상용화 기반
- [x] **T-B11** Firebase Auth (`AuthMiddleware`, 이메일 로그인)
- [x] **T-B12** 티어 시스템 (Free/Pro, `AUTH_ENABLED` 환경변수)
- [x] **T-B13** Cloud Run v5.0 배포 + 데이터 검증 이슈 0건

## 완료 (v5.1: 데이터 정합성 + 스케줄)

### 데이터 정합성
- [x] **T-13** 배당 지속성 수집 → yfinance 배당 이력으로 전환
- [x] **T-14** 외국인/기관 수집 — 장중에만 유효, 장외 자동 스킵
- [x] **T-C1** buy_score Firestore 반영 (107건)
- [x] **T-C2** 추세진입 199→75건 — `volume_ratio_min=1.2` 추가
- [x] **T-D1** Firestore 429 에러 — 재시도 로직 (3회 + 백오프)

### 스케줄 시스템
- [x] **T-D2** 고정 스케줄 수집 (06:30 / 09:30 / 16:00 / 22:30)
- [x] **T-D3** Cloud Run 즉시 리로드 (`POST /api/reload`)
- [x] **T-D4** 카테고리별 맥락 필터 UI
- [x] **T-D5** US 섹터 필터 셀렉터
- [x] **T-D6** Cloud Run v5.1 배포

## 완료 (v5.2: 장중 수집 + 클라우드 이관 + UX 전면 개선)

### 장중 경량 수집
- [x] **T-F1** heavy/light 2계층 스케줄 — KR 30분, US 60분 장중 스냅샷
- [x] **T-F2** Firestore heartbeat 5분 주기 (failover 감지)
- [x] **T-F3** `--cloud-fallback` 플래그 — 로컬 비활성 시 클라우드 자동 인계
- [x] **T-F4** 개별 수집 후 Cloud Run 자동 리로드 (`_notify_cloud_run`)

### 클라우드 이관
- [x] **T-F5** Dockerfile.collector + cloudbuild-collector.yaml
- [x] **T-F6** deploy-cloud-jobs.sh (Cloud Scheduler 20개 cron)

### UX 전면 개선 (30개 이슈)
- [x] **T-G1** 모바일 반응형 (`@media 768px/480px`) — 헤더/테이블/모달/필터
- [x] **T-G2** 종목 검색 — 이름/코드 디바운스 자동완성
- [x] **T-G3** 네트워크 에러 핸들링 — 재시도 버튼 + 토스트 알림
- [x] **T-G4** 상승/하락 ▲▼ 화살표 (색맹 접근성)
- [x] **T-G5** 데이터 신선도 상대시간 ("5분 전", 초록/노랑/빨강)
- [x] **T-G6** BT/PF → "백테스트"/"포트폴리오" 텍스트 라벨
- [x] **T-G7** Phase 로딩 메시지 ("펀더멘탈 분석 중...")
- [x] **T-G8** 온보딩 가이드 (첫 방문 5단계 오버레이)
- [x] **T-G9** 카테고리 그룹별 색상 (전략=파랑, 시장=보라, 시그널=초록)
- [x] **T-G10** 카테고리 hover tooltip (JS fixed position)
- [x] **T-G11** 빈 결과 → 필터 초기화 버튼
- [x] **T-G12** 차트 15초 타임아웃 + 재시도 버튼
- [x] **T-G13** 내보내기 확인 모달 (종목 수/필터/형식 표시)
- [x] **T-G14** 필터 min/max 유효성 검증
- [x] **T-G15** 키보드 단축키 (`/` 검색, `f` 필터, `?` 도움말)
- [x] **T-G16** 테마주 대분류 가로스크롤 (하위 테마 칩 제거)
- [x] **T-G17** 칩/테마 스크롤바 표시 (`scrollbar-width:thin`)
- [x] **T-G18** 선택 칩 가운데 자동 스크롤 (`scrollIntoView`)
- [x] **T-G19** 활성 칩 glow 효과 (box-shadow)
- [x] **T-G20** 별표 터치 타겟 확대 (28px + hover 스케일)
- [x] **T-G21** 관심종목 로컬 저장 안내 문구
- [x] **T-G22** 테이블 가로스크롤 래퍼
- [x] **T-G23** 스킵 내비게이션 (sr-only)
- [x] **T-G24** 로딩 ARIA (`role="status"`)
- [x] **T-G25** 백테스트 결과 UI (시그널별 적중률 카드 모달)
- [x] **T-G26** 포트폴리오 관리 UI (종목 추가/삭제 + 수익률 대시보드)
- [x] **T-G27** buy_score/buy_grade/sector/industry API 매핑 수정
- [x] **T-G28** AI점수 화살표 제거 (인라인 색상 전용)
- [x] **T-G29** /api/schedule-status 엔드포인트
- [x] **T-G30** Cloud Run v5.2 배포 완료

---

## 완료 (v5.3: 클라우드 자동 수집 배포)

### 인프라 배포
- [x] **T-F7** Cloud Run Job 빌드 — `gcloud builds submit --config=cloudbuild-collector.yaml`
- [x] **T-F8** Cloud Scheduler 배포 — 20개 cron 등록 (heavy 4 + light-kr 10 + light-us 6)
- [x] **T-F9** Secret Manager 시크릿 등록 (firebase-key, admin-key)
- [x] **T-F10** Cloud Run Job 수동 실행 테스트 → KR 2,772 + US 711 종목 수집 확인
- [x] **T-F11** App Engine 초기화 (Cloud Scheduler 필수 의존)

### 버그 수정 + 개선
- [x] **T-F12** .dockerignore에서 collector.py 제외 해제 → 빌드 COPY 실패 수정
- [x] **T-F13** cloudbuild-collector.yaml — jobs create||update 멱등성 보장
- [x] **T-F14** collector.py — 컨테이너 로그 경로(/tmp), Firestore 수집 상태 기록
- [x] **T-F15** /api/schedule-status — Firestore에서 수집 상태 반환 (Cloud Run 호환)
- [x] **T-F16** deploy-cloud-jobs.sh — 원클릭 통합 배포 (검증+빌드+Job+Scheduler)

### 안정성 검증 (진행 중)
- [x] **T-E1** collector-heavy 수동 실행 → Cloud Run 리로드 정상 확인
- [ ] **T-E2** 06:30 / 09:30 / 16:00 / 22:30 각 시간대 자동 수집 확인
- [ ] **T-E3** 장중 light 스케줄 (10:00~15:00) 30분 간격 동작 확인
- [ ] **T-E4** 72시간 안정성 검증 — Firestore 수집 상태 성공률 100% 확인

---

## 완료 (v5.4: 투자자 관점 품질 개선 — 알고리즘·리스크·매도 시그널)

### 알고리즘 정확도 향상
- [x] **T-H1** RSI → Wilder's EMA 방식 (증권사 HTS 동일 수치)
- [x] **T-H2** 골든크로스 → 실제 교차 시점 감지 (최근 5일 내, 기존: 상태만 표시)
- [x] **T-H3** 장기 골든크로스 추가 (MA20/MA60, 최근 10일)
- [x] **T-H4** 52주 고저가 정확도 — HISTORY_DAYS 60→250 (실제 52주 데이터)
- [x] **T-H5** 급등 예보 임계값 강화 — 3/5→4/5, 조건별 변별력 상향
- [x] **T-H6** 매집 시그널 강화 — 거래량 연속 증가 2일 조건 추가

### 매도 시그널 (신규)
- [x] **T-H7** 손절 시그널 — 52주 고점 대비 -7% 이하
- [x] **T-H8** 익절 시그널 — 52주 저점 대비 +15% 이상
- [x] **T-H9** 경고 시그널 — 데드크로스 / RSI≥75 / MA 역배열

### 리스크 지표 (신규)
- [x] **T-H10** 20일 변동성 (일간 수익률 표준편차)
- [x] **T-H11** ATR 14일 (Average True Range)
- [x] **T-H12** 리스크 등급 4단계 (낮음/보통/높음/매우높음)

### 한/미 분리 스코어링
- [x] **T-H13** KR: 기술(40) + 모멘텀(25) + 수급(20) + 가치(15)
- [x] **T-H14** US: 기술(35) + 모멘텀(30) + 성장(20) + 가치(15)
- [x] **T-H15** US PBR 2~4 구간 인정, ROE·거래량·시가총액 기반 성장 팩터

### UI/라벨 개선
- [x] **T-H16** "AI 추천"→"종합 추천", "AI점수"→"종합점수"
- [x] **T-H17** "AI 기반"→"데이터 기반" (온보딩)
- [x] **T-H18** 투자 유의사항 면책 문구 (온보딩 하단)
- [x] **T-H19** 매도신호 배지 (손절:빨강, 익절:초록, 경고:노랑)
- [x] **T-H20** 리스크 등급 컬럼 (색상 구분)
- [x] **T-H21** GC장기 배지, 변동성/ATR 컬럼 정의

### 백엔드 연동
- [x] **T-H22** schemas.py — 7개 새 필드 (sell_signal, risk_grade 등)
- [x] **T-H23** main.py — calculate_sell_signals 6곳 호출
- [x] **T-H24** collector.py — calculate_sell_signals 2곳 호출
- [x] **T-H25** 백테스트 — 250일 데이터로 샘플 수 약 4배 증가

---

## 완료 (v5.4.1: 핫픽스 — UTC→KST, 시크릿 검증, API 필드 매핑)

### 수집 시간 UTC→KST 수정
- [x] **T-I1** Dockerfile — `TZ=Asia/Seoul` + tzdata 설치 (Cloud Run 컨테이너 UTC 문제)
- [x] **T-I2** Dockerfile.collector — 동일 TZ 수정
- [x] **T-I3** routes.py — `last_update`에 명시적 KST timezone 적용 (`timedelta(hours=9)`)

### Heavy Collector Job 복구
- [x] **T-I4** cloudbuild-collector.yaml — heavy job에서 텔레그램 시크릿 제거 (SECRETS_LIGHT 사용)
- [x] **T-I5** deploy-cloud-jobs.sh — `gcloud secrets versions access` 검증 추가 (describe만으론 부족)

### v5.4 API 필드 매핑 누락 수정
- [x] **T-I6** routes.py `_row_to_item()` — 7개 필드 매핑 추가 (golden_cross_long, sell_signal, stop_loss_pct, target_price_pct, volatility_20d, atr_14, risk_grade)

### 배포
- [x] **T-I7** Cloud Run: stock-screener-00024-rrp (100% traffic)
- [x] **T-I8** Collector image: TZ=Asia/Seoul 적용 리빌드
- [x] **T-I9** Heavy Job: 텔레그램 시크릿 제거 후 테스트 실행 성공

---

## 미진행 — 다음 작업 (우선순위 순)

### Phase A: 빈 화면 / 신뢰도 문제 해결 (심각)
- [ ] **T-J1** surge(급등예보) 카테고리 0건 — v5.4 임계값 4/5 → 3/5 완화 또는 조건 재조정
- [ ] **T-J2** turnaround(반등매수) 카테고리 0건 — RSI+거래량 동시 충족 조건 완화
- [ ] **T-J3** ETF 카테고리 0건 — 1,088개 존재하는데 필터링 로직 버그
- [ ] **T-J4** sell_signal "손절" 80~90% — 52주 고점 대비 -7% 기준 과도 → -15~20%로 완화
- [ ] **T-J5** foreign_net/inst_net 항상 0 — 수급 데이터 미수집 → 스마트머니 카테고리 0건
- [ ] **T-J6** golden_cross_long 항상 0 — 히스토리 200일 미달 또는 계산 로직 버그

### Phase B: 데이터 품질 개선 (높음)
- [ ] **T-J7** KR sector/industry = "0.0" — 한국 주식 섹터 분류 누락 (US는 정상)
- [ ] **T-J8** US div_years 항상 0 — 미국 배당 연속 연수 수집 누락
- [ ] **T-J9** KR risk_grade 편향 — 대형주 53%가 높음/매우높음 vs US 5%. 시장별 변동성 기준 분리
- [ ] **T-J10** 히스토리 미수집 종목 20~40% — RSI/변동성/이동평균 0인 종목이 risk_grade "낮음"으로 오표시
- [ ] **T-J11** 히스토리 없는 종목(rsi=0) 과매도 필터 통과 — 기술지표 0인 종목 카테고리 제외

### Phase C: 기타 개선 (보통)
- [ ] **T-J12** schedule-status 모니터링 빈 값 — collector_heartbeat, last_schedule 미기록
- [ ] **T-J13** sectors 엔드포인트 `name: 0` 잘못된 항목 — US 미분류 종목 처리
- [ ] **T-J14** stop_loss_pct/target_price_pct 전 종목 -7/+15 고정 — 변동성 기반 종목별 차등
- [ ] **T-J15** US 성장주 ROE 이상값 — 음수 자본 기업(ROE 7000%) 필터 제외 또는 캡 처리
- [ ] **T-J16** schedule-status 타임스탬프 UTC→KST 불일치 — collector 측 isoformat에 KST 적용

### 3단계: UI/UX 실사용 검증
- [ ] **T-15** 브라우저 접속 → 전체 UI 검증 (Cloud Run + 데스크톱 앱)
- [ ] **T-16** 종목 상세 차트 → Firestore 히스토리 로드 확인
- [ ] **T-17** US 모드 기술지표 카테고리 확인
- [ ] **T-H1** 모바일(375px) 실기기 테스트 — 테이블/모달/필터 사용성
- [ ] **T-H2** 온보딩 → 검색 → 필터 → 상세 → 관심종목 전체 흐름 테스트

### 4단계: 상용화 배포
- [ ] **T-21** 도메인 + HTTPS 설정
- [ ] **T-22** 랜딩 페이지 / 다운로드 페이지
- [ ] **T-C7** 결제 연동 (Stripe / 토스페이먼츠)
- [ ] **T-C8** 관심종목 클라우드 동기화 (Firebase Auth 연동)
- [ ] **T-19** 데스크톱 인스톨러 (Inno Setup)
- [ ] **T-20** 자동 업데이트 체계

### 5단계: 수동 설정 (선택)
- [ ] **T-11** Windows 작업 스케줄러 — `setup_scheduler.bat` (로컬 이중화 시)
- [ ] **T-12** 텔레그램 봇 설정 — BotFather 토큰 + chat_id → `.env`

---

## 아키텍처 (v5.2)

```
[Cloud Scheduler + Cloud Run Job] (1차 — 클라우드 수집기)
  ├─ heavy: 06:30 / 09:30 / 16:00 / 22:30 (전체 수집, --all)
  ├─ light_kr: 10:00~15:00 매 30분 (--kr-snapshot --etf)
  ├─ light_us: 00:00~05:00 매 60분 (--us-snapshot)
  ├─ Cloud Scheduler 20개 cron → Cloud Run Job 트리거
  └─ 수집 후 /api/reload → 고객 즉시 확인
        ↓
[collector.py --schedule] (선택 — 로컬 개발/이중화)
  ├─ --cloud-fallback: heartbeat 기반 이중화 (클라우드 장애 시 자동 인계)
  └─ 로컬 테스트 시 --schedule로 직접 실행 가능
        ↓
[Firestore] (Google Cloud)
        ↓
[Cloud Run] (COLLECT_MODE=readonly, v5.2)
  ├─ Firestore 즉시 리로드 (/api/reload)
  ├─ 장중 5분마다 자동 리로드
  ├─ FastAPI API (16개 카테고리 + 백테스트 + 포트폴리오 + 섹터)
  ├─ 카테고리별 맥락 필터 (관련 필터만 표시)
  ├─ Firebase Auth + 티어 미들웨어
  ├─ WebSocket 실시간 업데이트
  └─ 크롤링 없음 (CPU/메모리 절약)
        ↓
[데스크톱 / 브라우저]
  └─ https://stock-screener-119320994983.asia-northeast3.run.app
```

## Cloud Run 설정
- URL: `https://stock-screener-119320994983.asia-northeast3.run.app`
- 리전: asia-northeast3 (서울)
- 메모리: 1Gi, CPU: 1, min-instances: 1
- 환경변수: `RUN_MODE=server, COLLECT_MODE=readonly`

## 환경변수 (.env)
```
RUN_MODE=server
COLLECT_MODE=readonly|full
PORT=8501
ADMIN_KEY=
FIREBASE_KEY_PATH=
FIREBASE_CREDENTIALS=
AUTH_ENABLED=false
FIREBASE_WEB_API_KEY=
FIREBASE_PROJECT_ID=
CLOUD_RUN_URL=https://stock-screener-119320994983.asia-northeast3.run.app
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```
