# 다음 작업 목록

> 업데이트: 2026-04-18 (v7.5 — Mailgun 자동화 + 레이아웃 정렬 + 휴장일 KR/US)

---

## 🚀 v7.5 배포 완료 (2026-04-18)

Cloud Run: `stock-screener-1043976673827.asia-northeast3.run.app` · 커밋 4개 · STATUS=SUCCESS.

### 구현 완료
- **C8** 트라이얼 D-2 Mailgun 이메일 자동화 (코드 완료, 사용자 DNS/Scheduler 설정 대기)
- **G15** Top 픽 섹션 리디자인 (메달 배지·텍스트 접기버튼·태그 색분리·hover 개선)
- **UX-16** Top 픽·Trial/Guest 배너 **1280px 컨테이너 정렬** (카드 스타일 통일, `.info-banner` 클래스 신설)
- **UX-17** **휴장일 3-line 안내** — 장 상태 / 📅 KR MM/DD(요일) 종가 / 📅 US MM/DD(요일) 종가 (KR KST 15:30·US ET 16:00 기준, 주말→금요일 되돌림. 공휴일 미반영)

### 논의만 (구현 X)
- **카드결제 재검토** — LS 재승인 대기 유지. 단기 Paddle 백업 + 중기 Toss Payments 병행 방향 정리.

### 남은 사용자 작업
- **C8 마무리**: Mailgun 가입 → 서브도메인 DNS 등록 → `gcloud secrets create mailgun-api-key` → `gcloud scheduler jobs create http trial-reminder-daily --schedule="0 10 * * *"` (상세: `DEPLOY_GUIDE.md §10`)

---

## 🎯 미완/누락 체크리스트 (매 배포 전 검증)

**배포 직전에 이 섹션 읽고 각 항목 상태 확인. 완료한 것만 체크.**

### A. 즉시 착수 (30분~1시간)
- [x] **A1** 오프라인 감지 + 친화적 토스트 (`navigator.onLine`)
- [x] **A2** 관심종목 정렬 옵션 (이름/등락률/점수/추가순)
- [x] **A3** `.cat-desc` 시각 강화 (배경/보더/💡 아이콘)
- [x] **A4** 포트폴리오 CSV export (모달 헤더 📥 CSV 버튼)

### B. 중간 (반나절~1일)
- [x] **B5** og:image 생성 — `/og/rank.svg?date=`·`/og/backtest.svg` (동적 SVG 1200x630)
- [x] **B6** 모바일 필터 드로어 애니메이션 (하단 슬라이드업, 핸들바, 배경 오버레이)
- [x] **B7** 리퍼럴 코드 시스템 — `/api/user/referral`·`/apply` (추천인 30일, 피추천인 14일)

### C. 큰 작업 (1~2일)
- [x] **C8** 트라이얼 D-2 이메일 알림
  - [x] `/api/admin/trial-expiring?days=2` 조회 엔드포인트
  - [x] `POST /api/admin/send-trial-reminders` 발송 엔드포인트 (Mailgun, 중복방지)
  - [x] `screener/services/mailer.py` Mailgun 래퍼
  - [x] `DEPLOY_GUIDE.md §10` Cloud Scheduler + Mailgun 셋업 절차
  - [ ] **사용자 작업**: Mailgun 가입 → DNS 등록 → Secret 등록 → Scheduler Job 생성
- [x] **C9** 관리자 액션 로그 — `users/{uid}/audit_log` 서브컬렉션 + `GET /api/admin/users/{uid}/audit-log`

### D. 기타 미완 (Phase 1~3 원안 대비)
- [x] **D10** 카테고리 진입 가이드 강화 (A3로 통합 완료)
- [x] **D11** 에러 UX 일관화 — 공통 fetch wrapper에 오프라인 감지 + 토큰 자동 갱신
- [ ] **D12** 백테스트 snapshot 공유 URL (선택 — 후순위)

### E. 권한 변경 (사용자 요청)
- [x] **E13** **백테스트 Pro 해제 → 로그인 필수** — `PRO_ENDPOINTS`에서 제거, `LOGIN_REQUIRED_ENDPOINTS` 신설

### F. 로직/UX 재조정 (사용자 피드백)
- [x] **F14** **매수 포인트 임계값 재조정** — 카테고리 설계(≥30)와 정합, 네거티브 톤 제거
  - 이전: 70+ 적극매수 / 50+ 매수후보 / 나머지 관망 권장 (Top 3도 대부분 관망)
  - 현재: 60+ 💎 강력 매수 / 45+ 👍 매수 후보 / 30+ 📊 관심 종목 / <30 🔍 추가 분석

### G. UI/UX 개선 (신규 발견)
- [x] **G15** **Top 픽 섹션 UI 리디자인**
  - [x] 접기 버튼: `−` → `접기/펼치기 ▼` 텍스트 + 회전 아이콘
  - [x] 카드: 순위 메달(🥇🥈🥉) + 상단 그라데이션 바 (gold/silver/bronze)
  - [x] 태그 색 분리: AI 추천(파랑) / 급등 예보(빨강)
  - [x] 등락률 배지화 (bg + 진한 색)
  - [x] 호버: translateY(-2px) + 블루 글로우 그림자
  - [x] 모바일 2열 + 폰트/패딩 최적화
  - [x] 섹션 상단 무지개 accent bar + AI 배지

### F. 사용자 지적 — 향후 재검증 필요
- 검증된 것
  - ✅ 비로그인 localStorage 잔재
  - ✅ 메모/태그 클라우드 동기화
  - ✅ 모달 7종 로그아웃 시 자동 닫기
  - ✅ `/api/portfolio/risk` PRO_ENDPOINTS 누락
  - ✅ 토스트 위치 (오른쪽 → 중앙)
  - ✅ 모달 그리드 공간 낭비
  - ✅ 펀더멘탈 탭 빈 상태 안내
  - ✅ 🔥 Top 픽 섹션 (Phase 1 누락분)

