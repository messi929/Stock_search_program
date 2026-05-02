"""utils/data_collectors/valueup_index.py 단위 테스트.

데이터 파일 (data/valueup_index.json)을 실제로 로드하여 공개 함수 검증.
"""

from __future__ import annotations

import pytest

from utils.data_collectors import valueup_index as vi


@pytest.fixture(autouse=True)
def _reset_cache():
    """각 테스트 전후로 모듈 캐시 초기화 (테스트 격리)."""
    vi.reset_cache()
    yield
    vi.reset_cache()


def test_get_metadata_has_required_fields():
    meta = vi.get_metadata()
    assert "schema_version" in meta
    assert "index_name" in meta
    assert "data_completeness" in meta
    assert meta["index_name"].startswith("코리아 밸류업")


def test_get_latest_rebalancing_returns_2024_09_30():
    """현재 데이터는 2024-09-30 출시 시점 1건만 등록."""
    latest = vi.get_latest_rebalancing()
    assert latest is not None
    assert latest["rebalancing_date"] == "2024-09-30"
    assert len(latest["constituents"]) >= 30


def test_get_valueup_constituents_default_returns_latest():
    constituents = vi.get_valueup_constituents()
    assert len(constituents) >= 30
    # 모든 항목 ticker/name/sector 형식
    for c in constituents:
        assert c["ticker"].isdigit() and len(c["ticker"]) == 6
        assert c["name"]
        assert c["sector"]


def test_get_valueup_constituents_specific_date():
    constituents = vi.get_valueup_constituents("2024-09-30")
    assert len(constituents) >= 30


def test_get_valueup_constituents_unknown_date_returns_empty():
    assert vi.get_valueup_constituents("1900-01-01") == []


def test_is_in_valueup_index_samsung_electronics():
    """삼성전자 (005930)는 2024-09-30 출시 시점 편입."""
    result = vi.is_in_valueup_index("005930")
    assert result["included"] is True
    assert result["name"] == "삼성전자"
    assert result["sector"] == "반도체"
    assert result["since"] == "2024-09-30"
    assert "data_completeness" in result


def test_is_in_valueup_index_unknown_ticker_partial_data():
    """등록 안 된 티커 + data_completeness=partial → '커버 안 됨' 메모 포함."""
    result = vi.is_in_valueup_index("999999")
    assert result["included"] is False
    assert "전체 100종목 미커버" in result.get("note", "")


def test_is_in_valueup_index_zero_pads():
    """5자리 입력 → 6자리 zero-pad."""
    a = vi.is_in_valueup_index("5930")
    b = vi.is_in_valueup_index("005930")
    assert a == b


def test_get_recent_changes_no_changes():
    """현재 등록 데이터는 출시 시점이라 added/removed 모두 빈 list."""
    changes = vi.get_recent_changes()
    assert changes["added"] == []
    assert changes["removed"] == []


def test_is_in_valueup_index_handles_missing_data_file(monkeypatch, tmp_path):
    """JSON 파일 미존재 시 graceful (모든 결과 included=False)."""
    fake = tmp_path / "not_exist.json"
    monkeypatch.setattr(vi, "DATA_FILE", fake)
    vi.reset_cache()

    result = vi.is_in_valueup_index("005930")
    assert result["included"] is False
