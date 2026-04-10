"""파생 지표 계산: 이동평균, RSI, 거래량 비율 + 예측 시그널 + 리스크."""

import numpy as np
import pandas as pd
from loguru import logger

from screener.config import (
    SURGE_CHANGE_PCT, SURGE_VOLUME_RATIO, SURGE_MIN_SCORE,
    PRE_SURGE_MIN_SCORE,
)


# ──────────────────────────────────────────────
# 이동평균 + 기술 시그널
# ──────────────────────────────────────────────

def calculate_moving_averages(
    history: pd.DataFrame,
    snapshot: pd.DataFrame,
    windows: list[int] = [5, 20, 60],
) -> pd.DataFrame:
    """이동평균선, 거래량 평균, 연속 상승일수 계산."""
    if history.empty:
        return snapshot

    close_pivot = history.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    ).sort_index()

    volume_pivot = history.pivot_table(
        index="date", columns="ticker", values="volume", aggfunc="last"
    ).sort_index()

    high_pivot = history.pivot_table(
        index="date", columns="ticker", values="high", aggfunc="last"
    ).sort_index()

    low_pivot = history.pivot_table(
        index="date", columns="ticker", values="low", aggfunc="last"
    ).sort_index()

    ma_data = {}
    for w in windows:
        ma_data[f"ma{w}"] = close_pivot.tail(w).mean()

    ma_data["avg_volume_20"] = volume_pivot.tail(20).mean()
    ma_data["consecutive_gains"] = _calc_consecutive_gains(close_pivot)

    # ── 예측 시그널용 추가 지표 ──
    ma_data["volume_trend"] = _calc_volume_trend(volume_pivot)
    ma_data["ma_squeeze"] = _calc_ma_squeeze(close_pivot, windows)

    # ── 리스크 지표 ──
    ma_data["volatility_20d"] = _calc_volatility(close_pivot, period=20)
    ma_data["atr_14"] = _calc_atr(high_pivot, low_pivot, close_pivot, period=14)

    ma_df = pd.DataFrame(ma_data)
    ma_df.index.name = "ticker"
    ma_df = ma_df.reset_index()

    # 기존 snapshot 컬럼과 충돌 시 suffixes로 처리
    existing_ma_cols = [c for c in ma_df.columns if c != "ticker" and c in snapshot.columns]
    if existing_ma_cols:
        snapshot = snapshot.drop(columns=existing_ma_cols, errors="ignore")

    result = snapshot.merge(ma_df, on="ticker", how="left")

    # NaN → 0 (히스토리에 없는 종목)
    for col in ma_df.columns:
        if col != "ticker" and col in result.columns:
            result[col] = result[col].fillna(0)

    # 거래량 비율
    if "volume_ratio" not in result.columns:
        result["volume_ratio"] = 0.0
    if "avg_volume_20" in result.columns:
        valid = result["avg_volume_20"] > 0
        result.loc[valid, "volume_ratio"] = (
            result.loc[valid, "volume"] / result.loc[valid, "avg_volume_20"]
        ).round(2)

    # 이동평균 대비 위치 (%)
    for w in windows:
        col = f"ma{w}"
        pct_col = f"vs_ma{w}_pct"
        result[pct_col] = 0.0
        if col in result.columns:
            valid_ma = result[col] > 0
            result.loc[valid_ma, pct_col] = (
                (result.loc[valid_ma, "close"] / result.loc[valid_ma, col] - 1) * 100
            ).round(2)

    # ── 골든크로스: 실제 교차 시점 감지 (단기 MA5/MA20) ──
    result["golden_cross"] = 0
    result["death_cross"] = 0
    if len(close_pivot) >= 20:
        ma5_series = close_pivot.rolling(5).mean()
        ma20_series = close_pivot.rolling(20).mean()
        # 전일 MA5<=MA20 → 당일 MA5>MA20 = 골든크로스
        gc_today = (ma5_series.iloc[-1] > ma20_series.iloc[-1])
        gc_yesterday = (ma5_series.iloc[-2] <= ma20_series.iloc[-2]) if len(close_pivot) >= 21 else pd.Series(False, index=close_pivot.columns)
        # 최근 5일 이내 골든크로스 발생 (교차 직후 구간 포함)
        gc_recent = pd.Series(False, index=close_pivot.columns)
        for i in range(-5, 0):
            if len(ma5_series) + i >= 1:
                crossed = (
                    (ma5_series.iloc[i] > ma20_series.iloc[i]) &
                    (ma5_series.iloc[i - 1] <= ma20_series.iloc[i - 1])
                )
                gc_recent = gc_recent | crossed
        gc_map = gc_recent.astype(int)
        gc_map.index.name = "ticker"
        result["golden_cross"] = result["ticker"].map(gc_map).fillna(0).astype(int)

        # 데드크로스: 최근 5일 이내 MA5가 MA20 하향 돌파
        dc_recent = pd.Series(False, index=close_pivot.columns)
        for i in range(-5, 0):
            if len(ma5_series) + i >= 1:
                crossed = (
                    (ma5_series.iloc[i] < ma20_series.iloc[i]) &
                    (ma5_series.iloc[i - 1] >= ma20_series.iloc[i - 1])
                )
                dc_recent = dc_recent | crossed
        dc_map = dc_recent.astype(int)
        dc_map.index.name = "ticker"
        result["death_cross"] = result["ticker"].map(dc_map).fillna(0).astype(int)

    # ── 골든크로스 (장기: MA20/MA60) ──
    result["golden_cross_long"] = 0
    if len(close_pivot) >= 60:
        ma20_s = close_pivot.rolling(20).mean()
        ma60_s = close_pivot.rolling(60).mean()
        gc_long_recent = pd.Series(False, index=close_pivot.columns)
        for i in range(-10, 0):
            if len(ma20_s) + i >= 1:
                crossed = (
                    (ma20_s.iloc[i] > ma60_s.iloc[i]) &
                    (ma20_s.iloc[i - 1] <= ma60_s.iloc[i - 1])
                )
                gc_long_recent = gc_long_recent | crossed
        gc_long_map = gc_long_recent.astype(int)
        gc_long_map.index.name = "ticker"
        result["golden_cross_long"] = result["ticker"].map(gc_long_map).fillna(0).astype(int)

    # 정배열 (5일 > 20일 > 60일)
    if all(f"ma{w}" in result.columns for w in [5, 20, 60]):
        result["ma_aligned"] = (
            (result["ma5"] > result["ma20"]) & (result["ma20"] > result["ma60"])
        ).astype(int)
    else:
        result["ma_aligned"] = 0

    # ── 매집 시그널: 거래량 증가 + 가격 변동 적음 + 연속성 ──
    result["accumulation"] = 0
    has_vr = result["volume_ratio"] > 0
    quiet_price = result["change_pct"].abs() < 2.0
    vol_up = result["volume_ratio"] >= 1.5
    vol_trend_ok = result["volume_trend"] >= 2  # 2일 이상 연속 거래량 증가 추가
    result.loc[has_vr & quiet_price & vol_up & vol_trend_ok, "accumulation"] = 1

    # ── 돌파 임박 점수 (0~4) ──
    result["breakout_score"] = 0
    # 52주 고가 5% 이내
    if "vs_high_52w" in result.columns:
        result.loc[result["vs_high_52w"] >= -5, "breakout_score"] += 1
    # 거래량 증가 추세
    if "volume_trend" in result.columns:
        result.loc[result["volume_trend"] >= 2, "breakout_score"] += 1
    # MA 정배열
    result.loc[result["ma_aligned"] == 1, "breakout_score"] += 1
    # 골든크로스
    result.loc[result["golden_cross"] == 1, "breakout_score"] += 1

    # ── 리스크 등급 (시장별 변동성 기준 분리) ──
    result["risk_grade"] = "보통"
    if "volatility_20d" in result.columns and "market" in result.columns:
        is_us = result["market"].isin(["NASDAQ", "S&P500"])
        is_kr = ~is_us
        vol = result["volatility_20d"]
        # 히스토리 미수집 종목(volatility=0) → "데이터없음"
        result.loc[vol <= 0, "risk_grade"] = "데이터없음"
        # KR: 변동성이 상대적으로 높으므로 기준 완화
        result.loc[is_kr & (vol > 0) & (vol <= 2.5), "risk_grade"] = "낮음"
        result.loc[is_kr & (vol > 2.5) & (vol < 5.0), "risk_grade"] = "보통"
        result.loc[is_kr & (vol >= 5.0) & (vol < 8.0), "risk_grade"] = "높음"
        result.loc[is_kr & (vol >= 8.0), "risk_grade"] = "매우높음"
        # US: 변동성이 상대적으로 낮으므로 기준 엄격
        result.loc[is_us & (vol > 0) & (vol <= 1.5), "risk_grade"] = "낮음"
        result.loc[is_us & (vol > 1.5) & (vol < 3.0), "risk_grade"] = "보통"
        result.loc[is_us & (vol >= 3.0) & (vol < 5.0), "risk_grade"] = "높음"
        result.loc[is_us & (vol >= 5.0), "risk_grade"] = "매우높음"

    logger.info("이동평균 + 예측 시그널 + 리스크 지표 계산 완료")
    return result