### 체크리스트 운영 규칙
1. 새 요구사항·허점 발견 시 **즉시 여기에 항목 추가**
2. 배포 전 전체 훑고 해당 항목 체크
3. 배포 후 완료 항목은 `v7.4 완료 섹션`으로 이동 (하단)
4. 미완 항목은 남겨두고 다음 세션 계속

---

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

## 완료 (v5.5: 실사용성 개선 — ETF 수정, 수급 전환, UI 정리)

### 버그 수정
- [x] **T-K1** ETF 카테고리 0건 수정 — 프론트엔드 market=KR 자동 주입이 ETF(market="ETF") 제외시킴
- [x] **T-K2** 필터 패널 영역 겹침 — max-height 확장 → flexbox 고정 폭 200px로 전환
- [x] **T-K3** 빈 결과 안내 개선 — 카테고리별 구체적 기준 설명 메시지 (7개 시그널 카테고리)

### 기능 제거
- [x] **T-K4** 매도 시그널(손절/익절/경고) 전면 제거 — 매수가 없이 52주 고저가 기준은 실용성 없음
  - calculate_sell_signals() 삭제, config 상수 삭제
  - schemas, routes, screener columns, main, collector 호출부 제거
  - 프론트엔드 매도신호 컬럼 및 badge-dead CSS 제거

### 수급 데이터 전환 (네이버 → pykrx + 네이버 하이브리드)
- [x] **T-K5** pykrx(KRX 공식) 우선, 실패 시 네이버 frgn.naver 폴백
- [x] **T-K6** 장 마감 후에도 외국인 순매수 수집 가능 (기존: 장중만)
- [x] **T-K7** collector에서 장중 시간 체크(_is_kr_market_hours) 제거
- [x] **T-K8** buy_score 수급 점수: 규모별 가산점 → 부호 기반 단순화 (단위 무관)
- [x] **T-K9** 프론트엔드 금액 표시 fmtAmt 함수 추가 (억/조 단위)

### UI/UX 개선
- [x] **T-K10** 종목 상세 모달에 외국인/기관 순매수 표시 추가
- [x] **T-K11** 종합추천 카테고리에서 foreign_net 컬럼 제거 (장 마감 후 항상 "-")
- [x] **T-K12** 스마트머니 카테고리 desc 업데이트 (KRX 공식 데이터)
- [x] **T-K13** export 컬럼 단위 표기 수정 (외국인순매수(원), 기관순매수(원))

### 배포
- [x] Cloud Run: stock-screener-00025 ~ 00031 (7회 배포)

---

## 완료 (v6.0: 기관급 분석 — Phase 1~5 백엔드)

### Phase 1: 시그널 신뢰도 확보
- [x] **P1-1** backtest.py 전면 개편 — 다기간 수익률(5/10/20/60d), sharpe, profit_factor, max_drawdown
- [x] **P1-2** score_history Firestore 컬렉션 — 30일 보관, 16:00 장마감 1회 저장
- [x] **P1-3** 벤치마크 대비 알파 — 전종목 평균 수익률 기준, 시그널별 alpha 필드

### Phase 2: 수급 분석 고도화
- [x] **P2-1** supply_history Firestore 컬렉션 — 종목별 20일 수급 이력 자동 저장
- [x] **P2-2** 수급 시그널 — foreign_consecutive, supply_intensity, dual_buy, supply_grade(5등급)
- [x] **P2-3** GET /api/market-sentiment — 시장 전체 수급 게이지 (외국인/기관 비율, 등락비)

### Phase 3: 펀더멘탈 깊이 확장
- [x] **P3-1** yfinance 10개 필드 추가 — forward_pe, peg_ratio, ev_ebitda, profit_margin, operating_margin, fcf_yield, debt_equity, revenue_growth, target_price, target_upside
- [x] **P3-2** StockItem 스키마 확장 — 12개 신규 필드 (62 fields total)
- [x] **P3-3** buy_score 가치 팩터 5단계 강화 — PER(4) + PBR(3) + EV/EBITDA(3) + FCF(3) + 목표가(2)
- [x] **P3-4** quality(퀄리티주) 카테고리 추가 — profit_margin≥10, debt_equity≤100, revenue_growth≥5

### Phase 4: 리스크 프레임워크
- [x] **P4-1** ATR 기반 포지션 사이징 — 2ATR 손절, 최대 25%
- [x] **P4-2** POST /api/portfolio/risk — 상관관계 행렬 + 포트폴리오 변동성 + 섹터 편중 경고
- [x] **P4-3** GET /api/market-regime — 강세/약세/횡보 감지 + 전략별 가중치

### Phase 5: 차별화 기능
- [x] **P5-1** GET /api/compare — 2~5개 종목 나란히 비교
- [x] **P5-2** 스마트 복합 알림 — 외국인연속+기술반등, 수급동반+목표가
- [x] **P5-3** GET /api/sector-flow — 섹터(테마그룹)별 자금 흐름

### 배포
- [x] Cloud Run API: rev 00033 (stock-screener)
- [x] Cloud Run Collector: 3개 Job 업데이트 (collector-heavy/light-kr/light-us)
- [x] 핫픽스: sector-flow NaN→int 변환 에러 수정

---

## 완료 (v6.1: 프론트엔드 전면 구현 + 데이터 품질 개선)

### v6 UI: 시그널 성적표 (Phase 1-4)
- [x] **V6-UI-1** 백테스트 모달 리디자인 — 5/10/20/60일 탭, profit_factor/max_drawdown/sharpe 표시
- [x] **V6-UI-2** 벤치마크 대비 알파 표시 — 시그널별 초과수익 배지
- [x] **V6-UI-3** 스냅샷 시그널 섹션 — buy_70plus, pre_surge, breakout, dual_buy 적중률 카드

### v6 UI: 수급 게이지 (Phase 2-3)
- [x] **V6-UI-4** 헤더/결과 상단 수급 게이지 바 — 외국인/기관 매수세 프로그레스바
- [x] **V6-UI-5** 수급 등급 badge — 강력매수(빨강)/매수세(주황)/중립/매도세/강력매도
- [x] **V6-UI-6** 외국인 연속매수일 컬럼 + 동반매수 아이콘 (COL_DEFS 추가)

