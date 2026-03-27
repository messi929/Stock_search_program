"""파생 지표 계산: 이동평균, RSI, 거래량 비율 + 예측 시그널."""

import numpy as np
import pandas as pd
from loguru import logger

from screener.config import SURGE_CHANGE_PCT, SURGE_VOLUME_RATIO, SURGE_MIN_SCORE


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

    ma_data = {}
    for w in windows:
        ma_data[f"ma{w}"] = close_pivot.tail(w).mean()

    ma_data["avg_volume_20"] = volume_pivot.tail(20).mean()
    ma_data["consecutive_gains"] = _calc_consecutive_gains(close_pivot)

    # ── 예측 시그널용 추가 지표 ──
    ma_data["volume_trend"] = _calc_volume_trend(volume_pivot)
    ma_data["ma_squeeze"] = _calc_ma_squeeze(close_pivot, windows)

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

    # 골든크로스 / 데드크로스
    if "ma5" in result.columns and "ma20" in result.columns:
        result["golden_cross"] = (result["ma5"] > result["ma20"]).astype(int)
        result["death_cross"] = (result["ma5"] < result["ma20"]).astype(int)
    else:
        result["golden_cross"] = 0
        result["death_cross"] = 0

    # 정배열 (5일 > 20일 > 60일)
    if all(f"ma{w}" in result.columns for w in [5, 20, 60]):
        result["ma_aligned"] = (
            (result["ma5"] > result["ma20"]) & (result["ma20"] > result["ma60"])
        ).astype(int)
    else:
        result["ma_aligned"] = 0

    # ── 매집 시그널: 거래량 증가 + 가격 변동 적음 ──
    result["accumulation"] = 0
    has_vr = result["volume_ratio"] > 0
    quiet_price = result["change_pct"].abs() < 2.0
    vol_up = result["volume_ratio"] >= 1.5
    result.loc[has_vr & quiet_price & vol_up, "accumulation"] = 1

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

    logger.info(f"이동평균 + 예측 시그널 계산 완료")
    return result


