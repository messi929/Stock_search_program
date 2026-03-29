# 다음 작업 목록

> 업데이트: 2026-03-29 (v5.2)

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

## 미진행 — 다음 작업 (우선순위 순)

### 1단계: 클라우드 수집기 배포 (인프라)
- [ ] **T-F7** Cloud Run Job 빌드 — `gcloud builds submit --config=cloudbuild-collector.yaml`
- [ ] **T-F8** Cloud Scheduler 배포 — `./deploy-cloud-jobs.sh` (20개 cron 등록)
- [ ] **T-F9** Secret Manager 시크릿 등록 (firebase-credentials, admin-key, telegram-*)
- [ ] **T-F10** Cloud Run Job 수동 실행 테스트 → Firestore 갱신 확인

### 2단계: 안정성 검증
- [ ] **T-E1** 22:30 US 수집 → Cloud Run 리로드 정상 동작 확인
- [ ] **T-E2** 06:30 / 09:30 / 16:00 각 시간대 수집 확인
- [ ] **T-E3** 장중 light 스케줄 (10:00~15:00) 30분 간격 동작 확인
- [ ] **T-E4** 72시간 안정성 검증 — schedule_status.json 성공률 100% 확인

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
  └─ https://stock-screener-ug23nrnjva-du.a.run.app
```

## Cloud Run 설정
- URL: `https://stock-screener-ug23nrnjva-du.a.run.app`
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
CLOUD_RUN_URL=https://stock-screener-ug23nrnjva-du.a.run.app
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```