### v6 UI: 펀더멘탈 탭 (Phase 3-5)
- [x] **V6-UI-7** 종목 상세 모달 탭 추가 — 기본 | 펀더멘탈 | 수급 | 리스크
- [x] **V6-UI-8** 펀더멘탈 탭 — EV/EBITDA, 영업이익률, FCF Yield, 부채비율, 매출 성장률, 목표가
- [x] **V6-UI-9** 수급 탭 — 외국인/기관 연속일수, 수급 강도, 동반매수, 수급 등급

### v6 UI: 리스크 (Phase 4)
- [x] **V6-UI-10** 포지션 사이징 표시 — 모달 리스크 탭에 "총 자산의 X% 투자 권장" 문구
- [x] **V6-UI-11** 포트폴리오 리스크 대시보드 — 상관관계 테이블 + 섹터 분포 바 + 편중 경고
- [x] **V6-UI-12** 시장 레짐 인디케이터 — 헤더에 강세/약세/횡보 배지 + 신뢰도 tooltip

### v6 UI: 차별화 (Phase 5)
- [x] **V6-UI-13** 종목 비교 뷰 — 2~5개 종목 나란히 카드 (14개 지표)
- [x] **V6-UI-14** 섹터 자금흐름 그리드 — 유입=녹색, 유출=빨강, 종목 수 표시
- [x] **V6-UI-15** 퀄리티주 카테고리 칩 + 컬럼 정의 (profit_margin, debt_equity 등)

### 데이터 품질 개선
- [x] **T-J11** rsi=0 종목 과매도/반등 필터 통과 방지 — oversold, turnaround에 rsi_min=1 추가
- [x] **T-J15** US ROE 이상값 캡 처리 — ROE를 -100~200% 범위로 clip
- [x] **T-J9** KR risk_grade 편향 수정 — 시장별(KR/US) 변동성 기준 분리, 히스토리 없는 종목 "데이터없음"

### backtest.py 개선
- [x] API 응답 windows 키 형식 "5d"/"10d"/"20d"/"60d"로 통일
- [x] 기본 5d 통계를 최상위에도 포함 (하위 호환)

### 트레이더 실사용 이슈 수정 (7건)
- [x] **UX-1** 검색 함수 bluechip만 조회 → 3개 카테고리 병렬 검색 (커버리지 확대)
- [x] **UX-2** 퀄리티주 KR 0건 → desc "해외 전용" 명시 + 빈 결과 안내 추가
- [x] **UX-3** buy_score 히스토리 없는 종목 부풀림 → RSI=0+MA20=0이면 점수 70% 감점
- [x] **UX-4** 백테스트/레짐 API 캐싱 없음 → 5분 TTL 간이 캐시 도입
- [x] **UX-5** 종목 비교 잘못된 코드 무시 → not_found 피드백 + 토스트 알림
- [x] **UX-6** 포트폴리오 리스크 1종목 무반응 → "2개 이상 필요" 안내
- [x] **UX-7** 온보딩 자동 팝업 비활성화 (? 키 수동 접근 유지)

### KR 섹터 + 히스토리 확대 + 배포
- [x] **T-J7** KR 섹터 분류 — 네이버금융 업종 크롤링 추가 (기존 PER/PBR 함수 확장)
- [x] **T-J10** 히스토리 커버리지 확대 — KR 600+400, US 300+200, 타임아웃 10→20초
- [x] Cloud Run 웹 서비스 재배포 (rev 00034)
- [x] Cloud Run Collector Jobs 재배포 (이미지 갱신)
- [x] docs/DEPLOY_GUIDE.md 작성 (Cloud Run, 도메인, HTTPS 3가지 방법)
- [x] docs/CHANGELOG_v6.1.md 작성

### 배포
- [x] Cloud Run: stock-screener (v6.1 전체 반영)
- [x] Cloud Run Collector: 3개 Job 이미지 갱신

---

## 완료 (v7.0: 상용화 — Stripe 결제 + 인증 시스템, 2026-04-11)

### 백엔드 Stripe 인프라
- [x] **COM-1** `stripe>=8.0.0` 패키지 추가
- [x] **COM-2** `screener/services/subscription.py` 신규 — 구독 서비스 레이어
  - `get_or_create_stripe_customer()` — Firestore ↔ Stripe 고객 동기화
  - `sync_subscription_to_firebase()` — Stripe 구독 → Firestore + Firebase custom claims
  - `ensure_user_doc()` — 첫 로그인 시 Firestore users 문서 자동 생성
  - `clear_subscription()` — 구독 해지/결제 실패 시 tier=free 초기화
- [x] **COM-3** `screener/api/stripe_routes.py` 신규 — 5개 API 엔드포인트
  - `POST /api/checkout` — Stripe Checkout Session 생성 (KRW 구독)
  - `POST /api/webhooks/stripe` — Stripe 이벤트 수신 (서명 검증, claims 갱신)
  - `GET /api/subscription` — 구독 상태 조회
  - `POST /api/subscription/cancel` — 기간 종료 해지
  - `POST /api/billing-portal` — Stripe 고객 포털 리다이렉트
- [x] **COM-4** middleware.py — PUBLIC_PATHS에 webhook, auth-config, stripe-config 추가
- [x] **COM-5** main.py — stripe_router 등록

### 프론트엔드 상용화 UI
- [x] **COM-6** 로그인 모달 전면 교체 — `prompt()` 제거, HTML 모달
  - 이메일/비밀번호 입력 필드 (다크 테마)
  - 로그인/회원가입 모드 토글
  - Google 로그인 (GoogleAuthProvider)
  - Firebase 에러코드별 한국어 메시지
- [x] **COM-7** 가격 모달 — 월간(₩9,900)/연간(₩99,000) 2카드
  - 기능 비교 리스트, "2개월 무료" 뱃지
  - 클릭 → `POST /api/checkout` → Stripe 결제 페이지 리다이렉트
