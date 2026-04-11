# 다음 작업 목록

> 업데이트: 2026-04-11 (v7.0 상용화)

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

## 다음 단계 — 서비스 런칭 준비

### 🔴 필수 (런칭 전 완료)
- [ ] **LAUNCH-1** Stripe Dashboard 설정
  - 상품 생성 (Stock Screener Pro)
  - 가격 생성: 월간 ₩9,900 / 연간 ₩99,000 (KRW, zero-decimal)
  - Webhook 엔드포인트 등록: `https://{domain}/api/webhooks/stripe`
  - 테스트 모드에서 카드(4242 4242 4242 4242)로 전체 플로우 검증
- [ ] **LAUNCH-2** Firebase Console 설정
  - Google 로그인 프로바이더 활성화
  - 승인된 도메인 추가
  - `FIREBASE_WEB_API_KEY` 확인
- [ ] **LAUNCH-3** Cloud Run 환경변수 설정
  - `AUTH_ENABLED=true`
  - `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
  - `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`
  - `FIREBASE_WEB_API_KEY`, `FIREBASE_PROJECT_ID`
- [ ] **LAUNCH-4** 도메인 + HTTPS 설정 (가이드: docs/DEPLOY_GUIDE.md)
- [ ] **LAUNCH-5** Cloud Run 재배포 (stripe 패키지 포함)
- [ ] **LAUNCH-6** E2E 테스트 — 회원가입 → Free 제한 확인 → 결제 → Pro 해금 → 해지

### 🟡 권장 (런칭 직후)
- [ ] **POST-1** 랜딩 페이지 — 서비스 소개 + 가격 안내 + CTA
- [ ] **POST-2** 관심종목 클라우드 동기화 — Firestore `users/{uid}/watchlist`
- [ ] **POST-3** 이메일 인증 + 비밀번호 재설정 플로우
- [ ] **POST-4** 관리자 대시보드 — 사용자/구독/매출 현황

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

# Stripe (v7.0 추가)
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_MONTHLY=price_...
STRIPE_PRICE_YEARLY=price_...

# 기타
CLOUD_RUN_URL=https://stock-screener-119320994983.asia-northeast3.run.app
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```
