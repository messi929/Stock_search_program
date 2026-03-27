# 다음 작업 목록

> 업데이트: 2026-03-27 (v5.1)

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
- [x] **T-13** 배당 지속성 수집 → 네이버(파싱 불가) → **yfinance 배당 이력**으로 전환
- [x] **T-14** 외국인/기관 수집 — 장중에만 유효 확인, 장외 자동 스킵 처리
- [x] **T-C1** `collector.py --all` 실행 → buy_score Firestore 반영 (107건)
- [x] **T-C2** 추세진입 199→**75건** — `volume_ratio_min=1.2` 조건 추가
- [x] **T-D1** Firestore 429 에러 대응 — save_history/save_stocks 재시도 로직 (3회 + 백오프)

### 스케줄 시스템
- [x] **T-D2** 고정 스케줄 수집 (06:30 / 09:30 / 16:00 / 22:30)
- [x] **T-D3** Cloud Run 즉시 리로드 (`POST /api/reload`) — 수집 완료 후 자동 호출
- [x] **T-D4** 카테고리별 맥락 필터 UI — 카테고리에 따라 관련 필터만 노출
- [x] **T-D5** US 섹터 필터 셀렉터 (`/api/sectors` → `f-sector`)
- [x] **T-D6** Cloud Run v5.1 배포

---

## 미진행 — 다음 작업 (우선순위 순)

### 1단계: 안정성 검증
- [ ] **T-10** `collector.py --schedule` 72시간 장기 안정성 테스트
- [ ] **T-E1** 22:30 US 수집 → Cloud Run 리로드 정상 동작 확인
- [ ] **T-E2** 06:30 / 09:30 / 16:00 각 시간대 수집 정상 동작 확인

### 2단계: UI/UX 검증 및 개선
- [ ] **T-15** 브라우저 접속 → 전체 UI 검증 (Cloud Run + 데스크톱 앱)
- [ ] **T-16** 종목 상세 차트 → Firestore 히스토리 로드 확인
- [ ] **T-17** US 모드 기술지표 카테고리 확인
- [ ] **T-C3** 백테스트 결과 UI 표시 (현재 API만 구현)
- [ ] **T-C4** 포트폴리오 관리 UI (현재 API만 구현)
- [ ] **T-C6** AI 추천 등급 뱃지 색상/스타일 최종 확인
- [ ] **T-E3** 카테고리별 맥락 필터 UX 검증 (실제 사용 흐름)

### 3단계: 상용화 배포
- [ ] **T-19** 인스톨러 생성 (Inno Setup)
- [ ] **T-20** 자동 업데이트 체계
- [ ] **T-21** 도메인 + HTTPS 설정
- [ ] **T-22** 랜딩 페이지 / 다운로드 페이지
- [ ] **T-C7** 결제 연동 (Stripe / 토스페이먼츠)
- [ ] **T-C8** 모바일 반응형 최적화

### 4단계: 수동 설정 (사용자)
- [ ] **T-11** Windows 작업 스케줄러 등록 — `setup_scheduler.bat` 관리자 실행
- [ ] **T-12** 텔레그램 봇 설정 — BotFather 토큰 + chat_id → `.env`

---

## 아키텍처 (v5.1)

```
[collector.py --schedule] (로컬 PC)
  ├─ 고정 스케줄: 06:30 / 09:30 / 16:00 / 22:30 KST
  │   ├─ 06:30  US 최종 + KR 전체 + 펀더멘탈 + 테마 + 배당
  │   ├─ 09:30  KR 개장 후 + 외국인/기관 + 히스토리
  │   ├─ 16:00  KR 마감 + 외국인/기관 확정 + 히스토리 + 배당
  │   └─ 22:30  US 프리마켓 + US 히스토리
  ├─ buy_score 계산 (기술40 + 모멘텀25 + 수급20 + 가치15)
  ├─ 데이터 검증 (validate_data)
  ├─ 시그널 알림 (텔레그램)
  ├─ Firestore 쓰기 (429 재시도 + 배치 딜레이)
  └─ Cloud Run /api/reload 호출 → 고객 즉시 확인
        ↓
[Firestore] (Google Cloud)
        ↓
[Cloud Run] (COLLECT_MODE=readonly, v5.1)
  ├─ Firestore 즉시 리로드 (/api/reload)
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