- [x] **COM-8** 계정 관리 모달 — 이메일, 플랜, 구독 상세
  - 다음 결제일, 해지 예정 표시
  - Stripe 고객 포털 / 구독 해지 버튼
- [x] **COM-9** 헤더 티어 배지 (Free/Pro) + CSS 스타일링
- [x] **COM-10** 403 핸들러 개선 — "Pro 업그레이드" → `showPricingModal()` 연동
- [x] **COM-11** 결제 완료 처리 — `?payment=success` 토스트 + `getIdToken(true)` 강제 갱신
- [x] **COM-12** `initAuth()` 확장 — 로그인 후 자동 user doc 생성 + 구독 상태 로드

### Firestore 스키마 추가
- [x] **COM-13** `users/{firebase_uid}` 컬렉션 설계
  - email, tier, created_at, stripe_customer_id, subscription(id/status/plan/period_end/cancel)

### Webhook 이벤트 처리
- [x] **COM-14** `checkout.session.completed` → tier=pro
- [x] **COM-15** `customer.subscription.updated` → 상태 동기화
- [x] **COM-16** `customer.subscription.deleted` → tier=free
- [x] **COM-17** `invoice.payment_failed` → tier=free

---

## 완료 (v7.1: Lemon Squeezy 전환 + 법적 페이지 + Pro UI 확장, 2026-04-12)

### 배경
한국 Stripe 정식 미지원 + 개인 개발자(사업자등록 없음) + 해외 고객 타겟 → **Lemon Squeezy (MoR)** 로 공급자 전환.
Paddle 대비 Stripe식 URL 리다이렉트 방식이라 마이그레이션 공수 최소, Stripe가 2024년 LS 인수해 안정성↑.

### 결제 공급자 교체
- [x] **LS-1** `screener/api/stripe_routes.py` 삭제 → `screener/api/lemon_routes.py` 신규
  - `POST /api/checkout` — LS Checkout URL 생성 (`custom_data.firebase_uid`)
  - `POST /api/webhooks/lemonsqueezy` — HMAC-SHA256(body, secret) 서명 검증, X-Signature 헤더
  - `GET /api/subscription` — Firestore에서 조회
  - `POST /api/subscription/cancel` — `DELETE /subscriptions/{id}` (기간 종료 예약)
  - `POST /api/billing-portal` — LS 고객 포털 URL 반환
- [x] **LS-2** `screener/services/subscription.py` — LS webhook 구조로 재작성 (variant_id, renews_at, ends_at)
  - 상태 매핑: `active`/`on_trial`/`cancelled` → pro 유지, `expired`/`payment_failed` → free 즉시 전환
- [x] **LS-3** `screener/middleware.py` — PUBLIC_PATHS 갱신 (법적 페이지 + LS webhook)
- [x] **LS-4** `screener/main.py` — stripe_router 제거, lemon_router 등록, /pricing·/terms·/privacy·/refund 라우트 추가
- [x] **LS-5** `requirements.txt` — `stripe` 제거, `httpx` 추가
- [x] **LS-6** `.env.example` — `STRIPE_*` → `LEMONSQUEEZY_*` (API_KEY, STORE_ID, VARIANT_MONTHLY, VARIANT_YEARLY, WEBHOOK_SECRET)
- [x] **LS-7** `docs/DEPLOY_GUIDE.md` — LS 환경변수·배포 명령 갱신
- [x] **LS-8** 프론트 엔드포인트 동일 유지 (`/api/checkout`, `/api/billing-portal`, `/api/subscription`) — 내부만 교체

### 법적 페이지 4종 신규
- [x] **LEGAL-1** `screener/static/pricing.html` — 요금제 (Free vs Pro)
- [x] **LEGAL-2** `screener/static/terms.html` — 이용약관 (투자자문 아님 면책 포함)
- [x] **LEGAL-3** `screener/static/privacy.html` — 개인정보처리방침 (GDPR + 개인정보보호법)
- [x] **LEGAL-4** `screener/static/refund.html` — 환불정책 (14일 전액환불)
- [x] **LEGAL-5** `screener/static/legal_common.css` — 법적 페이지 공통 스타일

### 가격 최종 확정 (KRW, 전 세션의 USD 검토안 취소)
- Monthly ₩79,000 / Yearly ₩700,000 (약 26% 할인)
- `index.html` + `pricing.html` KRW 통일 — LS가 MoR로 통화 환산 처리

### 카테고리 tier 노출 (Free/Pro 시각화)
- [x] **TIER-1** `schemas.py` — `CategoryInfo.tier: str = "free"` 필드 추가
- [x] **TIER-2** `routes.py` — `/categories`에서 `FREE_CATEGORIES`(surge, bluechip, recommend, watchlist, etf, foreign_inst) 기준 tier 세팅 + **Free 먼저 정렬** (그룹 내 원래 순서 보존)
- [x] **TIER-3** `index.html` — `.chip.pro-locked` (dashed border, opacity 0.72) + `.chip-pro-badge` (PRO 라벨) 스타일

### index.html 프론트 확장 (+489 / -33줄)
- [x] **UI-1** Site Footer — 법적 링크 네비 + 브랜드 + 투자자문 면책문구
- [x] **UI-2** Watchlist Insights Panel (`.wl-insights`) — 관심종목 상단 스코어·시그널 요약 카드
- [x] **UI-3** Bulk Portfolio Modal (`#bulkPfModal`) — 관심종목을 현재가로 페이퍼 포트폴리오에 일괄 담기 (종목당 수량, 중복 스킵, 페이퍼 트레이딩 안내)
- [x] **UI-4** Contact Modal (`#contactModal`) — 문의 이메일 복사
- [x] **UI-5** Global Tooltip 강화 — 카테고리명·설명·컬럼 칩 3단 구조, word-break keep-all, max-width 320px
- [x] **UI-6** 테이블 컬럼 헤더 ⓘ (`.th-info`) — 컬럼 의미 툴팁 호버
- [x] **UI-7** info-tip popover (`.info-tip` + `.info-popover`) — 메트릭 설명 화살표 팝오버
- [x] **UI-8** Header/userInfo 모바일 대응 — flex-wrap + row-gap + max-width 말줄임, regime-badge nowrap