# ──────────────────────────────────────────────
# RSI — Wilder's EMA (정석)
# ──────────────────────────────────────────────

def calculate_rsi(history: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI(상대강도지수) 계산 — Wilder's Smoothed EMA 방식.

    증권사 HTS/MTS와 동일한 결과를 산출하기 위해
    단순이동평균(SMA)이 아닌 Wilder의 지수이동평균 사용.
    """
    if history.empty:
        return pd.Series(dtype=float)

    close_pivot = history.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    ).sort_index()

    delta = close_pivot.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Wilder's Smoothed EMA: alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # 마지막 날짜의 RSI 반환
    return rsi.iloc[-1] if len(rsi) > 0 else pd.Series(dtype=float)


# ──────────────────────────────────────────────
# 52주 고저 — 실제 52주(250거래일) 기반
# ──────────────────────────────────────────────

def calculate_52week(history: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """52주 최고가/최저가 대비 현재 위치(%).

    HISTORY_DAYS=250 이상이면 실제 52주 데이터 기반.
    그보다 짧으면 보유 데이터 범위 내에서 계산.
    """
    if history.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    close_pivot = history.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    ).sort_index()

    high_52w = close_pivot.max()
    low_52w = close_pivot.min()
    current = close_pivot.iloc[-1]

    vs_high = ((current / high_52w.replace(0, np.nan)) - 1) * 100
    vs_low = ((current / low_52w.replace(0, np.nan)) - 1) * 100

    return vs_high.round(2), vs_low.round(2)




# ──────────────────────────────────────────────
# 급등 탐지 + 예보 (강화)
# ──────────────────────────────────────────────

def detect_surging_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """급등 예보: 아직 급등하지 않았지만 급등 전 징후가 있는 종목.

    v5.4 강화: 조건 변별력 향상, 최소 점수 4/5로 상향.
    """
    df = df.copy()
    df["surge_score"] = 0

    # 기존 급등 감지 (이미 오른 종목) — 참고용으로 유지
    df.loc[df["change_pct"] >= SURGE_CHANGE_PCT, "surge_score"] += 1

    if "volume_ratio" in df.columns:
        df.loc[df["volume_ratio"] >= SURGE_VOLUME_RATIO, "surge_score"] += 1

    gap_up = (df["open"] > df["low"]) & (df["change_pct"] > 2.0)
    df.loc[gap_up, "surge_score"] += 1

    if "consecutive_gains" in df.columns:
        df.loc[df["consecutive_gains"] >= 3, "surge_score"] += 1

    df["is_surging"] = (df["surge_score"] >= SURGE_MIN_SCORE).astype(int)

    # ── 급등 예보 점수 (pre_surge_score, 0~5) ──
    # v5.4: 조건별 변별력 강화, 최소 충족 4개로 상향
    df["pre_surge_score"] = 0

    # 1) 거래량 증가 중이지만 가격 변동 적음 (매집 징후)
    #    v5.4: volume_ratio 하한 2.0으로 상향 (기존 1.5)
    if "volume_ratio" in df.columns:
        quiet_accumulation = (
            (df["volume_ratio"] >= 2.0) &
            (df["volume_ratio"] <= 5.0) &
            (df["change_pct"].abs() < 2.0)  # 기존 3.0 → 2.0으로 강화
        )
        df.loc[quiet_accumulation, "pre_surge_score"] += 1

    # 2) 거래량 연속 증가 (3일 이상, 기존 2일→3일)
    if "volume_trend" in df.columns:
        df.loc[df["volume_trend"] >= 3, "pre_surge_score"] += 1

    # 3) 이평선 수렴 (에너지 축적, 스프레드 < 2%, 기존 3%→2%)
    if "ma_squeeze" in df.columns:
        df.loc[df["ma_squeeze"] < 2.0, "pre_surge_score"] += 1

    # 4) 연속 상승 (2~3일, 기존 1일→2일 이상)
    if "consecutive_gains" in df.columns:
        df.loc[
            (df["consecutive_gains"] >= 2) & (df["consecutive_gains"] <= 4),
            "pre_surge_score",
        ] += 1

    # 5) 골든크로스 또는 정배열
    gc_or_aligned = pd.Series(False, index=df.index)
    if "golden_cross" in df.columns:
        gc_or_aligned = gc_or_aligned | (df["golden_cross"] == 1)
    if "ma_aligned" in df.columns:
        gc_or_aligned = gc_or_aligned | (df["ma_aligned"] == 1)
    df.loc[gc_or_aligned, "pre_surge_score"] += 1

    # v5.4: 최소 점수 4/5로 상향 (기존 3/5)
    df["is_pre_surge"] = (df["pre_surge_score"] >= PRE_SURGE_MIN_SCORE).astype(int)

    surge_count = df["is_surging"].sum()
    pre_count = df["is_pre_surge"].sum()
    logger.info(f"급등주 탐지: 기발생 {surge_count}종목, 예보 {pre_count}종목 (임계={PRE_SURGE_MIN_SCORE}/5)")
    return df


# ──────────────────────────────────────────────
# 종합 매수 점수 — 한/미 분리 스코어링
# ──────────────────────────────────────────────

def calculate_buy_score(df: pd.DataFrame) -> pd.DataFrame:
    """종합 매수 추천 점수 (0~100).

    한국 주식: 기술(40) + 모멘텀(25) + 수급(20) + 가치(15)
    미국 주식: 기술(35) + 모멘텀(30) + 성장(20) + 가치(15)
      - US는 외국인/기관 순매수 데이터가 없으므로 수급 대신 성장 팩터 사용
    """
    df = df.copy()
    df["buy_score"] = 0.0

    is_us = df["market"].isin(["NASDAQ", "S&P500"])
    is_kr = ~is_us

    # ── 1. 기술적 시그널 ──
    tech_score = pd.Series(0.0, index=df.index)

    # 급등 예보 (0~5 → 0~15점)
    if "pre_surge_score" in df.columns:
        tech_score += (df["pre_surge_score"].clip(0, 5) / 5 * 15)

    # 돌파 점수 (0~4 → 0~10점)
    if "breakout_score" in df.columns:
        tech_score += (df["breakout_score"].clip(0, 4) / 4 * 10)

    # 골든크로스 — 단기(MA5/20): 5점, 장기(MA20/60): 3점 추가
    if "golden_cross" in df.columns:
        tech_score += df["golden_cross"] * 5
    if "golden_cross_long" in df.columns:
        tech_score += df["golden_cross_long"] * 3

    # 정배열 (0/1 → 0~7점)
    if "ma_aligned" in df.columns:
        tech_score += df["ma_aligned"] * 7

    # KR: 40점 만점, US: 35점 만점 (스케일링)
    tech_kr = tech_score.clip(0, 40)
    tech_us = (tech_score / 40 * 35).clip(0, 35)

    # ── 2. 모멘텀 ──
    momentum_score = pd.Series(0.0, index=df.index)

    # RSI 반등 구간
    if "rsi" in df.columns:
        rsi = df["rsi"]
        rsi_score = pd.Series(0.0, index=df.index)
        rsi_score[(rsi > 0) & (rsi <= 30)] = 8.0
        rsi_score[(rsi > 30) & (rsi <= 45)] = 10.0
        rsi_score[(rsi > 45) & (rsi <= 55)] = 5.0
        rsi_score[(rsi > 55) & (rsi <= 70)] = 2.0
        momentum_score += rsi_score

    # 거래량 추세 (0~5 → 0~8점)
    if "volume_trend" in df.columns:
        momentum_score += (df["volume_trend"].clip(0, 5) / 5 * 8)

    # 연속 상승
    if "consecutive_gains" in df.columns:
        cg = df["consecutive_gains"].clip(0, 5)
        cg_score = pd.Series(0.0, index=df.index)
        cg_score[cg == 1] = 4.0
        cg_score[cg == 2] = 6.0
        cg_score[cg == 3] = 7.0
        cg_score[cg == 4] = 5.0
        cg_score[cg >= 5] = 3.0
        momentum_score += cg_score

    # KR: 25점, US: 30점 만점
    mom_kr = momentum_score.clip(0, 25)
    mom_us = (momentum_score / 25 * 30).clip(0, 30)

    # ── 3. 수급 (KR only, 20점) / 성장 (US only, 20점) ──
    supply_score_kr = pd.Series(0.0, index=df.index)

    # 외국인 순매수 (KR) — 양수=매수, 음수=매도
    if "foreign_net" in df.columns:
        fn = df["foreign_net"]
        supply_score_kr[fn > 0] += 8.0        # 순매수 중

    # 기관 순매수 (KR) — 양수=매수, 음수=매도
    if "inst_net" in df.columns:
        inst = df["inst_net"]
        supply_score_kr[inst > 0] += 7.0      # 순매수 중

    # 매집 시그널 (KR)
    if "accumulation" in df.columns:
        supply_score_kr += df["accumulation"] * 5

    supply_score_kr = supply_score_kr.clip(0, 20)

    # 성장 팩터 (US) — ROE + 시가총액 안정성
    growth_score_us = pd.Series(0.0, index=df.index)
    if "roe" in df.columns:
        # ROE 캡 처리 (음수 자본 기업의 ROE 7000% 등 이상치 방지)
        roe = df["roe"].clip(-100, 200)
        growth_score_us[(roe > 0) & (roe <= 10)] = 4.0
        growth_score_us[(roe > 10) & (roe <= 20)] = 8.0
        growth_score_us[(roe > 20) & (roe <= 40)] = 10.0
        growth_score_us[(roe > 40) & (roe <= 200)] = 6.0  # 지나치게 높으면 감점
        growth_score_us[roe > 200] = 0.0  # 이상치 제외

    # 거래량 모멘텀 (US 추가 보너스)
    if "volume_ratio" in df.columns:
        vr = df["volume_ratio"]
        growth_score_us[(vr >= 1.5) & (vr <= 3.0)] += 5.0
        growth_score_us[(vr > 3.0) & (vr <= 5.0)] += 3.0

    # 시가총액 안정성 (US: 대형주 우대)
    if "market_cap" in df.columns:
        mc = df["market_cap"]
        growth_score_us[mc >= 100000] += 5.0   # 10조원 이상
        growth_score_us[(mc >= 10000) & (mc < 100000)] += 3.0

    growth_score_us = growth_score_us.clip(0, 20)

    # ── 4. 가치 (15점 만점 — 한/미 공통, v6 강화) ──
    value_score = pd.Series(0.0, index=df.index)

    # PER 적정 범위: 4점
    if "per" in df.columns:
        per = df["per"]
        per_score = pd.Series(0.0, index=df.index)
        per_score[(per > 0) & (per <= 5)] = 3.0
        per_score[(per > 5) & (per <= 10)] = 4.0
        per_score[(per > 10) & (per <= 15)] = 3.0
        per_score[(per > 15) & (per <= 25)] = 1.0
        value_score += per_score

    # PBR < 1.0: 3점
    if "pbr" in df.columns:
        pbr = df["pbr"]
        pbr_score = pd.Series(0.0, index=df.index)
        pbr_score[(pbr > 0) & (pbr <= 0.5)] = 3.0
        pbr_score[(pbr > 0.5) & (pbr <= 1.0)] = 2.5
        pbr_score[(pbr > 1.0) & (pbr <= 2.0)] = 1.0
        pbr_score[is_us & (pbr > 2.0) & (pbr <= 4.0)] = 0.5
        value_score += pbr_score

    # v6: EV/EBITDA < 10: 3점
    if "ev_ebitda" in df.columns:
        ev = df["ev_ebitda"]
        ev_score = pd.Series(0.0, index=df.index)
        ev_score[(ev > 0) & (ev <= 5)] = 3.0
        ev_score[(ev > 5) & (ev <= 10)] = 2.0
        ev_score[(ev > 10) & (ev <= 15)] = 1.0
        value_score += ev_score

    # v6: FCF Yield > 5%: 3점
    if "fcf_yield" in df.columns:
        fcf = df["fcf_yield"]
        fcf_score = pd.Series(0.0, index=df.index)
        fcf_score[fcf >= 10] = 3.0
        fcf_score[(fcf >= 5) & (fcf < 10)] = 2.0
        fcf_score[(fcf >= 2) & (fcf < 5)] = 1.0
        value_score += fcf_score

    # v6: 목표주가 괴리율 > 20%: 2점
    if "target_upside" in df.columns:
        tu = df["target_upside"]
        tu_score = pd.Series(0.0, index=df.index)
        tu_score[tu >= 30] = 2.0
        tu_score[(tu >= 20) & (tu < 30)] = 1.5
        tu_score[(tu >= 10) & (tu < 20)] = 0.5
        value_score += tu_score

    value_score = value_score.clip(0, 15)

    # ── 종합: 한국 vs 미국 분리 합산 ──
    kr_total = tech_kr + mom_kr + supply_score_kr + value_score
    us_total = tech_us + mom_us + growth_score_us + value_score

    df["buy_score"] = 0.0
    df.loc[is_kr, "buy_score"] = kr_total[is_kr]
    df.loc[is_us, "buy_score"] = us_total[is_us]
    df["buy_score"] = df["buy_score"].round(1).clip(0, 100)

    # 히스토리 미수집 종목 페널티: 기술+모멘텀이 0이면 가치만으로 등급 부여 방지
    # RSI=0이면 히스토리 없는 것 → 가치 점수만으로 "관심" 등급 받는 것 방지
    no_history = (df.get("rsi", pd.Series(0, index=df.index)) <= 0) & (df.get("ma20", pd.Series(0, index=df.index)) <= 0)
    df.loc[no_history, "buy_score"] = (df.loc[no_history, "buy_score"] * 0.3).round(1)  # 70% 감점

    # 등급 부여
    df["buy_grade"] = "관망"
    df.loc[df["buy_score"] >= 70, "buy_grade"] = "적극매수"
    df.loc[(df["buy_score"] >= 50) & (df["buy_score"] < 70), "buy_grade"] = "매수"
    df.loc[(df["buy_score"] >= 30) & (df["buy_score"] < 50), "buy_grade"] = "관심"

    # v6 Phase 4: 포지션 사이징
    df["position_size"] = 0.0
    if "atr_14" in df.columns and "close" in df.columns:
        for idx, row in df.iterrows():
            atr = float(row.get("atr_14", 0))
            close = float(row.get("close", 0))
            if atr > 0 and close > 0:
                df.at[idx, "position_size"] = calculate_position_size(atr, close)

    high_count = (df["buy_score"] >= 50).sum()
    logger.info(f"매수 추천 점수 계산 완료: 매수 이상 {high_count}종목")
    return df


# ──────────────────────────────────────────────
# 수급 시그널 (v6 Phase 2)
# ──────────────────────────────────────────────

def calculate_supply_signals(df: pd.DataFrame, supply_history: dict) -> pd.DataFrame:
    """수급 이력 기반 시그널 계산.

    Args:
        df: 종목 DataFrame
        supply_history: {ticker: [{"date": ..., "foreign_net": ..., "inst_net": ...}, ...]}

    새 필드:
        foreign_consecutive: 외국인 연속 순매수 일수 (음수=연속 순매도)
        supply_intensity: 수급 강도 (거래대금 대비 %)
        dual_buy: 외국인+기관 동반 순매수
        supply_grade: 수급 등급
    """
    df = df.copy()
    df["foreign_consecutive"] = 0
    df["supply_intensity"] = 0.0
    df["dual_buy"] = False
    df["supply_grade"] = "중립"

    if not supply_history:
        return df

    for idx, row in df.iterrows():
        ticker = str(row.get("ticker", ""))
        history = supply_history.get(ticker, [])
        if not history:
            continue

        # 연속 매수/매도 일수
        consecutive = 0
        for entry in reversed(history):
            fn = entry.get("foreign_net", 0)
            if fn > 0:
                if consecutive >= 0:
                    consecutive += 1
                else:
                    break
            elif fn < 0:
                if consecutive <= 0:
                    consecutive -= 1
                else:
                    break
            else:
                break

        df.at[idx, "foreign_consecutive"] = consecutive

        # 수급 강도: foreign_net / trading_value * 100
        trading_val = float(row.get("trading_value", 0))
        foreign_net = float(row.get("foreign_net", 0))
        if trading_val > 0:
            df.at[idx, "supply_intensity"] = round(abs(foreign_net) / trading_val * 100, 2)

        # 동반 매수
        inst_net = float(row.get("inst_net", 0))
        df.at[idx, "dual_buy"] = (foreign_net > 0 and inst_net > 0)

    # 수급 등급
    df.loc[
        (df["foreign_consecutive"] >= 5) & (df["dual_buy"]),
        "supply_grade"
    ] = "강력매수"
    df.loc[
        (df["supply_grade"] == "중립") & (
            (df["foreign_consecutive"] >= 3) | (df["supply_intensity"] > 10)
        ),
        "supply_grade"
    ] = "매수세"
    df.loc[
        (df["supply_grade"] == "중립") & (df["foreign_consecutive"] <= -3),
        "supply_grade"
    ] = "매도세"
    df.loc[
        (df["supply_grade"] == "중립") & (df["foreign_consecutive"] <= -5),
        "supply_grade"
    ] = "강력매도"

    buy_count = (df["supply_grade"].isin(["강력매수", "매수세"])).sum()
    logger.info(f"수급 시그널 계산 완료: 매수세 이상 {buy_count}종목")
    return df


# ──────────────────────────────────────────────
# 포지션 사이징 + 시장 레짐 (v6 Phase 4)
# ──────────────────────────────────────────────

def calculate_position_size(atr: float, close: float, account_size: float = 10_000_000, risk_pct: float = 0.02) -> float:
    """ATR 기반 적정 투자 비중 (%).

    Args:
        atr: 14일 ATR
        close: 현재가
        account_size: 계좌 규모 (기본 1000만원)
        risk_pct: 최대 손실 허용 비율 (기본 2%)

    Returns:
        position_pct: 총 자산 대비 권장 투자 비중 (%)
    """
    if atr <= 0 or close <= 0:
        return 0.0
    risk_per_share = atr * 2  # 2ATR 손절 기준
    shares = (account_size * risk_pct) / risk_per_share
    position_pct = (shares * close) / account_size * 100
    return round(min(position_pct, 25.0), 1)  # 최대 25%


def detect_market_regime(close_series: pd.Series) -> dict:
    """시장 레짐 판별 (인덱스 close 시리즈 기반).

    Returns:
        {"regime": "bull"|"bear"|"sideways", "confidence": 0.0~1.0}
    """
    if close_series is None or len(close_series) < 60:
        return {"regime": "sideways", "confidence": 0.3}

    current = float(close_series.iloc[-1])
    ma20 = float(close_series.tail(20).mean())
    ma60 = float(close_series.tail(60).mean())

    # MA60 방향 (최근 20일 vs 이전 20일)
    ma60_recent = float(close_series.tail(20).mean())
    ma60_prev = float(close_series.iloc[-40:-20].mean()) if len(close_series) >= 40 else ma60_recent
    ma60_direction = ma60_recent - ma60_prev

    signals = 0  # 양수=강세, 음수=약세

    # 1) 현재가 > MA20
    if current > ma20:
        signals += 1
    else:
        signals -= 1

    # 2) 현재가 > MA60
    if current > ma60:
        signals += 1
    else:
        signals -= 1

    # 3) MA60 방향
    if ma60_direction > 0:
        signals += 1
    else:
        signals -= 1

    if signals >= 2:
        return {"regime": "bull", "confidence": round(min(0.6 + abs(signals) * 0.1, 1.0), 2)}
    elif signals <= -2:
        return {"regime": "bear", "confidence": round(min(0.6 + abs(signals) * 0.1, 1.0), 2)}
    else:
        return {"regime": "sideways", "confidence": 0.5}


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _calc_consecutive_gains(close_pivot: pd.DataFrame) -> pd.Series:
    """연속 상승일수."""
    consecutive = pd.Series(0, index=close_pivot.columns)
    recent = close_pivot.tail(10)
    if len(recent) < 2:
        return consecutive

    daily_returns = recent.pct_change().iloc[1:]
    for ticker in close_pivot.columns:
        count = 0
        for val in daily_returns[ticker].iloc[::-1]:
            if pd.notna(val) and val > 0:
                count += 1
            else:
                break
        consecutive[ticker] = count

    return consecutive


def _calc_volume_trend(volume_pivot: pd.DataFrame) -> pd.Series:
    """최근 5일간 거래량 연속 증가 일수."""
    trend = pd.Series(0, index=volume_pivot.columns)
    recent = volume_pivot.tail(6)
    if len(recent) < 2:
        return trend

    daily_change = recent.pct_change().iloc[1:]
    for ticker in volume_pivot.columns:
        count = 0
        for val in daily_change[ticker].iloc[::-1]:
            if pd.notna(val) and val > 0:
                count += 1
            else:
                break
        trend[ticker] = count

    return trend


def _calc_ma_squeeze(close_pivot: pd.DataFrame, windows: list[int]) -> pd.Series:
    """이평선 수렴도 (낮을수록 수렴, 돌파 에너지 축적)."""
    squeeze = pd.Series(99.0, index=close_pivot.columns)
    ma_vals = {}
    for w in windows:
        ma_vals[w] = close_pivot.tail(w).mean()

    if 5 in ma_vals and 60 in ma_vals:
        valid = ma_vals[60] > 0
        spread = (ma_vals[5] - ma_vals[60]).abs()
        squeeze[valid] = (spread[valid] / ma_vals[60][valid] * 100).round(2)

    return squeeze


def _calc_volatility(close_pivot: pd.DataFrame, period: int = 20) -> pd.Series:
    """일간 수익률의 표준편차 (20일 변동성, %)."""
    if len(close_pivot) < period:
        return pd.Series(0.0, index=close_pivot.columns)

    daily_returns = close_pivot.pct_change().tail(period) * 100
    return daily_returns.std().round(2)


def _calc_atr(
    high_pivot: pd.DataFrame,
    low_pivot: pd.DataFrame,
    close_pivot: pd.DataFrame,
    period: int = 14,
) -> pd.Series:
    """ATR (Average True Range) — 14일 평균 변동폭.

    True Range = max(H-L, |H-Prev_C|, |L-Prev_C|)
    """
    if len(close_pivot) < period + 1:
        return pd.Series(0.0, index=close_pivot.columns)

    prev_close = close_pivot.shift(1)
    tr1 = high_pivot - low_pivot
    tr2 = (high_pivot - prev_close).abs()
    tr3 = (low_pivot - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3]).groupby(level=0).max()

    atr = tr.tail(period).mean()
    return atr.round(2)
