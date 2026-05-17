"""v2 페르소나별 예상 비용 추정 (Week E Day 4).

실 호출 없이 페르소나별 Claude 모델/토큰 추정치를 곱해 1회 분석 비용을 산출.

산출 모드:
  1. theoretical (default) — 시스템 프롬프트 길이 + 평균 입력/출력 토큰 추정값
  2. profiled — Firestore ai_usage 통계 기반 실측 (별도 PR)

가격표는 utils/cost_tracker.py 사용.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass


from utils.claude_client import MODEL_HAIKU, MODEL_OPUS, MODEL_SONNET
from utils.cost_tracker import USD_TO_KRW, calculate_cost  # noqa: E402

# Pydantic-free ClaudeUsage 모방 (cost_tracker가 dataclass-like duck typing)
@dataclass
class _Usage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


# ──────────────────────────────────────────────
# 페르소나별 예상 토큰 (실측 기반 추정)
# ──────────────────────────────────────────────
#
# 기준:
#   system_prompt_tokens = file 길이 / 3 (대략 1 token ≈ 3 chars 한국어 + JSON)
#   user_message_tokens  = 페르소나별 입력 데이터 크기 + 프레이밍
#   output_tokens        = 응답 JSON 평균 (max_tokens 설정 기반 보수적)
#   prompt cache         = 시스템 프롬프트가 1024+ tokens일 때 자동 cache_creation 1회 + 이후 cache_read
#
# Strategist (blackrock/ark/graham): research+analyst+validator 결과를 user에 인라인.
# Event Analyst: Week C 데이터 인프라 결과 + 4차원 점수 + 시나리오.
# Macro PM: cycle/regime 정량 결과 + 시장별 가중치.
# Korean Specialist: Week A 6 모듈 결과 + 5변수 점수.

PERSONA_PROFILES: dict[str, dict] = {
    "blackrock": {
        "model": MODEL_OPUS,
        "max_tokens": 1500,
        "system_chars": 1800,  # personas/blackrock.md
        "user_input_chars_avg": 4500,  # research+analyst+validator
        "expected_output_tokens": 1500,
    },
    "ark": {
        "model": MODEL_OPUS,
        "max_tokens": 1500,
        "system_chars": 1800,
        "user_input_chars_avg": 4500,
        "expected_output_tokens": 1500,
    },
    "graham": {
        "model": MODEL_OPUS,
        "max_tokens": 1500,
        "system_chars": 1800,
        "user_input_chars_avg": 4500,
        "expected_output_tokens": 1500,
    },
    "event": {
        "model": MODEL_SONNET,
        "max_tokens": 2500,
        "system_chars": 4900,  # personas/event.md (v2.1 가장 길음)
        "user_input_chars_avg": 2800,
        "expected_output_tokens": 2200,
    },
    "macro": {
        "model": MODEL_SONNET,
        "max_tokens": 2200,
        "system_chars": 2520,
        "user_input_chars_avg": 1800,
        "expected_output_tokens": 1900,
    },
    "korean": {
        "model": MODEL_SONNET,
        "max_tokens": 2200,
        "system_chars": 2960,
        "user_input_chars_avg": 2400,
        "expected_output_tokens": 2000,
    },
    # 보조 에이전트 (Strategist 흐름 내부)
    "research": {
        "model": MODEL_HAIKU,
        "max_tokens": 1024,
        "system_chars": 800,
        "user_input_chars_avg": 1200,
        "expected_output_tokens": 700,
    },
    "analyst": {
        "model": MODEL_SONNET,
        "max_tokens": 2048,
        "system_chars": 1800,
        "user_input_chars_avg": 2200,
        "expected_output_tokens": 1500,
    },
    "validator": {
        "model": MODEL_SONNET,
        "max_tokens": 1500,
        "system_chars": 1500,
        "user_input_chars_avg": 3500,
        "expected_output_tokens": 1100,
    },
}


def chars_to_tokens(chars: int) -> int:
    """한국어 + JSON 혼합에서 char → token 대략 변환 (1 token ≈ 3 chars)."""
    return max(1, chars // 3)


def estimate_persona_cost(persona: str, *, prompt_cache_hit: bool = False) -> dict:
    """1회 호출 비용 추정.

    Args:
        prompt_cache_hit: True면 system prompt가 cache_read로 처리되어
                          input 비용 90% 절감. 첫 호출은 False(cache_creation).
    """
    p = PERSONA_PROFILES[persona]
    sys_tokens = chars_to_tokens(p["system_chars"])
    user_tokens = chars_to_tokens(p["user_input_chars_avg"])
    out_tokens = p["expected_output_tokens"]

    if prompt_cache_hit:
        usage = _Usage(
            input_tokens=user_tokens,
            output_tokens=out_tokens,
            cache_read_tokens=sys_tokens,
        )
    else:
        # 첫 호출 — cache_creation (시스템 프롬프트가 1024+ tokens일 때만)
        if sys_tokens >= 1024:
            usage = _Usage(
                input_tokens=user_tokens,
                output_tokens=out_tokens,
                cache_creation_tokens=sys_tokens,
            )
        else:
            usage = _Usage(
                input_tokens=user_tokens + sys_tokens,
                output_tokens=out_tokens,
            )

    cost = calculate_cost(p["model"], usage)
    return {
        "persona": persona,
        "model": p["model"],
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "cache_read": cost.cache_read_tokens,
        "cache_creation": cost.cache_creation_tokens,
        "usd": cost.usd,
        "krw": cost.krw,
    }


def print_persona_table():
    """6 페르소나 + 보조 3 에이전트 1회 호출 비용 표."""
    print(
        f"\n{'페르소나':<12} {'모델':<25} {'in':>6} {'out':>6} "
        f"{'cache':>6} {'USD':>10} {'KRW':>10}"
    )
    print("─" * 80)

    print("\n[페르소나 — 사용자 노출]")
    for p in ("blackrock", "ark", "graham", "event", "macro", "korean"):
        # 첫 호출 (cache_creation) + 이후 호출 (cache_read) 모두 표시
        first = estimate_persona_cost(p, prompt_cache_hit=False)
        warm = estimate_persona_cost(p, prompt_cache_hit=True)
        print(
            f"{p:<12} {first['model']:<25} "
            f"{first['input_tokens']:>6} {first['output_tokens']:>6} "
            f"{first['cache_creation']:>6} "
            f"${first['usd']:>9.4f} ₩{first['krw']:>8.1f}  (cold)"
        )
        print(
            f"{'':<12} {'':<25} "
            f"{warm['input_tokens']:>6} {warm['output_tokens']:>6} "
            f"{warm['cache_read']:>6} "
            f"${warm['usd']:>9.4f} ₩{warm['krw']:>8.1f}  (warm)"
        )

    print("\n[보조 에이전트 — Strategist 흐름 내부]")
    for p in ("research", "analyst", "validator"):
        warm = estimate_persona_cost(p, prompt_cache_hit=True)
        print(
            f"{p:<12} {warm['model']:<25} "
            f"{warm['input_tokens']:>6} {warm['output_tokens']:>6} "
            f"{warm['cache_read']:>6} "
            f"${warm['usd']:>9.4f} ₩{warm['krw']:>8.1f}"
        )

    # ── 사용 시나리오별 합계 ──
    print("\n[1회 분석 합계 — 동일 페르소나 캐시 warm 가정]\n")
    print("Strategist 페르소나 (예: blackrock):")
    s_research = estimate_persona_cost("research", prompt_cache_hit=True)
    s_analyst = estimate_persona_cost("analyst", prompt_cache_hit=True)
    s_validator = estimate_persona_cost("validator", prompt_cache_hit=True)
    s_strategist = estimate_persona_cost("blackrock", prompt_cache_hit=True)
    sum_warm = (
        s_research["krw"] + s_analyst["krw"] + s_validator["krw"] + s_strategist["krw"]
    )
    print(
        f"  research + analyst + validator + strategist "
        f"= ₩{s_research['krw']:.1f} + ₩{s_analyst['krw']:.1f} + "
        f"₩{s_validator['krw']:.1f} + ₩{s_strategist['krw']:.1f} = ₩{sum_warm:.1f}"
    )

    print("\n신규 데이터 페르소나 (event/macro/korean) — 단독 호출:")
    for p in ("event", "macro", "korean"):
        warm = estimate_persona_cost(p, prompt_cache_hit=True)
        print(f"  {p}: ₩{warm['krw']:.1f}")

    print(f"\n환율 USD→KRW = {USD_TO_KRW}")


# ──────────────────────────────────────────────
# 최적화 옵션 검토 출력
# ──────────────────────────────────────────────


def print_optimization_options():
    print("\n[최적화 옵션 — Week E Day 4 검토]\n")
    print("Option 1: Strategist Sonnet 다운그레이드")
    opus = estimate_persona_cost("blackrock", prompt_cache_hit=True)
    # Sonnet 가정으로 임시 재계산
    p = PERSONA_PROFILES["blackrock"]
    sonnet_usage = _Usage(
        input_tokens=chars_to_tokens(p["user_input_chars_avg"]),
        output_tokens=p["expected_output_tokens"],
        cache_read_tokens=chars_to_tokens(p["system_chars"]),
    )
    sonnet = calculate_cost(MODEL_SONNET, sonnet_usage)
    saved_pct = 100 * (1 - sonnet.krw / opus["krw"]) if opus["krw"] else 0
    print(
        f"  현재 Opus warm ₩{opus['krw']:.1f} → Sonnet ₩{sonnet.krw:.1f} "
        f"(절감 {saved_pct:.0f}%)"
    )
    print(
        "  검증 필요: 회귀 테스트 60건 Sonnet 재실행 후 품질 비교 (Week E Day 5 backlog)"
    )

    print("\nOption 2: 페르소나별 프롬프트 캐싱 (현재 자동 적용)")
    print(
        "  utils/claude_client._build_system_param()는 system >=1024 chars면 "
        "ephemeral cache_control 자동 적용"
    )
    print("  → cold/warm 차이는 위 표 참고 (warm은 입력 비용 90% 절감)")

    print("\nOption 3: 페르소나별 데이터 재사용 (Strategist 흐름)")
    print(
        "  research/analyst/validator는 페르소나 무관 → 같은 ticker 재분석 시 "
        "Firestore 캐시로 1회만 호출 가능"
    )
    print(
        "  현재 utils/cache.py는 메모리 단위 1시간 TTL — Week E backlog: Firestore 캐시 전환"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v2 페르소나 예상 비용 추정")
    parser.add_argument(
        "--no-options",
        action="store_true",
        help="최적화 옵션 출력 생략",
    )
    args = parser.parse_args(argv)

    print("=" * 80)
    print("Axis v2 페르소나 1회 호출 비용 추정 (theoretical)")
    print("=" * 80)
    print_persona_table()

    if not args.no_options:
        print_optimization_options()

    return 0


if __name__ == "__main__":
    sys.exit(main())