### 인프라
- [x] **INFRA-1** `cloudbuild.yaml` — `--set-env-vars` → `--update-env-vars` (수동 설정 env 보존, 배포 시 LS/Firebase 키 덮어쓰기 방지)

### 파일 집계
- 신규 6 / 삭제 1 / 수정 10 (`.env.example`, `cloudbuild.yaml`, `docs/DEPLOY_GUIDE.md`, `requirements.txt`, `screener/api/routes.py`, `screener/api/schemas.py`, `screener/main.py`, `screener/middleware.py`, `screener/services/subscription.py`, `screener/static/index.html`)
- 통계: +610 / -316

---

---

## 완료 (v7.2: Trial + 세션/IP 추적 + 관리자 대시보드 + Phase A 악용 방지, 2026-04-12 후반)

### 7일 무료 체험 (명시적 시작 방식)
- [x] **TRIAL-1** `screener/services/subscription.py` — `ensure_user_doc()` 분리, `start_trial()` 신규 함수
  - 가입 시점엔 tier=free 유지, 사용자가 "체험 시작" 명시 클릭 필요
  - Firestore 필드 추가: `email_verified`, `normalized_email`, `trial_started`, `trial_ends_at`, `trial_claimed_at`, `trial_blocked_reason`, `suspended`, `suspicious`, `admin_note`, `signup_ip_hash`, `is_admin_role`
- [x] **TRIAL-2** `POST /api/user/start-trial` — 악용 체크 후 Pro 승격, custom claims 갱신
- [x] **TRIAL-3** `GET /api/user/profile` — `tier / trial_active / trial_ends_at / trial_days_left / can_start_trial / trial_blocked_reason` 반환
- [x] **TRIAL-4** 프론트 트라이얼 배너 (상태별 5분기):
  - 이메일 미인증 → 인증 안내 + 재발송 버튼
  - 체험 가능 → "🎁 7일 무료 체험 시작" 버튼
  - 체험 중 → D-day 카운트다운 + 구독 CTA
  - 체험 만료 → 구독 유도
  - 악용 차단 → 차단 사유 + 구독 유도
- [x] **TRIAL-5** Pro 잠금 모달에 체험 시작 CTA 조건부 노출 (`showProLockModal` async)

### 세션/IP 추적 (동시접속 제한 + 어뷰징 감지)
- [x] **SEC-1** `screener/services/security.py` 신규
  - `register_session()` — 동시접속 ≥`MAX_ACTIVE_SESSIONS`(기본 2) 시 오래된 세션 제거
  - `heartbeat_session()` — 무효 세션 감지 시 클라이언트 로그아웃 지시
  - `record_login()` — login_history 서브컬렉션 기록
  - 30일 unique IP ≥4 경고, ≥5 suspicious 플래그
- [x] **SEC-2** `POST /api/auth/session-start`·`heartbeat`·`session-end` 엔드포인트
- [x] **SEC-3** 프론트 — 로그인 직후 session-start 호출, 5분마다 heartbeat, 경고/강제 로그아웃 토스트
- [x] **SEC-4** `middleware.py` — `suspended=true` 계정 전면 차단 (403)

### Phase A 악용 방지 (이메일 인증 + 중복/일회용 차단)
- [x] **ABUSE-1** 회원가입 직후 `sendEmailVerification()` 자동 호출
- [x] **ABUSE-2** 60초 간격 `user.reload()` — 인증 완료 감지 후 토큰 갱신
- [x] **ABUSE-3** 일회용 메일 도메인 블랙리스트 (70+ 도메인 + 키워드 매칭: `tempmail`, `10minute`, `disposable`, `throwaway`…)
- [x] **ABUSE-4** 이메일 정규화 (`normalize_email`) — Gmail 점/+alias 제거, googlemail→gmail
- [x] **ABUSE-5** `normalized_email` 중복 체크 (이미 trial 받은 계정 방지)
- [x] **ABUSE-6** `trial_ips` 컬렉션 — 24h 내 같은 IP(해시)에서 2번째 계정 trial 차단
- [x] **ABUSE-7** `privacy.html` §1.4 IP 수집 목적 고지 추가

### 관리자 대시보드 `/admin`
- [x] **ADMIN-1** `screener/api/admin_routes.py` 신규 — prefix `/api/admin`
  - `GET /users?filter=all|suspicious|suspended|trial|pro|free`
  - `GET /users/{uid}` — 로그인이력(최근 30) + 활성세션 + 30일 unique IP
  - `GET /stats` — 전체/pro/free/체험중/의심/정지 카운트
  - `POST /users/{uid}/suspend` — 정지 + 모든 활성 세션 제거
  - `POST /users/{uid}/unsuspend`
  - `POST /users/{uid}/extend-trial` — 체험 연장 (1~90일)
  - `POST /users/{uid}/note` — 관리자 메모
- [x] **ADMIN-2** `screener/static/admin.html` 신규 — 인증 게이트 (Firebase + Admin Key 지원)
- [x] **ADMIN-3** 접근 제어 — `ADMIN_EMAILS` 환경변수 일치 이메일 또는 `X-Admin-Key` 헤더
- [x] **ADMIN-4** 관리자 이메일 자동 Pro 승격 (middleware + ensure_user_doc 통합)

### 포트폴리오 UX 개선
- [x] **PF-1** 관심종목 인사이트 각 row에 ✓/＋ 토글 버튼 (`wliTogglePortfolio`)
- [x] **PF-2** 메인 테이블 row에 ＋/✓ 버튼 (관심종목 카테고리 한정)
- [x] **PF-3** 개별 담기 모달 (`#addPfModal`) — 수량·매수가·예상 금액 실시간 계산
- [x] **PF-4** 포트폴리오 추가 폼 전면 개편 — 종목명/코드 통합 검색 + datalist autocomplete + 현재가 자동 입력
- [x] **PF-5** `GET /api/all-stocks?q=&limit=` — 경량 자동완성 전용 엔드포인트
- [x] **PF-6** 비로그인 시 포트폴리오 모달 게이트 (로그인 모달로 리다이렉트)
- [x] **PF-7** `refreshPortfolio` 방어 렌더 (summary/holdings undefined 가드, 403/upgrade 처리)
- [x] **PF-8** `portfolio/risk` 섹터 라벨 sanitizer — mojibake 시 "기타"/"ETF" 폴백

