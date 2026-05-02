"""한국 주요 지주사 NAV 디스카운트 자동 계산 모듈.

WEEK_A.md Day 3 산출물.

NAV (Net Asset Value) 디스카운트:
  NAV = Σ(보유 자회사 시총 × 지분율) + 순현금자산
  Discount % = (NAV - 지주사 시총) / NAV × 100

데이터 소스:
  - 자회사 지분율: DART 분기보고서 (수동 갱신, 분기 1회)
  - 자회사/지주사 시가총액: Firestore stocks 컬렉션 (collector.py가 운영 중)
  - 단위: 억원 (screener와 동일)

커버리지: 5개 주요 지주사 (LG, SK, GS, 한화, 롯데지주).
지분율은 분기마다 변동 → as_of/source 메타로 시점 표시.
미커버 지주사는 별도 PR로 추가.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger


# ──────────────────────────────────────────────
# 정적 지주사 데이터 (분기별 수동 갱신)
# ──────────────────────────────────────────────
# 지분율 출처: DART 정기보고서 + 지주사 IR 자료. as_of 시점 명시.
# net_cash_eok: 보수적으로 0 (DART 분기보고서 별도 갱신 필요).
# 데이터 갱신 책임: data_infra/korea_market.md §2.3 참고.

HOLDING_COMPANIES: dict[str, dict[str, Any]] = {
    "003550": {
        "name": "LG",
        "subsidiaries": [
            {"ticker": "066570", "name": "LG전자", "stake_pct": 33.7},
            {"ticker": "051910", "name": "LG화학", "stake_pct": 33.3},
            {"ticker": "051900", "name": "LG생활건강", "stake_pct": 30.0},
            {"ticker": "032640", "name": "LG유플러스", "stake_pct": 37.7},
        ],
        "net_cash_eok": 0,
        "metadata": {
            "as_of": "2024-12-31",
            "source": "DART 2024 4Q 사업보고서",
            "verified": True,
            "note": "LG에너지솔루션은 LG화학 자회사 (간접 보유) → 별도 산입 X",
        },
    },
    "034730": {
        "name": "SK",
        "subsidiaries": [
            {"ticker": "000660", "name": "SK하이닉스", "stake_pct": 20.1},
            {"ticker": "017670", "name": "SK텔레콤", "stake_pct": 30.6},
            {"ticker": "096770", "name": "SK이노베이션", "stake_pct": 33.4},
            {"ticker": "402340", "name": "SK스퀘어", "stake_pct": 30.6},
            {"ticker": "018670", "name": "SK가스", "stake_pct": 72.2},
        ],
        "net_cash_eok": 0,
        "metadata": {
            "as_of": "2024-12-31",
            "source": "DART 2024 4Q 사업보고서",
            "verified": True,
        },
    },
    "078930": {
        "name": "GS",
        "subsidiaries": [
            {"ticker": "006360", "name": "GS건설", "stake_pct": 20.1},
            {"ticker": "007070", "name": "GS리테일", "stake_pct": 65.8},
            {"ticker": "001250", "name": "GS글로벌", "stake_pct": 50.7},
        ],
        "net_cash_eok": 0,
        "has_unlisted_subsidiaries": True,
        "metadata": {
            "as_of": "2024-12-31",
            "source": "DART 2024 4Q 사업보고서",
            "verified": True,
            "note": "비상장 자회사 GS에너지/GS칼텍스(50%)/GS EPS 등 NAV 누락 → 디스카운트 산정 시 보수적",
        },
    },
    "000880": {
        "name": "한화",
        "subsidiaries": [
            {"ticker": "009830", "name": "한화솔루션", "stake_pct": 36.0},
            {"ticker": "012450", "name": "한화에어로스페이스", "stake_pct": 33.9},
            {"ticker": "088350", "name": "한화생명", "stake_pct": 22.0},
        ],
        "net_cash_eok": 0,
        "metadata": {
            "as_of": "2024-12-31",
            "source": "DART 2024 4Q 사업보고서",
            "verified": True,
            "note": "한화시스템(272210)은 한화에어로스페이스 자회사 → 간접 보유, 별도 산입 X",
        },
    },
    "004990": {
        "name": "롯데지주",
        "subsidiaries": [
            {"ticker": "023530", "name": "롯데쇼핑", "stake_pct": 40.0},
            {"ticker": "011170", "name": "롯데케미칼", "stake_pct": 25.3},
            {"ticker": "004000", "name": "롯데정밀화학", "stake_pct": 30.5},
            {"ticker": "280360", "name": "롯데웰푸드", "stake_pct": 48.4},
        ],
        "net_cash_eok": 0,
        "metadata": {
            "as_of": "2024-12-31",
            "source": "DART 2024 4Q 사업보고서",
            "verified": True,
        },
    },
}


# ──────────────────────────────────────────────
# NAV 디스카운트 분류 (korea_market.md §2.2)
# ──────────────────────────────────────────────


def classify_discount(pct: float, has_unlisted: bool = False) -> str:
    """NAV 디스카운트율을 5단계로 분류.

    Args:
        pct: 디스카운트율 (예: 45.0 = 45% 디스카운트, 음수면 프리미엄)
        has_unlisted: 비상장 자회사 보유 여부 — True면 NAV 과소산정 가능성 라벨에 명시.

    Returns:
        한국어 분류 라벨 — Korean Specialist 페르소나가 그대로 사용 가능.
    """
    if pct < 0:
        if has_unlisted:
            return "프리미엄 (비상장 자회사 NAV 미산입 — 산정 한계)"
        return "프리미엄 (NAV 대비 시총 초과 — 추가 분석 필요)"
    if pct < 20:
        return "낮음 (적정 평가)"
    elif pct < 40:
        return "중간 (구조적 디스카운트)"
    elif pct < 60:
        return "높음 (가치 vs 거버넌스 갈등)"
    else:
        return "매우 높음 (기회 또는 함정)"


# ──────────────────────────────────────────────
# NAV 계산기 (Firestore 의존)
# ──────────────────────────────────────────────


class HoldingCompanyAnalyzer:
    """지주사 NAV 디스카운트 자동 계산.

    Args:
        db: Firestore 클라이언트 (None 시 lazy import — screener.db.firebase_client.get_db).
        market_cap_field: stocks 컬렉션의 시총 필드명 (단위: 억원).
        market_cap_collection: 시총 조회 컬렉션 (기본: stocks).
    """

    def __init__(
        self,
        db: Any | None = None,
        market_cap_field: str = "market_cap",
        market_cap_collection: str = "stocks",
    ) -> None:
        self._db = db
        self.market_cap_field = market_cap_field
        self.market_cap_collection = market_cap_collection

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    # ──────────────────────────────────────────────
    # 시총 조회 (단위: 억원)
    # ──────────────────────────────────────────────

    def get_market_cap_eok(self, ticker: str) -> float:
        """Firestore stocks/{ticker} 에서 market_cap 읽기.

        Returns:
            시가총액 (억원). doc 미존재/필드 누락 시 0.0.
        """
        try:
            doc = self.db.collection(self.market_cap_collection).document(ticker).get()
        except Exception as e:
            logger.warning(
                f"Firestore 시총 조회 실패 (ticker={ticker}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            return 0.0

        if not getattr(doc, "exists", False):
            return 0.0

        data = doc.to_dict() or {}
        cap = data.get(self.market_cap_field, 0)
        try:
            return float(cap)
        except (TypeError, ValueError):
            return 0.0

    # ──────────────────────────────────────────────
    # NAV 디스카운트 계산
    # ──────────────────────────────────────────────

    def calculate_nav_discount(self, holding_ticker: str) -> dict[str, Any] | None:
        """지주사 NAV 디스카운트 계산.

        Args:
            holding_ticker: 지주사 종목 코드 (예: "003550" = LG)

        Returns:
            {
                "ticker": "003550",
                "name": "LG",
                "nav_eok": 350000.0,                   # 자회사 NAV 합 + 순현금 (억원)
                "market_cap_eok": 120000.0,            # 지주사 시총 (억원)
                "discount_pct": 65.7,                  # 디스카운트율
                "interpretation": "매우 높음 (기회 또는 함정)",
                "subsidiaries": [
                    {"ticker": "066570", "name": "LG전자",
                     "stake_pct": 33.7, "market_cap_eok": 200000.0,
                     "stake_value_eok": 67400.0},
                    ...
                ],
                "missing_subsidiary_caps": ["004990"],  # 시총 조회 실패 자회사
                "metadata": {...},                     # 정적 데이터의 metadata
            }
            HOLDING_COMPANIES 미등록 ticker → None.
            지주사 본인 시총 조회 실패 시 discount_pct=None (산정 불가).
        """
        holding_data = HOLDING_COMPANIES.get(holding_ticker)
        if holding_data is None:
            logger.debug(f"HOLDING_COMPANIES에 없는 ticker: {holding_ticker}")
            return None

        net_cash = float(holding_data.get("net_cash_eok", 0))
        nav = net_cash
        sub_results: list[dict[str, Any]] = []
        missing: list[str] = []

        for sub in holding_data.get("subsidiaries", []):
            sub_ticker = sub["ticker"]
            sub_cap = self.get_market_cap_eok(sub_ticker)
            stake_value = sub_cap * (sub["stake_pct"] / 100.0)
            nav += stake_value

            if sub_cap == 0.0:
                missing.append(sub_ticker)

            sub_results.append(
                {
                    "ticker": sub_ticker,
                    "name": sub["name"],
                    "stake_pct": sub["stake_pct"],
                    "market_cap_eok": round(sub_cap, 1),
                    "stake_value_eok": round(stake_value, 1),
                }
            )

        holding_cap = self.get_market_cap_eok(holding_ticker)

        if holding_cap == 0.0 or nav == 0.0:
            logger.warning(
                f"NAV 산정 불가 (ticker={holding_ticker}): "
                f"nav={nav:.1f}억, holding_cap={holding_cap:.1f}억"
            )
            return {
                "ticker": holding_ticker,
                "name": holding_data["name"],
                "nav_eok": round(nav, 1),
                "market_cap_eok": round(holding_cap, 1),
                "discount_pct": None,
                "interpretation": "산정 불가",
                "subsidiaries": sub_results,
                "missing_subsidiary_caps": missing,
                "metadata": holding_data.get("metadata", {}),
                "computed_at": datetime.now().isoformat(),
            }

        has_unlisted = bool(holding_data.get("has_unlisted_subsidiaries"))
        discount_pct = (nav - holding_cap) / nav * 100
        return {
            "ticker": holding_ticker,
            "name": holding_data["name"],
            "nav_eok": round(nav, 1),
            "market_cap_eok": round(holding_cap, 1),
            "discount_pct": round(discount_pct, 2),
            "interpretation": classify_discount(discount_pct, has_unlisted=has_unlisted),
            "has_unlisted_subsidiaries": has_unlisted,
            "subsidiaries": sub_results,
            "missing_subsidiary_caps": missing,
            "metadata": holding_data.get("metadata", {}),
            "computed_at": datetime.now().isoformat(),
        }

    # ──────────────────────────────────────────────
    # 일괄 계산 (모든 등록 지주사)
    # ──────────────────────────────────────────────

    def calculate_all(self) -> list[dict[str, Any]]:
        """HOLDING_COMPANIES 전체에 대해 NAV 디스카운트 계산.

        Returns:
            결과 리스트 (None은 자동 제외 — 등록 ticker는 항상 dict 반환).
        """
        results = []
        for holding_ticker in HOLDING_COMPANIES.keys():
            res = self.calculate_nav_discount(holding_ticker)
            if res is not None:
                results.append(res)
        return results
