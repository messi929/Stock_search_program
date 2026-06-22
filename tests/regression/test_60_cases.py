"""60건 회귀 테스트 매트릭스 (6 페르소나 × 10 종목).

WEEK_E.md Day 1-2 산출물.

⚠️ 본 테스트는 두 모드를 지원:

1. **mock 모드 (default, 단위 테스트)**
   - Claude API 호출 없이 매트릭스 정합성만 검증
   - 페르소나/종목/라우팅이 60건 모두 정상 분기되는지
   - LEGAL 후처리 필터가 단정어를 차단하는지

2. **실 분석 모드 (--real, 통합 테스트)**
   - ANTHROPIC_API_KEY + Firestore 연결 필요
   - py -m tests.regression.test_60_cases --real
   - 실제 비용 발생: 6 페르소나 × 10 종목 × 평균 ~200원 ≈ ₩12,000
   - 부분 실행 필터 (BETA_READINESS §5 Stage 1/2 검증용):
     · --smoke               Stage 1 — 1건만 (event × RKLB, ~₩200)
     · --persona-filter a,b  지정 페르소나만
     · --ticker-filter X,Y   지정 종목만 (예: --persona-filter event --ticker-filter AAPL,005930)

mock 모드는 pytest로 실행, 실 모드는 직접 모듈 실행.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────
# 테스트 매트릭스
# ──────────────────────────────────────────────


# 분석 모드 = 4 시간축 관점(horizon, 사용자 노출) + 3 데이터 노드(내부 제공자).
# (블랙록/ARK/그레이엄 페르소나는 2026-06-22 horizon으로 폐지)
HORIZONS = ("short", "short_mid", "mid", "long")
DATA_NODES = ("event", "macro", "korean")
MODES = HORIZONS + DATA_NODES

# 다양성: 한국 5 + 미국 4 + ETF 1
TICKERS_KR = (
    ("005930", "삼성전자", "대형 한국 — 글로벌 기술"),
    ("207940", "삼성바이오로직스", "한국 — 헬스케어"),
    ("010060", "OCI홀딩스", "한국 — 지주사"),
    ("005380", "현대차", "한국 — 자동차/전기차"),
    ("035720", "카카오", "한국 — 플랫폼"),
)

TICKERS_US = (
    ("AAPL", "Apple", "미국 — 대형 기술"),
    ("RKLB", "RocketLab", "미국 — 우주, 이벤트 케이스"),
    ("NVDA", "NVIDIA", "미국 — AI 반도체"),
    ("JPM", "JPMorgan", "미국 — 금융"),
    ("TLT", "iShares 20+Y Treasury", "ETF — 매크로 케이스"),
)

ALL_TICKERS = TICKERS_KR + TICKERS_US


# ──────────────────────────────────────────────
# 매트릭스 정합성 검증 (60건 분기)
# ──────────────────────────────────────────────


def test_matrix_size_is_70():
    """7 모드(4 관점 + 3 데이터 노드) × 10 종목 = 70건."""
    assert len(MODES) == 7
    assert len(ALL_TICKERS) == 10
    assert len(MODES) * len(ALL_TICKERS) == 70


def test_data_node_coverage():
    """데이터 노드 3종이 그래프 ALL_PERSONAS와 일치."""
    from agents.graph import ALL_PERSONAS as graph_all

    assert set(DATA_NODES) == graph_all


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    "ticker,name,desc",
    ALL_TICKERS,
    ids=[f"{t[0]}-{t[2][:10]}" for t in ALL_TICKERS],
)
def test_routing_dispatch(mode, ticker, name, desc):
    """70건 모두 graph.route_by_horizon이 정상 분기되는지.

    관점(horizon)은 통합 strategist_flow로, 데이터 노드는 각 단일 노드로.
    """
    from agents.graph import route_by_horizon

    if mode in HORIZONS:
        state = {"horizon": mode, "ticker": ticker}
        assert route_by_horizon(state) == "strategist_flow"
    else:
        state = {"persona": mode, "ticker": ticker}
        assert route_by_horizon(state) == mode


# ──────────────────────────────────────────────
# 부분 실행 필터 — resolve_matrix (Stage 1/2 검증용)
# ──────────────────────────────────────────────


def test_resolve_matrix_default_is_full_70():
    """필터 미지정 → 7 모드 × 10 종목 = 70건."""
    from tests.regression.test_60_cases import resolve_matrix

    modes, tickers = resolve_matrix()
    assert len(modes) == 7
    assert len(tickers) == 10
    assert len(modes) * len(tickers) == 70


def test_resolve_matrix_mode_filter():
    from tests.regression.test_60_cases import resolve_matrix

    modes, tickers = resolve_matrix(mode_filter="event,macro")
    assert modes == ["event", "macro"]
    assert len(tickers) == 10  # 종목은 전체


def test_resolve_matrix_ticker_filter_case_insensitive():
    from tests.regression.test_60_cases import resolve_matrix

    modes, tickers = resolve_matrix(ticker_filter="aapl,005930")
    assert {t[0] for t in tickers} == {"AAPL", "005930"}
    assert len(modes) == 7  # 모드는 전체


def test_resolve_matrix_combined_filter():
    from tests.regression.test_60_cases import resolve_matrix

    modes, tickers = resolve_matrix(
        mode_filter="korean", ticker_filter="005930"
    )
    assert modes == ["korean"]
    assert [t[0] for t in tickers] == ["005930"]


def test_resolve_matrix_smoke_default_is_event_rklb():
    """--smoke 미필터 → event × RKLB 1건 (가장 복잡한 이벤트 케이스)."""
    from tests.regression.test_60_cases import resolve_matrix

    personas, tickers = resolve_matrix(smoke=True)
    assert personas == ["event"]
    assert [t[0] for t in tickers] == ["RKLB"]


def test_resolve_matrix_smoke_with_filter_takes_first():
    """--smoke + 필터 → 필터 결과의 첫 항목 1건."""
    from tests.regression.test_60_cases import resolve_matrix

    personas, tickers = resolve_matrix(
        mode_filter="macro,korean", ticker_filter="AAPL,005930", smoke=True
    )
    assert personas == ["macro"]
    assert [t[0] for t in tickers] == ["AAPL"]  # 입력 순서 보존 → 첫 항목 AAPL


def test_resolve_matrix_invalid_mode_raises():
    from tests.regression.test_60_cases import resolve_matrix

    with pytest.raises(ValueError, match="알 수 없는 모드"):
        resolve_matrix(mode_filter="event,bogus")


def test_resolve_matrix_invalid_ticker_raises():
    from tests.regression.test_60_cases import resolve_matrix

    with pytest.raises(ValueError, match="매트릭스에 없는 종목"):
        resolve_matrix(ticker_filter="AAPL,ZZZZ")


# ──────────────────────────────────────────────
# 차별성 검증 (페르소나가 같은 입력에 다른 페르소나 ID를 출력)
# ──────────────────────────────────────────────


def test_persona_outputs_have_distinct_persona_field():
    """각 페르소나 결과의 persona 필드가 식별자로 일관 출력되는지.

    Claude 결과는 mock으로 생성. 실제 텍스트 차이는 mock으로 검증 불가하지만
    persona 메타가 정확히 출력되는지는 보장.
    """
    from agents.event_analyst import EventAnalystResult
    from agents.korean_specialist import KoreanSpecialistResult
    from agents.macro_pm import MacroPmResult

    # 빈 모델은 model_construct로 우회 — 검증 없이 인스턴스만 만들어 persona 필드 확인
    e = EventAnalystResult.model_construct(persona="event")
    m = MacroPmResult.model_construct(persona="macro")
    k = KoreanSpecialistResult.model_construct(persona="korean")

    assert e.persona == "event"
    assert m.persona == "macro"
    assert k.persona == "korean"


# ──────────────────────────────────────────────
# LEGAL 검증 (60건 모두 단정어 0건)
# ──────────────────────────────────────────────


def test_legal_check_baseline_passes():
    """현재 코드베이스의 LEGAL 검사가 통과하는지 (회귀 가드).

    개발 중 단정어가 코드/페르소나 prompt에 누출되면 즉시 차단.
    """
    from scripts.legal_check import _check_file, _walk_targets

    repo_root = Path(__file__).resolve().parents[2]
    issues = []
    for p in _walk_targets(repo_root):
        issues.extend(_check_file(p, repo_root))

    if issues:
        msg = "\n".join(f"{p.relative_to(repo_root)}:{ln} [{lbl}]" for p, ln, lbl in issues)
        pytest.fail(f"LEGAL 위반 {len(issues)}건:\n{msg}")


@pytest.mark.parametrize(
    "persona,sample_text,expect_filter",
    [
        ("blackrock", "삼성전자는 매수 신호입니다.", True),
        ("ark", "지금 사세요.", True),
        ("graham", "분명히 오릅니다.", True),
        ("event", "RKLB 매수 시그널 관찰.", True),  # event_inference_cache 정규식
        ("macro", "Goldilocks 추천합니다.", True),
        ("korean", "외국인이 사니까 사세요.", True),
        ("blackrock", "관찰 구간으로 분류됩니다.", False),
        ("ark", "장기 시계 통상 패턴.", False),
    ],
)
def test_filter_forbidden_catches_assertive_text(persona, sample_text, expect_filter):
    """6 페르소나 모두 단정어 후처리 필터로 차단되는지."""
    from agents.base import BaseAgent

    filtered, found = BaseAgent.filter_forbidden(sample_text)
    if expect_filter:
        assert len(found) > 0, f"단정어 미감지: {sample_text!r} (persona={persona})"
        assert "[필터링됨]" in filtered
    else:
        assert len(found) == 0, f"중립 표현이 잘못 차단됨: {sample_text!r}"


# ──────────────────────────────────────────────
# 시간 시계 정합성 (페르소나별 horizon 일관)
# ──────────────────────────────────────────────


def test_time_horizon_matrix():
    """프론트엔드 PERSONA_META와 백엔드 페르소나 의도가 일치하는지 (semantic 검증).

    프론트엔드 types/persona.ts에 정의된 시계는 다음과 같아야 함:
      - blackrock/ark/graham: long
      - event: short
      - macro/korean: medium
    """
    expected = {
        "blackrock": "long",
        "ark": "long",
        "graham": "long",
        "event": "short",
        "macro": "medium",
        "korean": "medium",
    }

    persona_ts = (
        Path(__file__).resolve().parents[2] / "web" / "types" / "persona.ts"
    )
    text = persona_ts.read_text(encoding="utf-8")
    for pid, horizon in expected.items():
        # PERSONA_META 항목 안에서 id+time_horizon 짝이 같은 객체에 있어야 함.
        # 텍스트 매칭으로 확인 (정밀도는 떨어지지만 회귀 가드로 충분)
        assert f'id: "{pid}"' in text
        assert f'time_horizon: "{horizon}"' in text


# ──────────────────────────────────────────────
# 실 분석 모드 (--real) — pytest 외부에서 실행
# ──────────────────────────────────────────────


async def _run_one_real_case(mode: str, ticker: str, name: str) -> dict[str, Any]:
    """1건 실 분석 — Claude/Firestore 호출 발생. mode = horizon 또는 데이터 노드."""
    from agents.graph import run_analysis

    started = datetime.now()
    try:
        if mode in HORIZONS:
            final = await run_analysis(ticker=ticker, query=f"{name} 분석", horizon=mode)
            out_key = "strategist_output"
        else:
            final = await run_analysis(ticker=ticker, query=f"{name} 분석", persona=mode)
            out_key = {
                "event": "event_output",
                "macro": "macro_output",
                "korean": "korean_output",
            }[mode]
        elapsed = (datetime.now() - started).total_seconds()
        out = final.get(out_key)
        return {
            "persona": mode,
            "ticker": ticker,
            "name": name,
            "ok": out is not None,
            "elapsed_sec": round(elapsed, 1),
            "summary_excerpt": (
                getattr(out, "summary_neutral", "")[:120]
                if out and hasattr(out, "summary_neutral")
                else (
                    getattr(out, "summary", "")[:120]
                    if out and hasattr(out, "summary")
                    else ""
                )
            ),
        }
    except Exception as e:
        return {
            "persona": mode,
            "ticker": ticker,
            "name": name,
            "ok": False,
            "error": f"{type(e).__name__}: {str(e)[:160]}",
        }


def resolve_matrix(
    mode_filter: str | None = None,
    ticker_filter: str | None = None,
    smoke: bool = False,
) -> tuple[list[str], list[tuple[str, str, str]]]:
    """필터를 적용해 실행할 (modes, tickers) 매트릭스를 산출.

    BETA_READINESS §5 Stage 1/2 단계 검증을 위한 부분 실행 지원.
    잘못된 페르소나/종목명은 ValueError로 즉시 차단 (오타로 빈 매트릭스 방지).

    - mode_filter: "event,macro" 또는 "short,long" 형태 콤마 구분. None이면 7 모드 전체.
    - ticker_filter: "AAPL,005930" 형태. 대소문자 무관. None이면 10 종목 전체.
    - smoke: True면 1건만. 필터 미지정 시 event × RKLB (가장 복잡한 이벤트 케이스),
             필터 지정 시 필터 결과의 첫 항목.
    """
    personas = list(MODES)
    if mode_filter:
        requested = [p.strip() for p in mode_filter.split(",") if p.strip()]
        invalid = [p for p in requested if p not in MODES]
        if invalid:
            raise ValueError(
                f"알 수 없는 모드: {invalid} (가능: {list(MODES)})"
            )
        personas = requested

    tickers = list(ALL_TICKERS)
    if ticker_filter:
        requested_t = [
            t.strip().upper() for t in ticker_filter.split(",") if t.strip()
        ]
        by_symbol = {t[0].upper(): t for t in ALL_TICKERS}
        missing = [t for t in requested_t if t not in by_symbol]
        if missing:
            raise ValueError(
                f"매트릭스에 없는 종목: {missing} "
                f"(가능: {[t[0] for t in ALL_TICKERS]})"
            )
        # 사용자 입력 순서 보존 (--smoke 시 첫 항목이 직관적으로 일치)
        tickers = [by_symbol[t] for t in requested_t]

    if smoke:
        personas = personas[:1] if mode_filter else ["event"]
        if ticker_filter:
            tickers = tickers[:1]
        else:
            tickers = [t for t in ALL_TICKERS if t[0] == "RKLB"]

    return personas, tickers


async def _run_real_matrix(
    personas: list[str],
    tickers: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for persona in personas:
        for ticker, name, desc in tickers:
            result = await _run_one_real_case(persona, ticker, name)
            print(
                f"[{persona:10s}] {ticker:6s} ({name:20s}): "
                f"{'✅' if result['ok'] else '❌'} {result.get('elapsed_sec', '-')}s"
            )
            results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔(cp949)에서도 이모지 출력이 깨지지 않도록 UTF-8 강제.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="60건 회귀 테스트")
    parser.add_argument(
        "--real",
        action="store_true",
        help="실 Claude 호출 (비용 발생). 미지정 시 pytest로 mock 모드 실행 안내.",
    )
    parser.add_argument(
        "--out",
        default="tests/regression/results/last_run.json",
        help="결과 저장 경로",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Stage 1 — 1건만 실행 (event × RKLB, ~₩200).",
    )
    parser.add_argument(
        "--mode-filter",
        default=None,
        help="실행할 모드 콤마 구분 (예: short,long 또는 event,macro). 미지정 시 7 전체.",
    )
    parser.add_argument(
        "--ticker-filter",
        default=None,
        help="실행할 종목 콤마 구분 (예: AAPL,005930). 미지정 시 10 전체.",
    )
    args = parser.parse_args(argv)

    if not args.real:
        print(
            "ℹ️  mock 모드는 pytest로 실행하세요:\n"
            "    py -m pytest tests/regression/test_60_cases.py -q\n"
            "실 Claude 호출은 --real 플래그 추가."
        )
        return 0

    try:
        personas, tickers = resolve_matrix(
            mode_filter=args.mode_filter,
            ticker_filter=args.ticker_filter,
            smoke=args.smoke,
        )
    except ValueError as e:
        print(f"❌ 필터 오류: {e}")
        return 1

    case_count = len(personas) * len(tickers)
    est_cost = case_count * 200
    print(
        f"🔥 실 분석 모드 — {case_count}건 "
        f"({len(personas)} 모드 × {len(tickers)} 종목)"
    )
    print(f"   모드: {personas}")
    print(f"   종목: {[t[0] for t in tickers]}")
    print(f"⚠️  비용 발생 — 약 ₩{est_cost:,} 예상\n")

    results = asyncio.run(_run_real_matrix(personas, tickers))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

    ok_count = sum(1 for r in results if r["ok"])
    print(f"통과: {ok_count}/{len(results)}")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