### 헤더/CTA/온보딩
- [x] **UX-1** 헤더 `🔐 로그인` 파란 그라디언트 버튼 (기본 표시)
- [x] **UX-2** 게스트 배너 "회원가입 후 7일 Pro 무료 체험" + 회원가입 CTA
- [x] **UX-3** 로그아웃 후 `location.replace('/')` 강제 — 이전 세션 상태 완전 소거
- [x] **UX-4** `_loadTrialBanner` / `loadSubscriptionStatus` race guard (expectedUser 비교)
- [x] **UX-5** Pro-locked 칩 클릭 사전 차단 (`selectCategory` early return)
- [x] **UX-6** `selectGroup` 그룹 전환 시 현재 카테고리가 잠금이면 첫 Free로 자동 선택
- [x] **UX-7** `/api/scan` 403 응답 시 Free 카테고리로 자동 복귀

### 인프라
- [x] **INFRA-2** Secret Manager API 활성화 (`all-of-asset` 프로젝트)
- [x] **INFRA-3** `firebase-key` 시크릿 생성 + Cloud Run SA `secretmanager.secretAccessor` 권한
- [x] **INFRA-4** 환경변수 설정: `AUTH_ENABLED=true`, `FIREBASE_WEB_API_KEY`, `FIREBASE_PROJECT_ID`, `ADMIN_EMAILS`
- [x] **INFRA-5** 시크릿 마운트: `FIREBASE_CREDENTIALS=firebase-key:latest`
- [x] **INFRA-6** Cloud Run IAM `roles/run.invoker` allUsers 부여 (ingress 403 해결)

### 정합성 버그 수정 (v7.2 후반 세션)
- [x] **FIX-1** `user_routes.py` dead import 제거
- [x] **FIX-2** `ensure_user_doc` — admin 이메일 신규 사용자 tier=pro/email_verified=true로 저장
- [x] **FIX-3** `showProLockModal` 깜빡임 — fetch 완료 후 모달 오픈
- [x] **FIX-4** `_syncRowPfBtn` — 포트폴리오 모달 열려있으면 자동 `refreshPortfolio`
- [x] **FIX-5** `admin.html` `loadStats` 403/오류 명확화 + 게이트 복귀
- [x] **FIX-6** `admin.html` Firebase SDK 중복 초기화 방어

### 파일 변경 (v7.2 세션 누적)
신규: `services/security.py`, `api/user_routes.py`, `api/admin_routes.py`, `static/admin.html`
수정: `services/subscription.py`, `middleware.py`, `api/lemon_routes.py`, `api/routes.py`, `api/schemas.py`, `main.py`, `static/index.html`, `static/privacy.html`, `cloudbuild.yaml`, `docs/DEPLOY_GUIDE.md`

---

## 완료 (v7.3: 완성도 — 전문가 분석·SEO·UX 리뉴얼, 2026-04-12 후반)

### 포트폴리오 전문가 분석 리뉴얼
- [x] **PF-EX-1** `/api/portfolio/risk` 전면 확장 — `holdings` 받아 **평가금 가중 비중** 계산
- [x] **PF-EX-2** 건강도 점수(0~100) + 등급(S/A/B/C/D/F) + 자동 조언
- [x] **PF-EX-3** 연 변동성·연 수익률·샤프 비율·최대낙폭(MDD)·평균 상관계수·Top 종목 집중도
- [x] **PF-EX-4** 섹터별·시장별 비중 (KR/US), 종목별 비중 정렬
- [x] **PF-EX-5** 8개 룰 기반 자동 추천 (`recommendations`: success/info/warning/danger)
- [x] **PF-EX-6** 프론트 SVG 도넛 차트 + 종목 비중 가중 바 + 상관관계 Top 4 + 시장 분할 카드
- [x] **PF-EX-7** 건강도 등급 배지 (그라디언트 6색) + 진행바

### 종목 상세 모달 고도화
- [x] **SD-1** "🎯 이 종목의 매수 포인트" 상단 하이라이트 — 7개 자동 시그널 감지 로직
- [x] **SD-2** 종목별 메모 입력 (localStorage, 400ms debounce 자동 저장)
- [x] **SD-3** 종목별 태그 추가/제거 (localStorage, 20자 제한)

### 알림 시그널 (4종)
- [x] **AL-1** 🎯 관심종목 매수점수 진입 (50/70점, 중복 방지 — 벗어났다 다시 오를 때 재알림)
- [x] **AL-2** 🚀 관심종목 급등 시그널 (예보 4+/돌파 3+/동반매수)
- [x] **AL-3** 📊 관심종목 등락률 (±X%)
- [x] **AL-4** 🔥 전체 급등주 발생 (일 1회)
- [x] **AL-5** 토스트 + Browser Notification 동시. `alertSeen` localStorage 중복 필터

### 데이터 신선도 배지
- [x] **FR-1** KST 시간 기반 장 상태 자동 감지: 🟢 장중 (09:00~15:30) / 🟡 장전 / 🟠 장후 / ⚪ 장마감/휴장일
- [x] **FR-2** 장중 30분+ 업데이트 없으면 경고 색상 전환
- [x] **FR-3** 장중 pulse 애니메이션 배지

### 모바일 카드뷰
- [x] **MC-1** 테이블/카드 뷰 토글 버튼 (`setViewMode` localStorage 저장)
- [x] **MC-2** 모바일(<=640px) 기본 카드뷰, 데스크톱 기본 표
- [x] **MC-3** 카드 구성: 종목명·코드·시장·현재가·등락률·관심/담기·뱃지·메타 3개

