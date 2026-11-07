"""수급·펀더멘탈 수집 회귀 테스트 (2026-11-07 무증상 고장).

- 네이버 구 페이지 폐지로 '200 + 빈 값'이 수집 성공으로 집계되던 문제
- pykrx 구간 조회 합산값이 당일 값으로 저장되던 문제
- 0건 수집이 옛 값을 '신선'하게 노출하던 문제
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from screener.api import routes
from screener.core import data_fetcher
from screener.db import repository


def _response(body):
    resp = MagicMock()
    resp.json.return_value = body
    return resp


def test_parse_naver_number():
    assert data_fetcher._parse_naver_number("8.68배") == 8.68
    assert data_fetcher._parse_naver_number("1,234.5배") == 1234.5
    assert data_fetcher._parse_naver_number("0.86%") == 0.86
    assert data_fetcher._parse_naver_number("N/A") == 0.0
    assert data_fetcher._parse_naver_number(None) == 0.0


def test_fundamental_parses_integration_api():
    body = {
        "industryCode": 278,
        "totalInfos": [
            {"code": "per", "value": "8.68배"},
            {"code": "pbr", "value": "2.25배"},
            {"code": "dividendYieldRatio", "value": "0.86%"},
        ],
    }
    with patch.object(data_fetcher.requests, "get", return_value=_response(body)):
        ticker, data = data_fetcher._fetch_single_fundamental("005930", {"278": "반도체"})

    assert ticker == "005930"
    assert data == {"per": 8.68, "pbr": 2.25, "div_yield": 0.86, "sector": "반도체"}


@pytest.mark.parametrize("body", [{"code": "NOT_FOUND"}, {"totalInfos": []}])
def test_fundamental_without_values_is_not_success(body):
    with patch.object(data_fetcher.requests, "get", return_value=_response(body)):
        assert data_fetcher._fetch_single_fundamental("091990") == ("091990", None)


def _pykrx_stub(by_day: dict) -> MagicMock:
    """by_day: {YYYYMMDD: DataFrame}. 구간 조회가 오면 실패시켜 단일일 조회를 강제."""
    def net_purchases(start, end, market, investor):
        assert start == end, "구간 조회는 합산값을 돌려주므로 금지"
        return by_day.get(start, pd.DataFrame())

    stock = MagicMock()
    stock.get_market_net_purchases_of_equities.side_effect = net_purchases
    module = MagicMock()
    module.stock = stock
    return module


def _days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y%m%d")


def _fetch_with(by_day: dict) -> dict:
    with patch.dict("sys.modules", {"pykrx": _pykrx_stub(by_day)}), \
            patch.object(data_fetcher.time, "sleep"):
        return data_fetcher._fetch_foreign_inst_pykrx()


def test_pykrx_uses_single_latest_trading_day():
    day = _days_ago(2)
    frame = pd.DataFrame({"순매수거래대금": [-115, 40]}, index=["005930", "000660"])

    result = _fetch_with({day: frame})

    assert result["005930"]["foreign_net"] == -115
    assert result["005930"]["date"] == f"{day[:4]}-{day[4:6]}-{day[6:]}"


def test_pykrx_skips_day_with_all_zero_values():
    zero = pd.DataFrame({"순매수거래대금": [0, 0]}, index=["005930", "000660"])
    real = pd.DataFrame({"순매수거래대금": [7, 0]}, index=["005930", "000660"])

    result = _fetch_with({_days_ago(0): zero, _days_ago(1): real})

    assert result["005930"]["foreign_net"] == 7


def test_pykrx_returns_empty_without_data():
    assert _fetch_with({}) == {}


def _save_history(existing: list, entry: dict) -> list:
    db = MagicMock()
    doc = db.collection.return_value.document.return_value
    doc.get.return_value.exists = True
    doc.get.return_value.to_dict.return_value = {"data": existing}
    with patch.object(repository, "get_db", return_value=db):
        repository.save_supply_history({"005930": entry})
    return db.batch.return_value.set.call_args[0][1]["data"]


def test_supply_history_uses_base_date_and_replaces_same_day():
    existing = [
        {"date": "2026-11-05", "foreign_net": 1, "inst_net": 0},
        {"date": "2026-11-06", "foreign_net": 2, "inst_net": 0},
    ]

    saved = _save_history(existing, {"foreign_net": 9, "inst_net": 3, "date": "2026-11-06"})

    assert [e["date"] for e in saved] == ["2026-11-05", "2026-11-06"]
    assert saved[-1]["foreign_net"] == 9


def test_supply_history_keeps_dates_sorted():
    existing = [{"date": "2026-11-07", "foreign_net": 2, "inst_net": 0}]

    saved = _save_history(existing, {"foreign_net": 9, "inst_net": 3, "date": "2026-11-06"})

    assert [e["date"] for e in saved] == ["2026-11-06", "2026-11-07"]


def test_kis_entry_converts_to_won_and_keeps_base_date():
    rows = [
        {"stck_bsop_date": "20261107", "stck_clpr": "", "frgn_ntby_qty": "", "orgn_ntby_qty": ""},
        {"stck_bsop_date": "20261106", "stck_clpr": "100", "frgn_ntby_qty": "-3", "orgn_ntby_qty": "2"},
    ]

    assert data_fetcher._kis_supply_entry(rows) == {
        "foreign_net": -300, "inst_net": 200, "date": "2026-11-06",
    }


def test_kis_entry_without_data_is_none():
    assert data_fetcher._kis_supply_entry([{"stck_clpr": "100"}]) is None


def test_empty_sector_does_not_overwrite_saved_value():
    doc = repository._row_to_doc({"ticker": "005930", "sector": "", "industry": ""})
    assert "sector" not in doc and "industry" not in doc

    doc = repository._row_to_doc({"ticker": "005930", "sector": "반도체", "industry": "반도체"})
    assert doc["sector"] == "반도체"


def test_foreign_inst_freshness_flags_stale_supply():
    meta = {
        "stocks_kr_updated_at": "2026-11-06T17:30:00",
        "foreign_inst_updated_at": "2026-09-08T08:13:00",
    }
    with patch.object(routes, "_get_sync_meta", return_value=meta):
        out = routes._data_freshness("foreign_inst", "KR")

    assert out["data_fresh"] is False
    assert "외국인·기관 수급" in out["freshness_note"]


def test_foreign_inst_freshness_ok_when_recent():
    meta = {
        "stocks_kr_updated_at": "2026-11-06T17:30:00",
        "foreign_inst_updated_at": "2026-11-06T17:35:00",
    }
    with patch.object(routes, "_get_sync_meta", return_value=meta):
        assert routes._data_freshness("foreign_inst", "KR")["data_fresh"] is True


def test_collect_foreign_inst_raises_on_zero_rows():
    import collector

    with patch("screener.core.data_fetcher.fetch_foreign_inst", return_value={}), \
            patch("screener.db.repository.load_stocks", return_value=None), \
            patch("screener.db.repository.save_stocks") as save:
        with pytest.raises(RuntimeError):
            collector.collect_foreign_inst()

    save.assert_not_called()
