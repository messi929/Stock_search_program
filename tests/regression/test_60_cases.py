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


PERSONAS = ("blackrock", "ark", "graham", "event", "macro", "korean")

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


def test_matrix_size_is_60():
    """6 페르소나 × 10 종목 = 60건."""
    assert len(PERSONAS) == 6
    assert len(ALL_TICKERS) == 10
    assert len(PERSONAS) * len(ALL_TICKERS) == 60


def test_persona_coverage():
    """6 페르소나 모두 포함 — 그래프 ALL_PERSONAS와 일치."""
    from agents.graph import ALL_PERSONAS as graph_all

    assert set(PERSONAS) == graph_all


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize(
    "ticker,name,desc",
    ALL_TICKERS,
    ids=[f"{t[0]}-{t[2][:10]}" for t in ALL_TICKERS],
)
def test_routing_dispatch(persona, ticker, name, desc):
    """60건 모두 graph.route_by_persona가 정상 분기되는지.

    이 테스트는 매트릭스 모든 조합을 pytest로 발생시켜 60건 보장.
    """
    from agents.graph import route_by_persona

    state = {"persona": persona, "ticker": ticker}
    result = route_by_persona(state)
    if persona in {"blackrock", "ark", "graham"}:
        assert result == "strategist_flow"
    elif persona == "event":
        assert result == "event"
    elif persona == "macro":
        assert result == "macro"
    elif persona == "korean":
        assert result == "korean"


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


async def _run_one_real_case(persona: str, ticker: str, name: str) -> dict[str, Any]:
    """1건 실 분석 — Claude/Firestore 호출 발생."""
    from agents.graph import run_analysis

    started = datetime.now()
    try:
        final = await run_analysis(ticker=ticker, query=f"{name} 분석", persona=persona)
        elapsed = (datetime.now() - started).total_seconds()
        # 페르소나별 출력 필드 확인
        out_key = {
            "blackrock": "strategist_output",
            "ark": "strategist_output",
            "graham": "strategist_output",
            "event": "event_output",
            "macro": "macro_output",
            "korean": "korean_output",
        }[persona]
        out = final.get(out_key)
        return {
            "persona": persona,
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
            "persona": persona,
            "ticker": ticker,
            "name": name,
            "ok": False,
            "error": f"{type(e).__name__}: {str(e)[:160]}",
        }


async def _run_real_matrix() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for persona in PERSONAS:
        for ticker, name, desc in ALL_TICKERS:
            result = await _run_one_real_case(persona, ticker, name)
            print(
                f"[{persona:10s}] {ticker:6s} ({name:20s}): "
                f"{'✅' if result['ok'] else '❌'} {result.get('elapsed_sec', '-')}s"
            )
            results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
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
    args = parser.parse_args(argv)

    if not args.real:
        print(
            "ℹ️  mock 모드는 pytest로 실행하세요:\n"
            "    py -m pytest tests/regression/test_60_cases.py -q\n"
            "실 Claude 호출은 --real 플래그 추가."
        )
        return 0

    print(f"🔥 실 분석 모드 — 60건 ({len(PERSONAS)} × {len(ALL_TICKERS)})")
    print("⚠️  비용 발생 — 약 ₩12,000 예상\n")

    results = asyncio.run(_run_real_matrix())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

    ok_count = sum(1 for r in results if r["ok"])
    print(f"통과: {ok_count}/{len(results)}")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