### CSV/Excel 개선
- [x] **EX-1** UTF-8 BOM 명시 (Excel 한글 깨짐 방지)
- [x] **EX-2** RFC 5987 파일명 인코딩 (`filename*=UTF-8''...`) + ASCII fallback 병기
- [x] **EX-3** 컬럼명 한국어 매핑 (`_EXPORT_COLUMNS`) 검증

### 백테스트 리포트 개선
- [x] **BT-1** 적중률 진행바 + 50% 기준선 시각화
- [x] **BT-2** "무작위 기준 대비 ±X%p" 상대 성과 텍스트

### 🌊 섹터 자금흐름 트리맵
- [x] **SF-1** Squarified 재귀 분할 트리맵 (SVG/div 기반)
- [x] **SF-2** 사각형 크기 = 자금 규모, 색 = 방향, 투명도 = 강도
- [x] **SF-3** 트리맵/그리드 뷰 토글 + 리사이즈 대응

### 📰 SEO 공개 페이지 (`screener/api/rank_page.py` 신규)
- [x] **SEO-1** `/rank` / `/rank/today` → 오늘 날짜 리다이렉트
- [x] **SEO-2** `/rank/<YYYY-MM-DD>` — 5섹션 TOP 리포트 (종합추천/급등예보/돌파/오늘급등/동반매수)
- [x] **SEO-3** `/backtest-report` — 시그널별 적중률 공개 리포트 + 점수별 성과 추적
- [x] **SEO-4** `/sitemap.xml` — 검색엔진용 사이트맵
- [x] **SEO-5** `/robots.txt` — 크롤링 허용/차단 경로
- [x] **SEO-6** 완비된 메타 태그 (`og:*`, `twitter:*`, canonical, JSON-LD Article 구조화 데이터)
- [x] **SEO-7** CDN 친화 `Cache-Control: public, max-age=600~1800`
- [x] **SEO-8** 하단 CTA "무료로 시작하기" 본 앱 유도

### 관심종목 고도화
- [x] **WL-1** 종목별 태그 저장/삭제 UI
- [x] **WL-2** 관심종목 카테고리 상단 태그 필터 칩 바 (자동 생성, 개수 표시)
- [x] **WL-3** 태그 선택 시 관심종목 필터링

