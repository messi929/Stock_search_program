"""DART client + buyback 모듈 단위 테스트 (mock httpx + Firestore)."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.data_collectors.dart_buyback import (
    AMENDMENT_PREFIXES,
    BUYBACK_KEYWORDS,
    DartBuybackCollector,
    classify_buyback_action,
    is_buyback_disclosure,
)
from utils.data_collectors.dart_client import (
    DartClient,
    mask_api_key_in_str,
)


# ──────────────────────────────────────────────
# 1. classify_buyback_action — 분류 로직
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "report_nm,expected_action,expected_weight,expected_amendment",
    [
        # burn (소각 — 가장 강한 주주환원)
        ("주식소각결정", "burn", 3, False),
        ("[기재정정]주식소각결정", "burn", 3, True),
        ("자기주식소각 결정", "burn", 3, False),
        # buy_complete (취득 결과보고)
        ("자기주식취득결과보고서", "buy_complete", 1, False),
        ("[정정]자기주식취득결과보고", "buy_complete", 1, True),
        # buy_decision (취득 결정)
        ("주요사항보고서(자기주식취득결정)", "buy_decision", 1, False),
        ("[기재정정]주요사항보고서(자기주식취득결정)", "buy_decision", 1, True),
        # dispose (처분 — 약한 신호)
        ("주요사항보고서(자기주식처분결정)", "dispose", 0, False),
        # trust (신탁)
        ("자기주식취득신탁계약체결결정", "trust_contract", 1, False),
        # unknown
        ("사업보고서", "unknown", 0, False),
        ("증권발행실적보고서", "unknown", 0, False),
        ("", "unknown", 0, False),
    ],
)
def test_classify_buyback_action(
    report_nm, expected_action, expected_weight, expected_amendment
):
    result = classify_buyback_action(report_nm)
    assert result["action"] == expected_action
    assert result["weight"] == expected_weight
    assert result["is_amendment"] is expected_amendment


def test_classify_buyback_action_priority():
    """소각 + 취득이 동시에 들어가면 소각이 우선 (BUYBACK_KEYWORDS 순서)."""
    # "주식소각" + "자기주식" 둘 다 매칭 가능 — 소각이 우선이어야 함
    r = classify_buyback_action("자기주식 주식소각결정")
    assert r["action"] == "burn"


def test_amendment_prefixes_are_all_recognized():
    """모든 [정정] prefix 변형이 is_amendment=True."""
    for prefix in AMENDMENT_PREFIXES:
        r = classify_buyback_action(f"{prefix}주식소각결정")
        assert r["is_amendment"] is True, f"prefix={prefix!r} not detected"


def test_is_buyback_disclosure_filter():
    assert is_buyback_disclosure("주식소각결정") is True
    assert is_buyback_disclosure("자기주식취득결정") is True
    assert is_buyback_disclosure("사업보고서") is False
    assert is_buyback_disclosure("") is False


# ──────────────────────────────────────────────
# 2. mask_api_key_in_str — 보안
# ──────────────────────────────────────────────


def test_mask_api_key_in_str():
    """40자리 API 키가 로그/예외 메시지에서 마스킹되어야 함."""
    raw = (
        "https://opendart.fss.or.kr/api/list.json?"
        "crtfc_key=4e5b7d836e0816a88e2e34901ed01b2b86a621af&corp_code=00126380"
    )
    masked = mask_api_key_in_str(raw)
    assert "4e5b7d836e0816a88e2e34901ed01b2b86a621af" not in masked
    assert "crtfc_key=***" in masked
    assert "corp_code=00126380" in masked


def test_mask_api_key_case_insensitive():
    s = "CRTFC_KEY=ABCDEF0123456789ABCDEF0123456789ABCDEF01"
    assert "ABCDEF" not in mask_api_key_in_str(s)


# ──────────────────────────────────────────────
# 3. DartClient.fetch_disclosures — 페이지네이션
# ──────────────────────────────────────────────


def _mk_response(json_data: dict) -> MagicMock:
    r = MagicMock()
    r.json.return_value = json_data
    r.raise_for_status.return_value = None
    return r


def test_fetch_disclosures_single_page():
    http = MagicMock()
    http.get.return_value = _mk_response(
        {
            "status": "000",
            "page_no": 1,
            "page_count": 100,
            "total_count": 3,
            "total_page": 1,
            "list": [
                {"corp_code": "00126380", "report_nm": "주식소각결정", "rcept_no": "1"},
                {"corp_code": "00126380", "report_nm": "사업보고서", "rcept_no": "2"},
                {"corp_code": "00126380", "report_nm": "자기주식취득결정", "rcept_no": "3"},
            ],
        }
    )
    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)

    items = client.fetch_disclosures(corp_code="00126380", bgn_de="20240101", end_de="20240131")

    assert len(items) == 3
    assert http.get.call_count == 1
    assert client.stats.successful_calls == 1


def test_fetch_disclosures_multi_page():
    """total_page=3이면 3번 호출하여 모두 합쳐서 반환."""
    http = MagicMock()
    pages = [
        {
            "status": "000",
            "page_no": p,
            "total_page": 3,
            "list": [{"corp_code": "x", "report_nm": f"공시{p}-{i}", "rcept_no": f"{p}{i}"}
                     for i in range(2)],
        }
        for p in (1, 2, 3)
    ]
    http.get.side_effect = [_mk_response(p) for p in pages]
    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)

    items = client.fetch_disclosures(corp_code="00126380", bgn_de="20240101", end_de="20241231")

    assert len(items) == 6
    assert http.get.call_count == 3


def test_fetch_disclosures_status_013_no_data():
    """status=013 = 조회 결과 없음 → 빈 리스트."""
    http = MagicMock()
    http.get.return_value = _mk_response({"status": "013", "message": "조회된 데이터가 없습니다"})
    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)

    items = client.fetch_disclosures(corp_code="00126380", bgn_de="20240101", end_de="20240102")

    assert items == []


def test_fetch_disclosures_handles_exception():
    http = MagicMock()
    http.get.side_effect = ConnectionError("network")
    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)

    items = client.fetch_disclosures(corp_code="00126380", bgn_de="20240101", end_de="20240131")

    assert items == []
    assert client.stats.failed_calls == 1


def test_fetch_disclosures_no_api_key_returns_empty():
    """API 키 없으면 즉시 빈 리스트 (호출 시도 X)."""
    client = DartClient(api_key="", http_client=MagicMock(), sleep_sec=0)
    items = client.fetch_disclosures(corp_code="00126380", bgn_de="20240101", end_de="20240131")
    assert items == []


def test_fetch_disclosures_max_pages_safety_limit():
    """max_pages 도달 시 호출 중단."""
    http = MagicMock()
    # 무한 페이지 응답
    http.get.return_value = _mk_response(
        {
            "status": "000",
            "page_no": 1,
            "total_page": 9999,
            "list": [{"report_nm": "x", "rcept_no": "1"}],
        }
    )
    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)

    client.fetch_disclosures(
        corp_code="00126380", bgn_de="20240101", end_de="20241231", max_pages=3
    )

    assert http.get.call_count == 3


# ──────────────────────────────────────────────
# 4. DartClient.get_corp_code_map — ZIP 처리
# ──────────────────────────────────────────────


def _mk_corpcode_zip(entries: list[tuple[str, str, str]]) -> bytes:
    """테스트용 corpCode.xml ZIP 생성. entries = [(corp_code, corp_name, stock_code)]."""
    xml_body = ['<?xml version="1.0" encoding="UTF-8"?>', "<result>"]
    for corp_code, corp_name, stock_code in entries:
        xml_body.append(
            f"<list><corp_code>{corp_code}</corp_code>"
            f"<corp_name>{corp_name}</corp_name>"
            f"<stock_code>{stock_code}</stock_code>"
            f"<modify_date>20240101</modify_date></list>"
        )
    xml_body.append("</result>")
    xml = "\n".join(xml_body).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("CORPCODE.xml", xml)
    return buf.getvalue()


def test_get_corp_code_map_parses_zip():
    """ZIP 다운로드 + XML 파싱 → stock_code 매핑."""
    zip_bytes = _mk_corpcode_zip(
        [
            ("00126380", "삼성전자", "005930"),
            ("00164779", "SK하이닉스", "000660"),
            ("99999999", "비상장회사", ""),  # stock_code 없음 → 제외
        ]
    )
    http = MagicMock()
    resp = MagicMock()
    resp.content = zip_bytes
    resp.raise_for_status.return_value = None
    http.get.return_value = resp

    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)
    mapping = client.get_corp_code_map()

    assert "005930" in mapping
    assert mapping["005930"]["corp_code"] == "00126380"
    assert mapping["005930"]["corp_name"] == "삼성전자"
    assert "000660" in mapping
    assert "비상장회사" not in str(mapping)
    # 비상장은 제외 — 매핑 2건만
    assert len(mapping) == 2


def test_get_corp_code_map_caches_result():
    """두 번째 호출은 캐시 사용 — http.get 1회만 호출."""
    zip_bytes = _mk_corpcode_zip([("00126380", "삼성전자", "005930")])
    http = MagicMock()
    resp = MagicMock()
    resp.content = zip_bytes
    resp.raise_for_status.return_value = None
    http.get.return_value = resp

    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)

    m1 = client.get_corp_code_map()
    m2 = client.get_corp_code_map()

    assert m1 is m2
    assert http.get.call_count == 1


def test_get_corp_code_map_handles_non_zip_response():
    """ZIP 아닌 응답 (예: 키 오류 JSON) → 빈 dict."""
    http = MagicMock()
    resp = MagicMock()
    resp.content = '{"status": "020", "message": "사용 한도 초과"}'.encode("utf-8")
    resp.raise_for_status.return_value = None
    resp.headers = {"content-type": "application/json"}
    http.get.return_value = resp

    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)
    mapping = client.get_corp_code_map()

    assert mapping == {}
    assert client.stats.failed_calls == 1


def test_corp_code_for_stock_zero_padding():
    """stock_code 5자리/문자열 입력도 6자리 zero-pad로 매칭."""
    zip_bytes = _mk_corpcode_zip([("00126380", "삼성전자", "005930")])
    http = MagicMock()
    resp = MagicMock()
    resp.content = zip_bytes
    resp.raise_for_status.return_value = None
    http.get.return_value = resp

    client = DartClient(api_key="x" * 40, http_client=http, sleep_sec=0)

    assert client.corp_code_for_stock("005930") == "00126380"
    assert client.corp_code_for_stock("5930") == "00126380"  # zero-pad
    assert client.corp_code_for_stock(5930) == "00126380"  # int
    assert client.corp_code_for_stock("999999") is None


# ──────────────────────────────────────────────
# 5. DartBuybackCollector — 통합 흐름
# ──────────────────────────────────────────────


def _mk_buyback_collector(
    corp_code_map: dict | None = None,
    disclosures: list[dict] | None = None,
    db: MagicMock | None = None,
) -> DartBuybackCollector:
    client = MagicMock()
    client.corp_code_for_stock.side_effect = lambda code: (
        (corp_code_map or {}).get(str(code).zfill(6))
    )
    client.fetch_disclosures.return_value = disclosures or []
    return DartBuybackCollector(client=client, db=db or MagicMock())


def test_fetch_buyback_disclosures_filters_and_classifies():
    """자사주 관련만 분류, unknown은 결과에서 제외."""
    collector = _mk_buyback_collector(
        corp_code_map={"005930": "00126380"},
        disclosures=[
            {"corp_code": "00126380", "corp_name": "삼성전자",
             "report_nm": "주식소각결정", "rcept_no": "1", "rcept_dt": "20250218"},
            {"corp_code": "00126380", "corp_name": "삼성전자",
             "report_nm": "사업보고서", "rcept_no": "2", "rcept_dt": "20250301"},
            {"corp_code": "00126380", "corp_name": "삼성전자",
             "report_nm": "자기주식취득결정", "rcept_no": "3", "rcept_dt": "20250215"},
        ],
    )

    records = collector.fetch_buyback_disclosures("005930", "20250101", "20250430")

    assert len(records) == 2  # 사업보고서는 제외
    actions = {r["action"] for r in records}
    assert actions == {"burn", "buy_decision"}
    assert collector.stats.total_disclosures == 3
    assert collector.stats.classified == 2


def test_fetch_buyback_disclosures_unknown_corp_code_returns_empty():
    collector = _mk_buyback_collector(corp_code_map={})

    records = collector.fetch_buyback_disclosures("999999", "20250101", "20250430")

    assert records == []


def test_save_to_firestore_doc_id_and_batch():
    """Doc ID = {stock_code}_{rcept_no}, batch.commit 호출."""
    db = MagicMock()
    batch = MagicMock()
    db.batch.return_value = batch
    captured: list[str] = []
    db.collection.return_value.document.side_effect = lambda doc_id: (
        captured.append(doc_id) or SimpleNamespace(id=doc_id)
    )

    collector = _mk_buyback_collector(db=db)
    collector.save_to_firestore(
        [
            {"stock_code": "005930", "rcept_no": "20250218000123",
             "action": "burn", "report_nm": "주식소각결정"},
            {"stock_code": "005930", "rcept_no": "20250215000456",
             "action": "buy_decision", "report_nm": "자기주식취득결정"},
        ]
    )

    assert captured == ["005930_20250218000123", "005930_20250215000456"]
    batch.commit.assert_called_once()


def test_save_to_firestore_skips_missing_keys():
    db = MagicMock()
    batch = MagicMock()
    db.batch.return_value = batch
    db.collection.return_value.document.return_value = SimpleNamespace(id="x")

    collector = _mk_buyback_collector(db=db)
    collector.save_to_firestore(
        [
            {"stock_code": "005930", "rcept_no": "1"},  # 정상
            {"rcept_no": "2"},  # stock_code 누락
            {"stock_code": "005930"},  # rcept_no 누락
        ]
    )

    assert batch.set.call_count == 1


def test_save_to_firestore_adds_metadata():
    db = MagicMock()
    batch = MagicMock()
    db.batch.return_value = batch
    db.collection.return_value.document.return_value = SimpleNamespace(id="x")

    collector = _mk_buyback_collector(db=db)
    collector.save_to_firestore([{"stock_code": "005930", "rcept_no": "1", "action": "burn"}])

    saved_doc = batch.set.call_args.args[1]
    assert saved_doc["data_source"] == "dart_opendart_v1"
    assert "collected_at" in saved_doc
    assert batch.set.call_args.kwargs.get("merge") is True


# ──────────────────────────────────────────────
# 6. summarize_buyback_history
# ──────────────────────────────────────────────


def test_summarize_buyback_history_aggregation():
    """집계 시 is_amendment 제외, max_weight + has_burn 정확히."""
    db = MagicMock()
    fake_records = [
        {"action": "burn", "weight": 3, "is_amendment": False, "rcept_dt": "20250218"},
        {"action": "burn", "weight": 3, "is_amendment": True, "rcept_dt": "20250218"},  # 제외
        {"action": "buy_decision", "weight": 1, "is_amendment": False, "rcept_dt": "20250215"},
        {"action": "buy_complete", "weight": 1, "is_amendment": False, "rcept_dt": "20250220"},
    ]
    fake_docs = [SimpleNamespace(to_dict=lambda r=r: r) for r in fake_records]
    query_chain = MagicMock()
    query_chain.stream.return_value = iter(fake_docs)
    query_chain.where.return_value = query_chain
    db.collection.return_value.where.return_value = query_chain

    collector = _mk_buyback_collector(db=db)
    summary = collector.summarize_buyback_history("005930", years=3)

    assert summary["stock_code"] == "005930"
    assert summary["total_disclosures"] == 4
    assert summary["by_action"]["burn"] == 1  # 정정 제외
    assert summary["by_action"]["buy_decision"] == 1
    assert summary["by_action"]["buy_complete"] == 1
    assert summary["has_burn"] is True
    assert summary["max_weight"] == 3
    # latest_action = rcept_dt 가장 늦은 것 (20250220 = buy_complete)
    assert summary["latest_action"]["action"] == "buy_complete"


def test_summarize_buyback_history_no_burn():
    """소각 없는 경우 has_burn=False."""
    db = MagicMock()
    fake_records = [
        {"action": "buy_decision", "weight": 1, "is_amendment": False, "rcept_dt": "20240101"},
    ]
    fake_docs = [SimpleNamespace(to_dict=lambda r=r: r) for r in fake_records]
    query_chain = MagicMock()
    query_chain.stream.return_value = iter(fake_docs)
    query_chain.where.return_value = query_chain
    db.collection.return_value.where.return_value = query_chain

    collector = _mk_buyback_collector(db=db)
    summary = collector.summarize_buyback_history("005930")

    assert summary["has_burn"] is False
    assert summary["max_weight"] == 1


def test_summarize_buyback_history_empty_history():
    db = MagicMock()
    query_chain = MagicMock()
    query_chain.stream.return_value = iter([])
    query_chain.where.return_value = query_chain
    db.collection.return_value.where.return_value = query_chain

    collector = _mk_buyback_collector(db=db)
    summary = collector.summarize_buyback_history("999999")

    assert summary["total_disclosures"] == 0
    assert summary["has_burn"] is False
    assert summary["max_weight"] == 0
    assert summary["latest_action"] is None
