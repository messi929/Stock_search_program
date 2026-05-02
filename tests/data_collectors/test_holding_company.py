"""utils/data_collectors/holding_company.py 단위 테스트.

검증:
  1. classify_discount 4단계 분류 임계값
  2. calculate_nav_discount 정상 계산 (mock 시총 주입)
  3. 누락 ticker → None
  4. 자회사 시총 일부 누락 → missing_subsidiary_caps에 기록
  5. 지주사 자체 시총 0 → discount_pct=None + "산정 불가"
  6. Firestore 예외 graceful 처리
  7. calculate_all → 5개 지주사 결과
  8. HOLDING_COMPANIES 데이터 sanity (ticker 형식 + 지분율 범위)
  9. chaebol_groups.json 데이터 sanity (필수 필드 + 검증 그룹 수)
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.data_collectors.holding_company import (
    HOLDING_COMPANIES,
    HoldingCompanyAnalyzer,
    classify_discount,
)


# ──────────────────────────────────────────────
# 1. classify_discount 4단계
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "pct,expected_label_prefix",
    [
        (0.0, "낮음"),
        (15.0, "낮음"),
        (19.99, "낮음"),
        (20.0, "중간"),
        (35.0, "중간"),
        (39.99, "중간"),
        (40.0, "높음"),
        (55.5, "높음"),
        (59.99, "높음"),
        (60.0, "매우 높음"),
        (75.0, "매우 높음"),
        (100.0, "매우 높음"),
    ],
)
def test_classify_discount_thresholds(pct, expected_label_prefix):
    label = classify_discount(pct)
    assert label.startswith(expected_label_prefix), f"pct={pct} → {label!r}"


# ──────────────────────────────────────────────
# 2-6. NAV 계산 logic
# ──────────────────────────────────────────────


def _mk_db_with_caps(market_caps_eok: dict[str, float | None]) -> MagicMock:
    """Firestore mock — ticker별 market_cap 주입.

    Args:
        market_caps_eok: {ticker: 시총(억원) 또는 None(=doc 미존재)}
    """
    db = MagicMock()

    def _document_factory(ticker: str):
        cap = market_caps_eok.get(ticker)
        if cap is None:
            doc = SimpleNamespace(exists=False, to_dict=lambda: {})
        else:
            doc = SimpleNamespace(exists=True, to_dict=lambda c=cap: {"market_cap": c})
        getter = MagicMock()
        getter.get.return_value = doc
        return getter

    db.collection.return_value.document.side_effect = _document_factory
    return db


def test_calculate_nav_discount_lg_normal_case():
    """LG 지주사: 자회사 4개 + 지주사 시총 → NAV/discount 정확히 계산.

    가설:
      LG전자 시총 200,000억 × 33.7% = 67,400억
      LG화학 시총 300,000억 × 33.3% = 99,900억
      LG생활건강 시총 50,000억 × 30.0% = 15,000억
      LG유플러스 시총 50,000억 × 37.7% = 18,850억
      net_cash = 0
      NAV = 201,150억
      LG (003550) 시총 = 100,000억
      Discount = (201,150 - 100,000) / 201,150 × 100 = 50.29%
      → "높음 (가치 vs 거버넌스 갈등)"
    """
    db = _mk_db_with_caps(
        {
            "066570": 200_000.0,
            "051910": 300_000.0,
            "051900": 50_000.0,
            "032640": 50_000.0,
            "003550": 100_000.0,
        }
    )
    analyzer = HoldingCompanyAnalyzer(db=db)

    result = analyzer.calculate_nav_discount("003550")

    assert result is not None
    assert result["ticker"] == "003550"
    assert result["name"] == "LG"
    assert result["nav_eok"] == 201_150.0
    assert result["market_cap_eok"] == 100_000.0
    assert result["discount_pct"] == round((201_150 - 100_000) / 201_150 * 100, 2)
    assert result["interpretation"].startswith("높음")
    assert result["missing_subsidiary_caps"] == []
    assert len(result["subsidiaries"]) == 4
    # 지분 가치 검증
    lg_elec = next(s for s in result["subsidiaries"] if s["ticker"] == "066570")
    assert lg_elec["stake_value_eok"] == 67_400.0
    # 메타 보존
    assert result["metadata"]["as_of"] == "2024-12-31"
    assert "computed_at" in result


def test_calculate_nav_discount_unknown_ticker_returns_none():
    db = _mk_db_with_caps({})
    analyzer = HoldingCompanyAnalyzer(db=db)

    assert analyzer.calculate_nav_discount("999999") is None


def test_calculate_nav_discount_missing_subsidiary_caps_recorded():
    """일부 자회사 시총 조회 실패 시 missing_subsidiary_caps에 기록 + 누락분 0 처리."""
    db = _mk_db_with_caps(
        {
            "066570": 200_000.0,
            # 나머지 LG 자회사는 모두 None (doc 미존재)
            "003550": 100_000.0,
        }
    )
    analyzer = HoldingCompanyAnalyzer(db=db)

    result = analyzer.calculate_nav_discount("003550")

    assert result is not None
    assert "051910" in result["missing_subsidiary_caps"]
    assert "051900" in result["missing_subsidiary_caps"]
    assert "032640" in result["missing_subsidiary_caps"]
    # NAV는 LG전자 지분만 산입됨
    assert result["nav_eok"] == 67_400.0


def test_calculate_nav_discount_holding_cap_zero_returns_unable():
    """지주사 본인 시총 0 → discount_pct=None + '산정 불가'."""
    db = _mk_db_with_caps(
        {
            "066570": 200_000.0,
            "051910": 300_000.0,
            "051900": 50_000.0,
            "032640": 50_000.0,
            # 003550은 None
        }
    )
    analyzer = HoldingCompanyAnalyzer(db=db)

    result = analyzer.calculate_nav_discount("003550")

    assert result is not None
    assert result["discount_pct"] is None
    assert result["interpretation"] == "산정 불가"


def test_calculate_nav_discount_negative_discount_classified_as_premium():
    """지주사 시총 > NAV → 음수 디스카운트 (premium) → '프리미엄' 라벨."""
    db = _mk_db_with_caps(
        {
            "066570": 10_000.0,
            "051910": 10_000.0,
            "051900": 10_000.0,
            "032640": 10_000.0,
            "003550": 1_000_000.0,  # 비정상적으로 큰 시총 (테스트용)
        }
    )
    analyzer = HoldingCompanyAnalyzer(db=db)

    result = analyzer.calculate_nav_discount("003550")

    assert result is not None
    assert result["discount_pct"] < 0
    assert result["interpretation"].startswith("프리미엄")
    # LG는 비상장 자회사 없음 → "산정 한계" 문구 X
    assert "산정 한계" not in result["interpretation"]


def test_calculate_nav_discount_negative_with_unlisted_subsidiaries():
    """GS처럼 비상장 자회사 있는 경우 음수 디스카운트 → '비상장 자회사 NAV 미산입' 명시."""
    db = _mk_db_with_caps(
        {
            "006360": 30_000.0,
            "007070": 20_000.0,
            "001250": 5_000.0,
            "078930": 80_000.0,  # GS 시총이 자회사 NAV 합보다 큼 (실제와 유사)
        }
    )
    analyzer = HoldingCompanyAnalyzer(db=db)

    result = analyzer.calculate_nav_discount("078930")

    assert result is not None
    assert result["discount_pct"] < 0
    assert result["has_unlisted_subsidiaries"] is True
    assert "비상장 자회사" in result["interpretation"]


def test_classify_discount_negative_without_unlisted():
    from utils.data_collectors.holding_company import classify_discount

    assert classify_discount(-50.0, has_unlisted=False).startswith("프리미엄")
    assert "산정 한계" not in classify_discount(-50.0, has_unlisted=False)


def test_classify_discount_negative_with_unlisted():
    from utils.data_collectors.holding_company import classify_discount

    label = classify_discount(-100.0, has_unlisted=True)
    assert label.startswith("프리미엄")
    assert "비상장 자회사" in label


def test_get_market_cap_handles_firestore_exception():
    """Firestore 예외 시 0.0 반환 (graceful)."""
    db = MagicMock()
    db.collection.return_value.document.side_effect = ConnectionError("network")
    analyzer = HoldingCompanyAnalyzer(db=db)

    assert analyzer.get_market_cap_eok("005930") == 0.0


def test_get_market_cap_handles_invalid_value():
    """시총 필드가 string 등 변환 불가 → 0.0."""
    db = MagicMock()
    doc = SimpleNamespace(exists=True, to_dict=lambda: {"market_cap": "not a number"})
    db.collection.return_value.document.return_value.get.return_value = doc
    analyzer = HoldingCompanyAnalyzer(db=db)

    assert analyzer.get_market_cap_eok("005930") == 0.0


# ──────────────────────────────────────────────
# 7. calculate_all
# ──────────────────────────────────────────────


def test_calculate_all_returns_one_per_holding():
    """모든 등록 지주사에 대해 dict 반환 (시총 0이어도 '산정 불가' 형태로 포함)."""
    db = _mk_db_with_caps({})  # 모든 시총 None → 산정 불가
    analyzer = HoldingCompanyAnalyzer(db=db)

    results = analyzer.calculate_all()

    assert len(results) == len(HOLDING_COMPANIES)
    tickers = {r["ticker"] for r in results}
    assert tickers == set(HOLDING_COMPANIES.keys())


# ──────────────────────────────────────────────
# 8. HOLDING_COMPANIES 데이터 sanity
# ──────────────────────────────────────────────


def test_holding_companies_data_integrity():
    """HOLDING_COMPANIES 데이터 형식 검증."""
    assert len(HOLDING_COMPANIES) >= 5, "최소 5개 주요 지주사"

    for ticker, data in HOLDING_COMPANIES.items():
        # ticker는 6자리 숫자 문자열
        assert ticker.isdigit() and len(ticker) == 6, f"잘못된 ticker: {ticker}"
        # 필수 필드
        assert "name" in data
        assert "subsidiaries" in data
        assert "metadata" in data
        # 자회사 1개 이상
        assert len(data["subsidiaries"]) >= 1
        # 자회사 ticker + 지분율 범위 검증
        for sub in data["subsidiaries"]:
            assert sub["ticker"].isdigit() and len(sub["ticker"]) == 6
            assert 0 < sub["stake_pct"] <= 100, (
                f"{ticker} {sub['ticker']} 지분율 이상: {sub['stake_pct']}"
            )
        # 메타에 as_of/source/verified 필수
        assert "as_of" in data["metadata"]
        assert "source" in data["metadata"]
        assert data["metadata"]["verified"] is True


# ──────────────────────────────────────────────
# 9. chaebol_groups.json 데이터 sanity
# ──────────────────────────────────────────────


def test_chaebol_groups_json_loadable_and_structured():
    """data/chaebol_groups.json — 구조 + 검증 그룹 수 확인."""
    path = Path(__file__).resolve().parents[2] / "data" / "chaebol_groups.json"
    assert path.exists(), f"파일 없음: {path}"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "_meta" in raw

    # _meta 제외한 그룹 수
    groups = {k: v for k, v in raw.items() if not k.startswith("_")}
    assert len(groups) >= 10, "상위 10대 그룹 이상"

    for name, info in groups.items():
        assert "rank" in info
        assert isinstance(info["rank"], int)
        assert "core_companies" in info
        assert len(info["core_companies"]) >= 1
        assert info.get("verified") is True, f"{name}: verified=true 필수"
        # core_companies 내부 형식
        for c in info["core_companies"]:
            assert c["ticker"].isdigit() and len(c["ticker"]) == 6
            assert isinstance(c["name"], str) and c["name"]
        # holding_company는 6자리 ticker 또는 null (농협 같은 협동조합)
        hc = info.get("holding_company")
        if hc is not None:
            assert hc.isdigit() and len(hc) == 6