### 🔥 홈 첫 진입 개선 (원래 Phase 1 항목이었으나 누락 → 별도 구현)
- [x] **HOME-1** 헤더 직하 "오늘의 TOP 픽" 섹션 — 비로그인 포함 공개
- [x] **HOME-2** 💎 AI 추천 TOP 3 + 🚀 급등 예보 TOP 2 병렬 조회
- [x] **HOME-3** 카드 클릭 → 종목 상세 모달 (매수 포인트 하이라이트)
- [x] **HOME-4** 순위 배지 (#1 금색 / #2 은색 / #3 동색)
- [x] **HOME-5** "전체 보기 →" 버튼 → 종합 추천 카테고리 이동 + 상단 스크롤
- [x] **HOME-6** 접기/펼치기 (`topPicksCollapsed` localStorage 기억)
- [x] **HOME-7** 지역 전환(KR/US) 시 재로드

### 🧹 기타 UX 정합성 수정
- [x] **UX-8** 토스트 위치 오른쪽 → 상단 중앙 (가독성 개선)
- [x] **UX-9** 뷰 토글 버튼 **항상 표시** (기존 ≤640px 제한 제거)
- [x] **UX-10** 자동 카드뷰 기준 **≤900px** (좁은 태블릿/창 포함)
- [x] **UX-11** 페이지당 종목 100→50 (모바일 스크롤 완화)
- [x] **UX-12** 테이블 헤더 **sticky** + 가로 스크롤 그라디언트 힌트
- [x] **UX-13** 관심종목 인사이트 **compact 리뉴얼** — 시그널 있는 종목만 표시, 접기 가능
- [x] **UX-14** 모달 그리드 공간 낭비 개선 — label/value 간격 최적화
- [x] **UX-15** 펀더멘탈 탭 — 값 있는 항목만 표시, 전부 없으면 명확한 안내

### 🔐 로그인 게이트 강화
- [x] **GATE-1** `getWatchlist`/`getPortfolio` 자체 로그인 가드 — 비로그인 시 무조건 빈 배열
- [x] **GATE-2** 로그아웃 시 모든 사용자 데이터 localStorage 클리어
- [x] **GATE-3** 로그아웃 시 열린 모달 7종 강제 닫기
- [x] **GATE-4** 관심종목 카테고리 비로그인 상태 — 큰 로그인 유도 카드
- [x] **GATE-5** 메모/태그 (`wlnote:*`, `wltag:*`) 클라우드 동기화 — `/api/user/meta`

### ☁️ 클라우드 동기화 (POST-2 이행)
- [x] **CLOUD-1** `/api/user/watchlist` (GET/POST) — `users/{uid}.watchlist`
- [x] **CLOUD-2** `/api/user/holdings` (GET/POST) — `users/{uid}.holdings`
- [x] **CLOUD-3** `/api/user/meta` (GET/POST) — `users/{uid}.wl_meta.{notes,tags}`
- [x] **CLOUD-4** 로그인 시 자동 pull + 로컬 병합 (이전 세션 잔재 upload)
- [x] **CLOUD-5** 변경 시 800ms debounce 자동 sync

### 포트폴리오 UX 버그 수정
- [x] **FIX-A** 로그인 안 하면 포트폴리오 모달 자체가 열리지 않음 (로그인 게이트)
- [x] **FIX-B** `refreshPortfolio` 방어 렌더 (summary/holdings undefined 가드, 403/upgrade 처리)
- [x] **FIX-C** 관심종목 인사이트 토글 후 포트폴리오 모달 자동 갱신 (`_syncRowPfBtn`)
- [x] **FIX-D** 로그아웃 race 방지 (`location.replace('/')` 강제 + `expectedUser` 가드)
- [x] **FIX-E** 관리자 프로필 일관성 (middleware + user_profile + subscription 통합)

### 파일 변경 (v7.3 세션)
신규: `api/rank_page.py` (랜딩/백테스트 리포트/sitemap/robots)
수정: `static/index.html`(대폭), `api/routes.py` (portfolio/risk 확장, CSV BOM), `api/user_routes.py`, `services/subscription.py`, `middleware.py` (public paths), `main.py` (router 등록)

---

## 다음 단계 — 서비스 런칭 준비

### 🔴 필수 (런칭 전 완료)
- [ ] **LAUNCH-1** 법적 페이지 배포 (LS 승인 선결조건)
  - `gcloud builds submit --config=cloudbuild.yaml`
  - 접속 확인: `/pricing`, `/terms`, `/privacy`, `/refund`
- [ ] **LAUNCH-2** Lemon Squeezy 설정
  - https://lemonsqueezy.com/signup
  - Store 생성 → Products → Variant 2개 (월 ₩79,000 / 연 ₩700,000 KRW)
  - Settings → API → API Key 발급
  - Settings → Webhooks → `/api/webhooks/lemonsqueezy` 등록 (Signing secret 복사)
  - 승인 소요: 당일~1일
  - 테스트 카드로 전체 플로우 검증
- [ ] **LAUNCH-3** Firebase Console 설정
  - Authentication → Sign-in method → Google 활성화
  - 프로젝트 설정 → 웹 앱에서 `apiKey` 복사 (= `FIREBASE_WEB_API_KEY`)
  - Authentication → Settings → Authorized domains에 Cloud Run URL 추가
- [ ] **LAUNCH-4** Cloud Run 환경변수 + Secret 업데이트
  - `AUTH_ENABLED=true`
  - `FIREBASE_WEB_API_KEY`, `FIREBASE_PROJECT_ID=stock-search-program`
  - `LEMONSQUEEZY_STORE_ID`, `LEMONSQUEEZY_VARIANT_MONTHLY`, `LEMONSQUEEZY_VARIANT_YEARLY`
  - Secret: `lemon-ls-api-key`, `lemon-ls-webhook-secret`
  - 상세 명령: docs/DEPLOY_GUIDE.md §4
- [ ] **LAUNCH-5** 도메인 + HTTPS (선택, 가이드: docs/DEPLOY_GUIDE.md §3)
- [ ] **LAUNCH-6** Cloud Run 재배포 (`httpx` 포함, `stripe` 제거된 requirements로)
- [ ] **LAUNCH-7** E2E 테스트 — 회원가입 → Free 제한 → Pro 카테고리 chip 잠금 표시 → 결제 → 해금 → 관심종목 → Bulk 포트폴리오 담기 → 해지 → Free 복귀

### 🟠 런칭 직전 — 마케팅/성장 (v7.3 이후 제안)
- [ ] **GROW-1** Google Search Console 등록 + `/sitemap.xml` 제출 — 색인 시작
- [ ] **GROW-2** 네이버 웹마스터 도구 등록 + `/sitemap.xml` 제출 — 한국 유입 (GROW-1보다 중요)
- [ ] **GROW-3** Lemon Squeezy 승인 재신청 — 랜딩·백테스트 리포트·법적페이지 모두 준비됐으니 심사 통과 가능성↑
- [ ] **GROW-4** 리퍼럴 코드 시스템 — 추천인/피추천인 체험 연장 (기존 trial 인프라 활용)
- [ ] **GROW-5** 트라이얼 D-2 이메일 알림 — 전환율 핵심 (Firebase Functions or Cloud Scheduler + SendGrid/Mailgun)
- [ ] **GROW-6** 트위터/오픈그래프 이미지 — `/rank/<date>` 공유 시 썸네일 노출 (og:image 생성)

### 🟡 권장 (런칭 직후)
- [x] **POST-1** 랜딩 페이지 — `/rank/<date>` + `/backtest-report`로 대체 구현 완료
- [ ] **POST-2** 관심종목 클라우드 동기화 — Firestore `users/{uid}/watchlist` (localStorage → 크로스 디바이스)
- [ ] **POST-3** 비밀번호 재설정 플로우 (`sendPasswordResetEmail`)
- [x] **POST-4** 관리자 대시보드 — `/admin` 완료 (v7.2)

### 🟢 향후 (안정화 후)
- [ ] **FUTURE-1** 데스크톱 인스톨러 (Inno Setup)
- [ ] **FUTURE-2** 자동 업데이트 체계
- [ ] **FUTURE-3** KIS API 연동 (실시간 호가/체결)
- [ ] **FUTURE-4** 뉴스/공시 연동
- [ ] **FUTURE-5** 실적 캘린더 (yfinance earningsDate / DART)

### 미진행 — 외부 의존
- [ ] **V6-BE-1** pykrx 기관 유형별 분리 — 연기금 vs 투신 (pykrx 정상화 대기)
- [ ] **V6-BE-2** 실적 캘린더 — yfinance earningsDate / DART API

### 데이터 품질 (낮은 우선순위)
- [ ] **T-J8** US div_years 항상 0 — 미국 배당 연속 연수 수집 누락
- [ ] **T-J12** schedule-status 모니터링 빈 값
- [ ] **T-J13** sectors 엔드포인트 `name: 0` 잘못된 항목
- [ ] **T-J16** schedule-status 타임스탬프 UTC→KST 불일치

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
# 서버 기본
RUN_MODE=server
COLLECT_MODE=readonly|full
PORT=8501
ADMIN_KEY=

# Firebase
FIREBASE_KEY_PATH=
FIREBASE_CREDENTIALS=
AUTH_ENABLED=false
FIREBASE_WEB_API_KEY=
FIREBASE_PROJECT_ID=

# Lemon Squeezy (v7.1 — Stripe 대체)
LEMONSQUEEZY_API_KEY=
LEMONSQUEEZY_STORE_ID=
LEMONSQUEEZY_VARIANT_MONTHLY=
LEMONSQUEEZY_VARIANT_YEARLY=
LEMONSQUEEZY_WEBHOOK_SECRET=

# 기타
CLOUD_RUN_URL=https://stock-screener-119320994983.asia-northeast3.run.app
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```
