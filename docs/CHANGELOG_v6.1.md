# Changelog — v6.1 (2026-04-10)

> v6.0 백엔드에 대응하는 프론트엔드 전면 구현 + 데이터 품질 개선

---

## 프론트엔드 (index.html)

### 백테스트 리디자인

- 5/10/20/60일 **다기간 탭** — 기간별 시그널 성과를 한눈에 비교
- **Sharpe Ratio**, **Profit Factor**, **Max Drawdown** 표시 — 단순 적중률 넘어 위험조정수익률 제공
- **벤치마크 대비 알파** 배지 — 시그널 초과수익 녹색/적색 표시
- **점수별 성과 추적** — buy_70plus, pre_surge, breakout, dual_buy 적중률 카드

### 수급 분석

- **수급 게이지 바** — 외국인/기관 매수세를 결과 상단에 프로그레스바로 표시
- **수급 등급 badge** — 강력매수(적)/매수세(황)/중립/매도세/강력매도(청) 5단계
- **외국인 연속매수일** 컬럼 — +N일(적)/-N일(청) 색상 표시
- **동반매수 아이콘** — 외국인+기관 동시 순매수 표시

### 종목 상세 모달

- **4탭 구조** — 기본 | 펀더멘탈 | 수급 | 리스크
- **펀더멘탈 탭** — Forward PER, PEG, EV/EBITDA, 순이익률, 영업이익률, FCF Yield, 부채비율, 매출성장률, 목표주가, 목표괴리율, PER, PBR
- **수급 탭** — 외국인/기관 순매수, 연속일수, 수급 강도, 동반매수, 수급 등급
- **리스크 탭** — 변동성(20일), ATR(14일), 리스크 등급, 투자 비중 권장, 골든크로스(단기/장기), 돌파점수, 정배열

### 시장 레짐 인디케이터

- **헤더 배지** — 강세장(녹)/약세장(적)/횡보장(황) + 신뢰도 tooltip

### 종목 비교 (신규)

- **카드형 비교뷰** — 2~5개 종목 나란히, 14개 핵심 지표 비교
- PER, PBR, ROE, 배당률, 종합점수, 등급, RSI, 리스크, EV/EBITDA, 순이익률, 부채비율, 목표괴리율, 수급등급, 투자비중

### 섹터 자금흐름 (신규)

- **테마그룹별 유입/유출 그리드** — 외국인+기관 순매수 합계
- 유입(녹색 테두리) / 유출(적색 테두리) + 종목 수 표시

### 포트폴리오 리스크 (강화)

- **상관계수 테이블** — 종목 간 상관계수 히트맵 (고/중/저 색상)
- **연간 변동성** — 포트폴리오 전체 변동성 (30%↑ 적, 20%↑ 황, 기본 녹)
- **섹터 분포 바** — 섹터별 비중 가로 바 차트
- **편중 경고** — 60% 이상 집중 시 경고 메시지

### COL_DEFS 확장 (+15개 v6 필드)

| 필드 | 라벨 |
|------|------|
| foreign_consecutive | 외국인연속 |
| supply_intensity | 수급강도 |
| dual_buy | 동반매수 |
| supply_grade | 수급등급 |
| forward_pe | Forward PER |
| peg_ratio | PEG |
| ev_ebitda | EV/EBITDA |
| profit_margin | 순이익률 |
| operating_margin | 영업이익률 |
| fcf_yield | FCF Yield |
| debt_equity | 부채비율 |
| revenue_growth | 매출성장률 |
| target_price | 목표주가 |
| target_upside | 목표괴리율 |
| position_size | 투자비중 |

---

## 백엔드 개선

### backtest.py

- API 응답 `windows` 키 형식 `"5d"/"10d"/"20d"/"60d"` 문자열로 통일
- 기본 5d 통계를 최상위에도 포함 (하위 호환성)

### metrics.py — 데이터 품질

- **risk_grade 시장별 분리** — KR(5%/8% 높음/매우높음), US(3%/5%) 별도 기준
  - 히스토리 미수집 종목(volatility=0) → "데이터없음" 표시