def calculate_rsi(history: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI(상대강도지수) 계산. 종목별 마지막 RSI 반환."""
    if history.empty:
        return pd.Series(dtype=float)

    close_pivot = history.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    ).sort_index()

    delta = close_pivot.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.tail(period).mean()
    avg_loss = loss.tail(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_52week(history: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """52주 최고가/최저가 대비 현재 위치(%)."""
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
    """이평선 수렴도 (낮을수록 수렴, 돌파 에너지 축적).
    MA5~MA60 스프레드를 MA60 대비 %로 측정.
    """
    squeeze = pd.Series(99.0, index=close_pivot.columns)
    ma_vals = {}
    for w in windows:
        ma_vals[w] = close_pivot.tail(w).mean()

    if 5 in ma_vals and 60 in ma_vals:
        valid = ma_vals[60] > 0
        spread = (ma_vals[5] - ma_vals[60]).abs()
        squeeze[valid] = (spread[valid] / ma_vals[60][valid] * 100).round(2)

    return squeeze


def detect_surging_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """급등 예보: 아직 급등하지 않았지만 급등 전 징후가 있는 종목."""
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
    # "아직 안 올랐지만 곧 오를 징후"
    df["pre_surge_score"] = 0

    # 1) 거래량 증가 중이지만 가격 변동 적음 (매집 징후)
    if "volume_ratio" in df.columns:
        quiet_accumulation = (
            (df["volume_ratio"] >= 1.5) &
            (df["volume_ratio"] <= 5.0) &
            (df["change_pct"].abs() < 3.0)
        )
        df.loc[quiet_accumulation, "pre_surge_score"] += 1

    # 2) 거래량 연속 증가 (2일 이상)
    if "volume_trend" in df.columns:
        df.loc[df["volume_trend"] >= 2, "pre_surge_score"] += 1

    # 3) 이평선 수렴 (에너지 축적, 스프레드 < 3%)
    if "ma_squeeze" in df.columns:
        df.loc[df["ma_squeeze"] < 3.0, "pre_surge_score"] += 1

    # 4) 연속 상승 시작 (1~2일, 아직 초기)
    if "consecutive_gains" in df.columns:
        df.loc[
            (df["consecutive_gains"] >= 1) & (df["consecutive_gains"] <= 3),
            "pre_surge_score",
        ] += 1

    # 5) 골든크로스 또는 정배열
    if "golden_cross" in df.columns:
        df.loc[df["golden_cross"] == 1, "pre_surge_score"] += 1

    df["is_pre_surge"] = (df["pre_surge_score"] >= 3).astype(int)

    surge_count = df["is_surging"].sum()
    pre_count = df["is_pre_surge"].sum()
    logger.info(f"급등주 탐지: 기발생 {surge_count}종목, 예보 {pre_count}종목")
    return df


def calculate_buy_score(df: pd.DataFrame) -> pd.DataFrame:
    """AI 매수 추천 종합점수 (0~100).

    8개 요소를 가중 합산하여 종합 점수 산출:
      - 기술적 시그널 (40%): 급등예보, 돌파점수, 골든크로스, 정배열
      - 모멘텀 (25%): RSI 반등구간, 거래량 추세, 연속 상승
      - 수급 (20%): 외국인/기관 순매수, 매집 시그널
      - 가치 (15%): PER 적정성, PBR 저평가
    """
    df = df.copy()
    df["buy_score"] = 0.0

    # ── 1. 기술적 시그널 (40점 만점) ──
    tech_score = pd.Series(0.0, index=df.index)

    # 급등 예보 (0~5 → 0~15점)
    if "pre_surge_score" in df.columns:
        tech_score += (df["pre_surge_score"].clip(0, 5) / 5 * 15)

    # 돌파 점수 (0~4 → 0~10점)
    if "breakout_score" in df.columns:
        tech_score += (df["breakout_score"].clip(0, 4) / 4 * 10)

    # 골든크로스 (0/1 → 0~8점)
    if "golden_cross" in df.columns:
        tech_score += df["golden_cross"] * 8

    # 정배열 (0/1 → 0~7점)
    if "ma_aligned" in df.columns:
        tech_score += df["ma_aligned"] * 7

    # ── 2. 모멘텀 (25점 만점) ──
    momentum_score = pd.Series(0.0, index=df.index)

    # RSI 반등 구간 (30~45: 매수 적기, 0~10점)
    if "rsi" in df.columns:
        rsi = df["rsi"]
        # RSI 30~45: 만점, 45~55: 감점, 55+: 0점, 0(미계산): 0점
        rsi_score = pd.Series(0.0, index=df.index)
        rsi_score[(rsi > 0) & (rsi <= 30)] = 8.0   # 과매도 반등 기대
        rsi_score[(rsi > 30) & (rsi <= 45)] = 10.0  # 최적 매수구간
        rsi_score[(rsi > 45) & (rsi <= 55)] = 5.0   # 중립
        rsi_score[(rsi > 55) & (rsi <= 70)] = 2.0   # 과열 접근
        momentum_score += rsi_score

    # 거래량 추세 (0~5 → 0~8점)
    if "volume_trend" in df.columns:
        momentum_score += (df["volume_trend"].clip(0, 5) / 5 * 8)

    # 연속 상승 (1~3: 초기 상승, 0~7점)
    if "consecutive_gains" in df.columns:
        cg = df["consecutive_gains"].clip(0, 5)
        # 1~3일: 점수 증가, 4~5일: 과열 감점
        cg_score = pd.Series(0.0, index=df.index)
        cg_score[cg == 1] = 4.0
        cg_score[cg == 2] = 6.0
        cg_score[cg == 3] = 7.0
        cg_score[cg == 4] = 5.0
        cg_score[cg >= 5] = 3.0
        momentum_score += cg_score

    # ── 3. 수급 (20점 만점) ──
    supply_score = pd.Series(0.0, index=df.index)

    # 외국인 순매수 (양수면 가산, 0~8점)
    if "foreign_net" in df.columns:
        fn = df["foreign_net"]
        supply_score[fn > 0] += 4.0
        supply_score[fn > 10000] += 2.0
        supply_score[fn > 50000] += 2.0

    # 기관 순매수 (0~7점)
    if "inst_net" in df.columns:
        inst = df["inst_net"]
        supply_score[inst > 0] += 3.0
        supply_score[inst > 10000] += 2.0
        supply_score[inst > 50000] += 2.0

    # 매집 시그널 (0/1 → 0~5점)
    if "accumulation" in df.columns:
        supply_score += df["accumulation"] * 5

    # ── 4. 가치 (15점 만점) ──
    value_score = pd.Series(0.0, index=df.index)

    # PER 적정성 (5~15: 적정, 0~8점)
    if "per" in df.columns:
        per = df["per"]
        per_score = pd.Series(0.0, index=df.index)
        per_score[(per > 0) & (per <= 5)] = 6.0    # 저PER
        per_score[(per > 5) & (per <= 10)] = 8.0   # 적정
        per_score[(per > 10) & (per <= 15)] = 6.0   # 약간 높음
        per_score[(per > 15) & (per <= 25)] = 3.0   # 높음
        value_score += per_score

    # PBR 저평가 (0.5~1.0: 적정, 0~7점)
    if "pbr" in df.columns:
        pbr = df["pbr"]
        pbr_score = pd.Series(0.0, index=df.index)
        pbr_score[(pbr > 0) & (pbr <= 0.5)] = 7.0   # 심한 저평가
        pbr_score[(pbr > 0.5) & (pbr <= 1.0)] = 6.0  # 저평가
        pbr_score[(pbr > 1.0) & (pbr <= 2.0)] = 3.0  # 적정
        value_score += pbr_score

    # ── 종합 ──
    df["buy_score"] = (tech_score + momentum_score + supply_score + value_score).round(1)
    df["buy_score"] = df["buy_score"].clip(0, 100)

    # 등급 부여
    df["buy_grade"] = "관망"
    df.loc[df["buy_score"] >= 70, "buy_grade"] = "적극매수"
    df.loc[(df["buy_score"] >= 50) & (df["buy_score"] < 70), "buy_grade"] = "매수"
    df.loc[(df["buy_score"] >= 30) & (df["buy_score"] < 50), "buy_grade"] = "관심"

    high_count = (df["buy_score"] >= 50).sum()
    logger.info(f"매수 추천 점수 계산 완료: 매수 이상 {high_count}종목")
    return df
