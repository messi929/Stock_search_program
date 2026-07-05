"""교육 콘텐츠 생성기 단위 테스트 (LLM 비호출 결정론 부분).

토픽 뱅크 정합성 + 토픽 선정(중복 회피·시리즈 한정) 검증. 실 Sonnet 생성은
integration 마커(비용) — `pytest --run-integration` 시에만.

실행:
    py -m pytest tests/test_education.py -q
"""

from __future__ import annotations

import pytest

from agents.education import _SERIES_LABEL, _TOPICS, pick_topic


def test_topic_bank_integrity():
    keys = [t["key"] for t in _TOPICS]
    assert len(keys) == len(set(keys)), "topic key 중복"
    for t in _TOPICS:
        assert t["series"] in _SERIES_LABEL, f"알 수 없는 시리즈: {t['series']}"
        for field in ("key", "title", "teach", "example_fit"):
            assert t[field].strip(), f"{t['key']}.{field} 비어 있음"
        # 교육 글은 개념 사실이 생명 — teach가 최소한의 분량을 갖는지.
        assert len(t["teach"]) >= 40, f"{t['key']} teach 너무 짧음"


def test_both_series_present():
    series = {t["series"] for t in _TOPICS}
    assert series == {"psychology", "metric"}


def test_pick_topic_respects_series():
    for _ in range(20):
        t = pick_topic(series=["metric"])
        assert t is not None and t["series"] == "metric"


def test_pick_topic_avoids_recent():
    metric_keys = [t["key"] for t in _TOPICS if t["series"] == "metric"]
    # metric 전체 중 하나만 남기고 다 회피 → 그 하나가 뽑혀야 한다.
    keep = metric_keys[0]
    avoid = metric_keys[1:]
    for _ in range(20):
        t = pick_topic(series=["metric"], avoid_keys=avoid)
        assert t is not None and t["key"] == keep


def test_pick_topic_all_exhausted_falls_back():
    all_keys = [t["key"] for t in _TOPICS]
    t = pick_topic(avoid_keys=all_keys)  # 전부 회피해도 None 아님(전체 순환)
    assert t is not None
    assert t["key"] in all_keys


def test_pick_topic_empty_series():
    assert pick_topic(series=["nonexistent"]) is None
