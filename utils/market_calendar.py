"""한국 증시 개장/휴장 판별 — '오늘 국내장' 표현의 사실 정확성 보장용.

새벽 브리핑이 휴장일(주말·공휴일)에 "오늘 국내장을 보라"는 잘못된 정보를 내지
않도록, 프롬프트에 주입할 개장 상태 힌트를 만든다.

- 주말은 무조건 휴장(신뢰 100%, 무의존).
- 공휴일은 `holidays` 라이브러리(설치 시) + KRX 고유 휴장일(근로자의날 5/1, 연말 12/31)로 보강.
- `holidays` 미설치/오류 시 **주말만** 판별하도록 graceful 폴백(틀린 단정 대신 보수적).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from loguru import logger


def kr_market_closed(d: Optional[date] = None) -> tuple[bool, str]:
    """해당 날짜 한국 증시 휴장 여부. 반환 (closed, reason).

    reason: 'weekend' | 'holiday:<이름>' | '' (개장).
    공휴일 판별은 라이브러리 가용 시에만 — 불확실하면 휴장으로 단정하지 않는다.
    """
    d = d or datetime.now().date()
    if d.weekday() >= 5:  # 5=토, 6=일
        return True, "weekend"
    # KRX 고유 휴장(공휴일 라이브러리에 없거나 다르게 잡히는 날)
    if (d.month, d.day) == (5, 1):
        return True, "holiday:근로자의 날"
    if (d.month, d.day) == (12, 31):
        return True, "holiday:연말 휴장"
    try:
        import holidays

        kr = holidays.SouthKorea(years=d.year)
        name = kr.get(d)
        if name:
            return True, f"holiday:{name}"
    except Exception as e:
        logger.debug(f"[market_calendar] 공휴일 조회 불가(주말만 판별): {e}")
    return False, ""


def kr_market_status_hint(d: Optional[date] = None) -> str:
    """브리핑 프롬프트에 주입할 '한국 증시 개장 상태' 지시문.

    휴장일이면 '오늘 국내장' 표현 금지를 명시, 개장일이면 한국장은 낮에 열린다는 점을 명시
    (LLM이 '오늘 밤 국내장'이라 쓰는 시간 오류 방지).
    """
    closed, reason = kr_market_closed(d)
    if closed:
        why = "주말" if reason == "weekend" else reason.replace("holiday:", "")
        return (
            f"오늘은 한국 증시 휴장일입니다({why}). "
            "'오늘 국내장', '오늘 밤 국내시장' 같은 표현을 절대 쓰지 마세요. "
            "대신 '다음 거래일 국내 증시' 또는 '국내장 재개 시' 관점으로, 간밤 미국장 흐름이 "
            "다음 개장 때 관찰 포인트가 될지를 1줄로만 적으세요."
        )
    return (
        "오늘은 한국 증시 정상 거래일입니다. 한국 증시는 낮(09:00~15:30)에 열리므로 "
        "'오늘 밤 국내장' 같은 표현은 틀립니다 — '오늘 국내 증시(낮)'로 표현하고, "
        "간밤 미국장이 오늘 국내장에 줄 관찰 포인트를 1줄 중립적으로 적으세요."
    )


def next_kr_trading_day(d: Optional[date] = None) -> date:
    """주어진 날짜(포함 안 함) 이후의 첫 한국 증시 개장일.

    주말 브리핑(일요일 밤)이 '다음 거래일(보통 월요일)'을 정확히 가리키게 한다.
    공휴일이 낀 월요일이면 그 다음 개장일을 찾는다. 안전상 최대 10일만 탐색.
    """
    d = d or datetime.now().date()
    cur = d
    for _ in range(10):
        cur = cur + timedelta(days=1)
        closed, _reason = kr_market_closed(cur)
        if not closed:
            return cur
    return d + timedelta(days=1)  # 폴백(이론상 도달 안 함)


def kr_next_session_hint(d: Optional[date] = None) -> str:
    """주말/휴장 브리핑용 — '다음 거래일' 한국 증시 개장 지시문.

    발행 시점(일요일 밤 등)에서 다음 개장일을 계산해 LLM이 '오늘 국내장'이 아니라
    '다음 거래일(○월 ○일, ○요일) 국내장' 관점으로 쓰게 한다.
    """
    nd = next_kr_trading_day(d)
    weekday_kr = ("월", "화", "수", "목", "금", "토", "일")[nd.weekday()]
    return (
        f"다음 한국 증시 개장일은 {nd.month}월 {nd.day}일({weekday_kr})입니다. "
        "한국 증시는 낮(09:00~15:30)에 열립니다. '오늘 국내장'이라 쓰지 말고 "
        f"'{nd.month}월 {nd.day}일({weekday_kr}) 국내장' 또는 '다음 거래일 국내 증시'로 표현하세요. "
        "주말/마감된 미국장 흐름이 그날 국내장에 줄 관찰 포인트를 중립적으로 적으세요."
    )
