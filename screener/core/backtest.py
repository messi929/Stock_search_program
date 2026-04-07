"""백테스트 엔진 — 시그널 적중률 검증 (v6.0 다기간).

히스토리 데이터를 기반으로 각 시그널이 발생한 시점 이후
5/10/20/60일간 수익률을 시뮬레이션하여 적중률·Sharpe·알파 등을 산출.
"""

import numpy as np
import pandas as pd
from loguru import logger

FORWARD_WINDOWS = [5, 10, 20, 60]
RISK_FREE_RATE = 0.035  # 연 3.5% (한국 기준금리 근사)
TRADING_DAYS_YEAR = 250


def backtest_signals(history: pd.DataFrame, snapshot: pd.DataFrame) -> dict:
    """전체 시그널 백테스트 (다기간).

    Args:
        history: OHLCV 데이터 (date, ticker, open, high, low, close, volume)
        snapshot: 현재 스냅샷 (기술지표 포함)

    Returns:
        {"signals": {signal_name: {"windows": {5: {...}, 10: {...}, ...}}},
         "score_tracking": {...}}
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

    # 다기간 forward returns 미리 계산
    fwd_returns = _calc_forward_returns(close_pivot, FORWARD_WINDOWS)

    # 벤치마크 수익률 (인덱스 데이터가 히스토리에 있으면 사용)
    benchmark_returns = _calc_benchmark_returns(close_pivot, FORWARD_WINDOWS)

    results = {}

    # ── 기술적 시그널 ──
    results["golden_cross"] = _test_signal_multi(
        _detect_golden_cross(close_pivot), fwd_returns, "골든크로스", benchmark_returns
    )
    results["accumulation"] = _test_signal_multi(
        _detect_accumulation(close_pivot, volume_pivot), fwd_returns, "매집", benchmark_returns
    )
    results["rsi_oversold"] = _test_signal_multi(
        _detect_rsi_oversold(close_pivot), fwd_returns, "RSI 과매도 반등", benchmark_returns
    )
    results["ma_squeeze_breakout"] = _test_signal_multi(
        _detect_ma_squeeze(close_pivot), fwd_returns, "이평수렴 돌파", benchmark_returns
    )
    results["volume_trend"] = _test_signal_multi(
        _detect_volume_trend(close_pivot, volume_pivot), fwd_returns, "거래량 연속 증가", benchmark_returns
    )

    # ── 스냅샷 기반 시그널 (snapshot → 과거 시점 재현) ──
    score_tracking = _test_snapshot_signals(snapshot, close_pivot, fwd_returns)

    # 요약 로그
    for name, r in results.items():
        for w, stats in r.get("windows", {}).items():
            if stats["sample_count"] > 0:
                logger.info(
                    f"백테스트 [{name}][{w}d]: 적중률 {stats['hit_rate']:.1f}%, "
                    f"평균수익 {stats['avg_return']:.2f}%, 샘플 {stats['sample_count']}건"
                )

    return {"signals": results, "score_tracking": score_tracking}


# ─────────────────────────────────────────────
# Forward returns 계산
# ─────────────────────────────────────────────

def _calc_forward_returns(close_pivot: pd.DataFrame, windows: list[int]) -> dict:
    """N일 후 수익률 계산 (% 단위)."""
    fwd = {}
    for n in windows:
        fwd[n] = close_pivot.pct_change(n).shift(-n) * 100
    return fwd


def _calc_benchmark_returns(close_pivot: pd.DataFrame, windows: list[int]) -> dict:
    """벤치마크(KOSPI/S&P500) forward returns 계산.

    히스토리에 인덱스 데이터가 없으면 전종목 평균으로 대체.
    """
    bench = {}
    for n in windows:
        # 전종목 평균 수익률을 벤치마크로 사용 (인덱스 데이터 없는 환경 대비)
        fwd = close_pivot.pct_change(n).shift(-n) * 100
        bench[n] = fwd.mean(axis=1)  # 날짜별 평균 수익률
    return bench


# ─────────────────────────────────────────────
# 시그널 감지 함수 (bool DataFrame 반환)
# ─────────────────────────────────────────────

def _detect_golden_cross(close_pivot: pd.DataFrame) -> pd.DataFrame:
    """골든크로스(MA5>MA20) 시점."""
    ma5 = close_pivot.rolling(5).mean()
    ma20 = close_pivot.rolling(20).mean()
    return (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))


def _detect_accumulation(close_pivot: pd.DataFrame, volume_pivot: pd.DataFrame) -> pd.DataFrame:
    """매집 시그널(거래량↑ 가격변동↓)."""
    vol_avg = volume_pivot.rolling(20).mean()
    vol_ratio = volume_pivot / vol_avg.replace(0, np.nan)
    price_change = close_pivot.pct_change().abs() * 100
    return (vol_ratio >= 1.5) & (price_change < 2.0)


def _detect_rsi_oversold(close_pivot: pd.DataFrame) -> pd.DataFrame:
    """RSI 30 이하 진입 시점."""
    delta = close_pivot.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return (rsi <= 30) & (rsi.shift(1) > 30)


def _detect_ma_squeeze(close_pivot: pd.DataFrame) -> pd.DataFrame:
    """이평선 수렴 후 상방 돌파."""
    ma5 = close_pivot.rolling(5).mean()
    ma60 = close_pivot.rolling(60).mean()
    spread = ((ma5 - ma60).abs() / ma60.replace(0, np.nan) * 100)
    squeeze = spread < 2.0
    price_above = close_pivot > ma5
    return squeeze & price_above & (~price_above.shift(1).fillna(False))


def _detect_volume_trend(close_pivot: pd.DataFrame, volume_pivot: pd.DataFrame) -> pd.DataFrame:
    """3일 연속 거래량 증가."""
    vc = volume_pivot.pct_change()
    return (vc > 0) & (vc.shift(1) > 0) & (vc.shift(2) > 0)


# ─────────────────────────────────────────────
# 다기간 시그널 테스트
# ─────────────────────────────────────────────

def _test_signal_multi(
    signal_mask: pd.DataFrame,
    fwd_returns: dict,
    label: str,
    benchmark_returns: dict | None = None,
) -> dict:
    """시그널 마스크에 대해 모든 기간(5/10/20/60d) 수익률 통계 산출."""
    windows = {}
    for n, fwd_df in fwd_returns.items():
        returns = _extract_returns(signal_mask, fwd_df)

        # 알파 계산: 시그널 평균수익 - 벤치마크 평균수익
        alpha = 0.0
        if benchmark_returns and n in benchmark_returns and returns:
            # 시그널 발생 시점의 벤치마크 수익률
            bench_returns = _extract_benchmark_at_signal(
                signal_mask, benchmark_returns[n]
            )
            if bench_returns:
                alpha = round(np.mean(returns) - np.mean(bench_returns), 2)

        stats = _summarize(returns, f"{label} {n}일", n)
        stats["alpha"] = alpha
        windows[n] = stats

    return {"label": label, "windows": windows}


def _extract_benchmark_at_signal(
    signal_mask: pd.DataFrame, bench_series: pd.Series
) -> list[float]:
    """시그널 발생 시점의 벤치마크 수익률 추출."""
    common_idx = signal_mask.index.intersection(bench_series.index)
    if len(common_idx) == 0:
        return []

    results = []
    for date in common_idx:
        if signal_mask.loc[date].any():
            val = bench_series.loc[date]
            if not pd.isna(val):
                results.append(float(val))
    return results


def _extract_returns(signal_mask: pd.DataFrame, fwd_df: pd.DataFrame) -> list[float]:
    """시그널이 True인 셀의 forward return 값을 추출."""
    # 인덱스 교차점으로 정렬
    common_idx = signal_mask.index.intersection(fwd_df.index)
    common_cols = signal_mask.columns.intersection(fwd_df.columns)

    if len(common_idx) == 0 or len(common_cols) == 0:
        return []

    sig = signal_mask.loc[common_idx, common_cols]
    fwd = fwd_df.loc[common_idx, common_cols]

    # 벡터화 추출
    mask = sig.fillna(False).values & ~np.isnan(fwd.values)
    return fwd.values[mask].tolist()


# ─────────────────────────────────────────────
# 스냅샷 기반 시그널 (buy_score, pre_surge 등)
# ─────────────────────────────────────────────

def _test_snapshot_signals(
    snapshot: pd.DataFrame,
    close_pivot: pd.DataFrame,
    fwd_returns: dict,
) -> dict:
    """스냅샷 지표 기준 시그널 검증.

    snapshot의 현재 시점 기준으로, close_pivot 마지막 날짜에서의
    forward return을 사용하여 각 조건별 통계 산출.
    이전 히스토리 시그널과 달리, 현재 시점 단일 크로스섹션 분석.
    """
    if snapshot.empty or close_pivot.empty:
        return {}

    result = {}
    last_date = close_pivot.index[-1]

    # snapshot에서 ticker 기준 조건 필터
    conditions = {
        "buy_70plus": {
            "label": "적극매수 등급 (buy_score ≥ 70)",
            "filter": lambda df: df[df.get("buy_score", pd.Series(dtype=float)) >= 70]["ticker"] if "buy_score" in df.columns else pd.Series(dtype=str),
        },
        "buy_50plus": {
            "label": "매수 등급 (buy_score ≥ 50)",
            "filter": lambda df: df[df["buy_score"] >= 50]["ticker"] if "buy_score" in df.columns else pd.Series(dtype=str),
        },
        "pre_surge": {
            "label": "급등예보 (pre_surge_score ≥ 4)",
            "filter": lambda df: df[df["pre_surge_score"] >= 4]["ticker"] if "pre_surge_score" in df.columns else pd.Series(dtype=str),
        },
        "breakout": {
            "label": "돌파 임박 (breakout_score ≥ 3)",
            "filter": lambda df: df[df["breakout_score"] >= 3]["ticker"] if "breakout_score" in df.columns else pd.Series(dtype=str),
        },
        "dual_buy": {
            "label": "수급 동반 매수 (외국인+기관)",
            "filter": lambda df: df[(df.get("foreign_net", pd.Series(0)) > 0) & (df.get("inst_net", pd.Series(0)) > 0)]["ticker"] if "foreign_net" in df.columns and "inst_net" in df.columns else pd.Series(dtype=str),
        },
    }

    for key, cfg in conditions.items():
        try:
            tickers = cfg["filter"](snapshot)
            if isinstance(tickers, pd.Series) and not tickers.empty:
                ticker_list = tickers.tolist()
            else:
                ticker_list = []
        except Exception:
            ticker_list = []

        windows = {}
        for n, fwd_df in fwd_returns.items():
            returns = []
            for t in ticker_list:
                if t in fwd_df.columns and last_date in fwd_df.index:
                    val = fwd_df.loc[last_date, t]
                    if not pd.isna(val):
                        returns.append(val)
            windows[n] = _summarize(returns, f"{cfg['label']} {n}일", n)

        result[key] = {"label": cfg["label"], "windows": windows, "current_count": len(ticker_list)}

    return result


# ─────────────────────────────────────────────
# 통계 요약
# ─────────────────────────────────────────────

def _summarize(returns: list[float], label: str, window_days: int = 5) -> dict:
    """수익률 리스트 → 통계 요약 (hit_rate, sharpe, profit_factor, max_drawdown 등)."""
    if not returns:
        return {
            "label": label,
            "hit_rate": 0.0,
            "avg_return": 0.0,
            "median_return": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "sample_count": 0,
        }

    arr = np.array(returns)
    positive = (arr > 0).sum()
    total = len(arr)

    # 기본 통계
    hit_rate = round(positive / total * 100, 1)
    avg_ret = round(float(arr.mean()), 2)
    median_ret = round(float(np.median(arr)), 2)

    # profit_factor = 총이익 / 총손실 (손실 없으면 999)
    gains = arr[arr > 0].sum()
    losses = abs(arr[arr < 0].sum())
    profit_factor = round(gains / losses, 2) if losses > 0 else (999.0 if gains > 0 else 0.0)

    # max_drawdown (시그널 수익률 중 최악)
    max_dd = round(float(arr.min()), 2)

    # Sharpe ratio (연율화)
    std = float(arr.std())
    if std > 0 and window_days > 0:
        periods_per_year = TRADING_DAYS_YEAR / window_days
        rf_per_period = RISK_FREE_RATE / periods_per_year * 100  # % 단위
        excess = float(arr.mean()) - rf_per_period
        sharpe = round(excess / std * np.sqrt(periods_per_year), 2)
    else:
        sharpe = 0.0

    return {
        "label": label,
        "hit_rate": hit_rate,
        "avg_return": avg_ret,
        "median_return": median_ret,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "sample_count": total,
    }
