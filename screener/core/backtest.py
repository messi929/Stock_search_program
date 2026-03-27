"""백테스트 엔진 — 시그널 적중률 검증.

히스토리 데이터를 기반으로 각 시그널이 발생한 시점 이후
N일간 수익률을 시뮬레이션하여 적중률을 산출.
"""

import numpy as np
import pandas as pd
from loguru import logger


def backtest_signals(history: pd.DataFrame, snapshot: pd.DataFrame) -> dict:
    """전체 시그널 백테스트.

    Args:
        history: OHLCV 데이터 (date, ticker, open, high, low, close, volume)
        snapshot: 현재 스냅샷 (기술지표 포함)

    Returns:
        {signal_name: {hit_rate, avg_return, sample_count, details}}
    """
    if history.empty:
        return {}

    close_pivot = history.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    ).sort_index()

    volume_pivot = history.pivot_table(
        index="date", columns="ticker", values="volume", aggfunc="last"
    ).sort_index()

    if len(close_pivot) < 20:
        logger.warning("히스토리 부족 (20일 미만) — 백테스트 스킵")
        return {}

    results = {}

    # 1) 골든크로스 시그널
    results["golden_cross"] = _test_golden_cross(close_pivot)

    # 2) 거래량 급증 + 가격 미변동 (매집)
    results["accumulation"] = _test_accumulation(close_pivot, volume_pivot)

    # 3) RSI 과매도 반등
    results["rsi_oversold"] = _test_rsi_oversold(close_pivot)

    # 4) 이평선 수렴 후 돌파
    results["ma_squeeze_breakout"] = _test_ma_squeeze(close_pivot)

    # 5) 연속 거래량 증가
    results["volume_trend"] = _test_volume_trend(close_pivot, volume_pivot)

    # 요약 로그
    for name, r in results.items():
        if r["sample_count"] > 0:
            logger.info(
                f"백테스트 [{name}]: 적중률 {r['hit_rate']:.1f}%, "
                f"평균수익 {r['avg_return']:.2f}%, 샘플 {r['sample_count']}건"
            )

    return results


def _calc_forward_returns(close_pivot: pd.DataFrame, periods: list[int] = [3, 5, 10]) -> dict:
    """N일 후 수익률 계산."""
    fwd = {}
    for n in periods:
        fwd[n] = close_pivot.pct_change(n).shift(-n) * 100
    return fwd


def _test_golden_cross(close_pivot: pd.DataFrame) -> dict:
    """골든크로스(MA5>MA20) 발생 후 5일 수익률."""
    ma5 = close_pivot.rolling(5).mean()
    ma20 = close_pivot.rolling(20).mean()

    # 골든크로스: 전일 MA5<MA20, 당일 MA5>MA20
    gc_signal = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))

    fwd_5d = close_pivot.pct_change(5).shift(-5) * 100

    returns = []
    for date in gc_signal.index:
        for ticker in gc_signal.columns:
            if gc_signal.loc[date, ticker] and not pd.isna(fwd_5d.loc[date, ticker]):
                returns.append(fwd_5d.loc[date, ticker])

    return _summarize(returns, "골든크로스 후 5일")


def _test_accumulation(close_pivot: pd.DataFrame, volume_pivot: pd.DataFrame) -> dict:
    """매집 시그널(거래량↑ 가격변동↓) 후 5일 수익률."""
    vol_avg = volume_pivot.rolling(20).mean()
    vol_ratio = volume_pivot / vol_avg.replace(0, np.nan)

    price_change = close_pivot.pct_change().abs() * 100

    # 매집: 거래량비 1.5x 이상, 가격변동 2% 미만
    accum = (vol_ratio >= 1.5) & (price_change < 2.0)

    fwd_5d = close_pivot.pct_change(5).shift(-5) * 100

    returns = []
    for date in accum.index:
        for ticker in accum.columns:
            if accum.loc[date, ticker] and not pd.isna(fwd_5d.loc[date, ticker]):
                returns.append(fwd_5d.loc[date, ticker])

    return _summarize(returns, "매집 시그널 후 5일")


def _test_rsi_oversold(close_pivot: pd.DataFrame) -> dict:
    """RSI 30 이하 진입 후 5일 수익률."""
    delta = close_pivot.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # RSI 30 이하 진입 시점
    oversold = (rsi <= 30) & (rsi.shift(1) > 30)

    fwd_5d = close_pivot.pct_change(5).shift(-5) * 100

    returns = []
    for date in oversold.index:
        for ticker in oversold.columns:
            if oversold.loc[date, ticker] and not pd.isna(fwd_5d.loc[date, ticker]):
                returns.append(fwd_5d.loc[date, ticker])

    return _summarize(returns, "RSI 과매도 반등 5일")


def _test_ma_squeeze(close_pivot: pd.DataFrame) -> dict:
    """이평선 수렴(MA5-MA60 스프레드 <2%) 후 5일 수익률."""
    ma5 = close_pivot.rolling(5).mean()
    ma60 = close_pivot.rolling(60).mean()

    spread = ((ma5 - ma60).abs() / ma60.replace(0, np.nan) * 100)

    # 수렴 후 상방 돌파: 스프레드 <2% → 가격이 MA5 돌파
    squeeze = spread < 2.0
    price_above_ma5 = close_pivot > ma5

    breakout = squeeze & price_above_ma5 & (~price_above_ma5.shift(1).fillna(False))

    fwd_5d = close_pivot.pct_change(5).shift(-5) * 100

    returns = []
    for date in breakout.index:
        for ticker in breakout.columns:
            if breakout.loc[date, ticker] and not pd.isna(fwd_5d.loc[date, ticker]):
                returns.append(fwd_5d.loc[date, ticker])

    return _summarize(returns, "이평수렴 돌파 5일")


def _test_volume_trend(close_pivot: pd.DataFrame, volume_pivot: pd.DataFrame) -> dict:
    """3일 연속 거래량 증가 후 5일 수익률."""
    vol_change = volume_pivot.pct_change()

    # 3일 연속 증가
    trend3 = (vol_change > 0) & (vol_change.shift(1) > 0) & (vol_change.shift(2) > 0)

    fwd_5d = close_pivot.pct_change(5).shift(-5) * 100

    returns = []
    for date in trend3.index:
        for ticker in trend3.columns:
            if trend3.loc[date, ticker] and not pd.isna(fwd_5d.loc[date, ticker]):
                returns.append(fwd_5d.loc[date, ticker])

    return _summarize(returns, "거래량 3일 연속 증가 5일")


def _summarize(returns: list, label: str) -> dict:
    """수익률 리스트를 요약."""
    if not returns:
        return {
            "label": label,
            "hit_rate": 0.0,
            "avg_return": 0.0,
            "median_return": 0.0,
            "max_return": 0.0,
            "min_return": 0.0,
            "sample_count": 0,
        }

    arr = np.array(returns)
    positive = (arr > 0).sum()

    return {
        "label": label,
        "hit_rate": round(positive / len(arr) * 100, 1),
        "avg_return": round(float(arr.mean()), 2),
        "median_return": round(float(np.median(arr)), 2),
        "max_return": round(float(arr.max()), 2),
        "min_return": round(float(arr.min()), 2),
        "sample_count": len(arr),
    }