- **ROE 캡 처리** — `clip(-100, 200)` 적용하여 US ROE 7000% 등 이상치 방지

### screener.py — 데이터 품질

- `oversold` 카테고리: `rsi_min=1` 추가 → rsi=0(히스토리 없는 종목) 필터 제외
- `turnaround` 카테고리: `rsi_min=1` 추가 → 동일 이슈 수정

---

## 트레이더 실사용 이슈 수정 (7건)

| # | 이슈 | 수정 |
|---|------|------|
| UX-1 | 검색이 대형주만 | 3개 카테고리 병렬 검색으로 커버리지 확대 |
| UX-2 | 퀄리티주 KR 0건 | "해외 전용" desc + 빈 결과 안내 메시지 |
| UX-3 | buy_score 히스토리 없는 종목 부풀림 | RSI=0+MA20=0 → 점수 70% 감점 |
| UX-4 | 백테스트/레짐 API 캐싱 없음 | 5분 TTL 간이 캐시 |
| UX-5 | 비교 잘못된 코드 무시 | not_found 목록 반환 + 토스트 |
| UX-6 | 포트폴리오 리스크 1종목 무반응 | "2개 이상 필요" 안내 |
| UX-7 | 온보딩 자동 팝업 | 비활성화 (? 키 수동) |

---

## KR 섹터 분류 (T-J7)

- 네이버금융 크롤링에 업종 추출 추가 (`_fetch_single_fundamental`)
- `apply_fundamentals`에서 sector/industry 자동 적용
- `fetch_daily_snapshot`에 sector/industry 초기값 빈 문자열 추가

---

## 히스토리 커버리지 확대 (T-J10)

| 항목 | Before | After |
|------|--------|-------|
| KR 시총 상위 | 300 | 600 |
| KR 거래량 상위 | 200 | 400 |
| US 시총 상위 | 150 | 300 |
| US 거래량 상위 | 100 | 200 |
| 타임아웃 | 10초 | 20초 |
| 실패 로깅 | 없음 | debug 로깅 추가 |

---

## 배포

| 대상 | 상태 | 소요 |
|------|------|------|
| Cloud Run 웹 서비스 | SUCCESS | 5분 5초 |
| Cloud Run Collector Jobs | SUCCESS | 4분 34초 |
| 라이브 확인 | 200 OK, 3,495종목, Phase 3 | - |

---

## 변경 파일 (전체 5개 커밋)

| 파일 | 줄 수 | 설명 |
|------|-------|------|
| `screener/static/index.html` | +430 | 15개 v6 UI + 트레이더 UX 7건 + CSS |
| `screener/api/routes.py` | +46 | API 캐싱 + 비교 피드백 + 퀄리티 안내 |
| `screener/core/metrics.py` | +25 | risk_grade 분리 + ROE 캡 + buy_score 감점 |
| `screener/core/backtest.py` | +14 | windows 키 형식 통일 |
| `screener/core/screener.py` | +4 | rsi_min=1 + 퀄리티 desc |
| `screener/core/data_fetcher.py` | +45 | KR 섹터 크롤링 + 타임아웃 확대 |
| `collector.py` | +6 | 히스토리 타겟 확대 |
| `docs/DEPLOY_GUIDE.md` | 신규 | Cloud Run + 도메인 + HTTPS 가이드 |
| `docs/CHANGELOG_v6.1.md` | 신규 | 본 문서 |
| `docs/TODO.md` | 갱신 | Step 11 추가 |
| `docs/NEXT_TODO.md` | 갱신 | 전체 상태 업데이트 |
| **합계** | **+700줄** | **11개 파일, 5개 커밋** |

---

## 다음 작업

- [ ] 도메인 + HTTPS (가이드: docs/DEPLOY_GUIDE.md)
- [ ] 결제 연동 (Stripe / 토스페이먼츠)
- [ ] US div_years 수집 (T-J8)
- [ ] 실적 캘린더 (V6-BE-2)
