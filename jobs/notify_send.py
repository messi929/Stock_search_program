"""알림 발송 Job (이메일 / Mailgun) — 진입선 도달 알림 + 일일 시황 브리핑.

--mode entry (기본, 장중 30분 주기):
  opt-in 사용자의 관심종목 진입선(관찰 구간 tier_1/2/3)과 현재가(stocks.close)를
  비교해 **새로 도달한 구간만** 발송. 중복은 notify_state/entry_points armed 맵으로
  방지하고, 구간 위로 +REARM_PCT 회복 시 재무장해 다음 하락에 다시 알린다.

--mode briefing (아침 1회):
  당일 시황 브리핑(axis_briefing_cache 캐시, 없으면 ResearchAgent로 생성)을
  opt-in 사용자에게 발송. notify_state/briefing.last_sent_date로 하루 1회 보장.

LEGAL: "추천"·"매수가"·"목표가"·"매수/매도 신호" 금지.
       진입선은 사용자가 저장한 '관찰 구간', 본 알림은 도달 사실의 정보 제공일 뿐.
       모든 메일 하단에 면책 문구(agents.base.DISCLAIMER) 포함.

실행 예:
  python -m jobs.notify_send                       # 진입선 알림 실제 발송
  python -m jobs.notify_send --mode briefing       # 일일 브리핑 발송
  python -m jobs.notify_send --dry-run             # 발송·상태쓰기 skip (판정만)
  python -m jobs.notify_send --limit 50            # 처리 사용자 수 제한(테스트)

Cloud Run Job 등록은 deploy-notify-job.sh 참고.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Optional

from loguru import logger

# 관찰 구간 회복 재무장 임계 — 구간 대비 +3% 위로 회복 시 재무장(노이즈 방지)
REARM_PCT = 0.03

# 관찰 구간 라벨
TIER_LABELS = {
    "tier_1": "1차 관찰 구간",
    "tier_2": "2차 관찰 구간",
    "tier_3": "3차 관찰 구간",
}

_FALLBACK_DISCLAIMER = (
    "이 분석은 투자 권유가 아닌 정보 제공입니다. "
    "최종 판단은 사용자 본인의 책임입니다. Axis는 투자자문업 면허가 없습니다."
)


def _disclaimer() -> str:
    try:
        from agents.base import DISCLAIMER

        return DISCLAIMER
    except Exception:
        return _FALLBACK_DISCLAIMER


def _app_base_url() -> str:
    import os

    return os.environ.get("APP_BASE_URL", "https://axislytics.com").rstrip("/")


def _pro_only() -> bool:
    import os

    return os.environ.get("ENTRY_ALERT_PRO_ONLY", "false").lower() == "true"


def _kst_today() -> str:
    """Cloud Run(UTC) → +9h KST 날짜(YYYY-MM-DD). ai.py와 동일 규칙."""
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")


# ──────────────────────────────────────────────
# 가격 맵
# ──────────────────────────────────────────────


def build_price_map() -> dict[str, dict[str, Any]]:
    """stocks 컬렉션 → {ticker: {"name": str, "close": float}} (KR+US+ETF).

    Job 런타임 1회 벌크 로드 — 종목당 외부 호출 없음.
    """
    from screener.db.repository import load_stocks

    out: dict[str, dict[str, Any]] = {}
    for source in ("kr", "us", "etf"):
        try:
            df = load_stocks(source=source)
        except Exception as e:
            logger.warning(f"load_stocks({source}) 실패: {type(e).__name__}: {e}")
            continue
        if df is None or df.empty or "close" not in df.columns:
            continue
        for _, row in df.iterrows():
            ticker = str(row.get("ticker", "")).strip()
            close = row.get("close")
            if not ticker or close is None:
                continue
            try:
                close_f = float(close)
            except (TypeError, ValueError):
                continue
            if close_f <= 0:
                continue
            # 동일 ticker가 여러 source에 있으면 먼저 로드된 것 유지
            out.setdefault(ticker, {"name": str(row.get("name", "") or ticker), "close": close_f})
    logger.info(f"가격 맵 로드: {len(out)}종목")
    return out


def fmt_price(ticker: str, value: float) -> str:
    """KR(숫자 코드)=원, 그 외(US)=$ 표기."""
    if ticker.isdigit():
        return f"{int(round(value)):,}원"
    return f"${value:,.2f}"


# ──────────────────────────────────────────────
# 사용자 조회
# ──────────────────────────────────────────────


def iter_optin_users(db: Any, limit: Optional[int] = None):
    """진입선 알림 opt-in 사용자 문서 순회 (인덱스 equality 쿼리 — 전량 스캔 아님)."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    q = db.collection("users").where(
        filter=FieldFilter("notification_preferences.entry_point_alerts_enabled", "==", True)
    )
    n = 0
    for doc in q.stream():
        yield doc
        n += 1
        if limit and n >= limit:
            break


def recipient_email(db: Any, uid: str, user_data: dict) -> str:
    """수신 이메일 — notification_preferences.email_override → users.email → Firebase Auth."""
    prefs = user_data.get("notification_preferences") or {}
    override = (prefs.get("email_override") or "").strip()
    if override:
        return override
    email = (user_data.get("email") or "").strip()
    if email:
        return email
    try:
        from firebase_admin import auth as fb_auth

        rec = fb_auth.get_user(uid)
        return (rec.email or "").strip()
    except Exception:
        return ""


# ──────────────────────────────────────────────
# 진입선 판정
# ──────────────────────────────────────────────


def load_entry_points(db: Any, uid: str) -> dict[str, dict]:
    """users/{uid}/watchlist_meta → {ticker: entry_points dict}."""
    out: dict[str, dict] = {}
    try:
        col = db.collection("users").document(uid).collection("watchlist_meta").stream()
        for d in col:
            x = d.to_dict() or {}
            ep = x.get("entry_points")
            if ep:
                out[d.id] = ep
    except Exception as e:
        logger.warning(f"watchlist_meta 조회 실패 uid={uid}: {e}")
    return out


def _state_doc(db: Any, uid: str):
    return db.collection("users").document(uid).collection("notify_state").document("entry_points")


def evaluate_user(
    db: Any,
    uid: str,
    entry_map: dict[str, dict],
    price_map: dict[str, dict],
    armed: dict[str, dict],
) -> tuple[list[dict], dict[str, dict], list[tuple[str, str, float]]]:
    """진입선 도달 판정.

    Returns:
        (triggers, armed_after_rearm, pending_arm)
        - triggers: 발송할 알림 [{ticker, name, close, hits:[{tier_label, price, basis}]}]
        - armed_after_rearm: 재무장(가격 회복) 반영된 armed 맵 (trigger 추가는 미반영)
        - pending_arm: 발송 성공 시 armed에 추가할 [(ticker, tier_name, close)]
    """
    triggers: list[dict] = []
    pending_arm: list[tuple[str, str, float]] = []
    armed = {t: dict(v) for t, v in armed.items()}  # 복사

    for ticker, ep in entry_map.items():
        price_row = price_map.get(ticker)
        if not price_row:
            continue
        close = price_row["close"]
        name = price_row["name"]
        basis = ep.get("technical_basis") or []
        hits: list[dict] = []

        for tier_name in ("tier_1", "tier_2", "tier_3"):
            tp = ep.get(tier_name)
            try:
                tp = float(tp) if tp is not None else 0.0
            except (TypeError, ValueError):
                tp = 0.0
            if tp <= 0:
                continue

            armed_price = armed.get(ticker, {}).get(tier_name)

            if close <= tp and armed_price is None:
                # 신규 도달 → 발송 대상
                hits.append({
                    "tier_label": TIER_LABELS.get(tier_name, tier_name),
                    "price": tp,
                    "basis": basis,
                })
                pending_arm.append((ticker, tier_name, close))
            elif armed_price is not None and close >= tp * (1 + REARM_PCT):
                # 구간 위로 충분히 회복 → 재무장
                armed.get(ticker, {}).pop(tier_name, None)
                if ticker in armed and not armed[ticker]:
                    armed.pop(ticker, None)

        if hits:
            triggers.append({"ticker": ticker, "name": name, "close": close, "hits": hits})

    return triggers, armed, pending_arm


# ──────────────────────────────────────────────
# 이메일 렌더링
# ──────────────────────────────────────────────


def render_email(triggers: list[dict]) -> tuple[str, str, str]:
    """도달 알림 → (subject, html, text). LEGAL 준수."""
    base = _app_base_url()
    n_stocks = len(triggers)
    first = triggers[0]["name"]
    if n_stocks == 1:
        subject = f"[Axis] {first} 관찰 구간 도달"
    else:
        subject = f"[Axis] {first} 외 {n_stocks - 1}개 종목 관찰 구간 도달"

    rows_html: list[str] = []
    lines_text: list[str] = [f"관찰 종목 {n_stocks}개가 저장한 관찰 구간에 도달했습니다.\n"]
    for t in triggers:
        ticker, name, close = t["ticker"], t["name"], t["close"]
        link = f"{base}/stocks/{ticker}"
        hit_html = "".join(
            f"<li style='margin:2px 0;color:#374151;'>{h['tier_label']} "
            f"<b>{fmt_price(ticker, h['price'])}</b> 도달</li>"
            for h in t["hits"]
        )
        rows_html.append(
            f"<div style='border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;margin:10px 0;'>"
            f"<div style='font-size:16px;font-weight:700;color:#111827;'>{name} "
            f"<span style='font-size:13px;color:#6b7280;font-weight:500;'>({ticker})</span></div>"
            f"<div style='font-size:13px;color:#6b7280;margin:4px 0 8px;'>현재가 "
            f"<b style='color:#111827;'>{fmt_price(ticker, close)}</b></div>"
            f"<ul style='margin:0;padding-left:18px;font-size:13px;'>{hit_html}</ul>"
            f"<a href='{link}' style='display:inline-block;margin-top:10px;font-size:13px;"
            f"color:#2563eb;text-decoration:none;'>데이터로 직접 판단해보기 →</a>"
            f"</div>"
        )
        hit_text = ", ".join(f"{h['tier_label']} {fmt_price(ticker, h['price'])}" for h in t["hits"])
        lines_text.append(f"- {name} ({ticker}) 현재가 {fmt_price(ticker, close)} | {hit_text}\n  {link}")

    disclaimer = _disclaimer()
    html = (
        f"<div style='font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;"
        f"max-width:560px;margin:0 auto;padding:8px;'>"
        f"<h2 style='font-size:18px;color:#111827;margin:8px 0 4px;'>관찰 구간 도달 알림</h2>"
        f"<p style='font-size:14px;color:#6b7280;margin:0 0 8px;'>"
        f"저장하신 관찰 구간에 현재가가 도달했습니다. 아래 데이터로 직접 판단해보세요.</p>"
        f"{''.join(rows_html)}"
        f"<p style='font-size:12px;color:#9ca3af;line-height:1.6;"
        f"border-top:1px solid #f3f4f6;margin-top:16px;padding-top:12px;'>📌 {disclaimer}</p>"
        f"<p style='font-size:11px;color:#cbd5e1;margin-top:8px;'>"
        f"알림 설정은 Axis 앱 → 알림 설정에서 변경할 수 있습니다.</p>"
        f"</div>"
    )
    text = "\n".join(lines_text) + f"\n\n📌 {disclaimer}"
    return subject, html, text


# ──────────────────────────────────────────────
# 일일 시황 브리핑
# ──────────────────────────────────────────────

_BRIEFING_COLLECTION = "axis_briefing_cache"
_SENTIMENT_COLOR = {"낙관적": "#16a34a", "신중": "#d97706", "비관적": "#dc2626"}


def ensure_briefing(db: Any, date_str: str) -> Optional[dict]:
    """당일 브리핑 payload 확보 — 캐시 우선, 없으면 ResearchAgent로 생성·캐시.

    ai.py /briefing 과 동일한 캐시 doc(axis_briefing_cache/{date})·payload 구조 재사용.
    생성은 Haiku(~5원). 생성 실패 시 None.
    """
    try:
        doc = db.collection(_BRIEFING_COLLECTION).document(date_str).get()
        if doc.exists:
            payload = (doc.to_dict() or {}).get("payload")
            if payload:
                logger.info(f"브리핑 캐시 사용 ({date_str})")
                return payload
    except Exception as e:
        logger.warning(f"브리핑 캐시 조회 실패 ({date_str}): {e}")

    # 캐시 없음 → 생성 (ANTHROPIC_API_KEY 필요)
    try:
        import asyncio

        from agents.base import DISCLAIMER
        from agents.research import ResearchAgent, ResearchInput

        logger.info(f"브리핑 생성 시작 ({date_str}) — ResearchAgent")
        t0 = time.time()
        result = asyncio.run(
            ResearchAgent().run(
                ResearchInput(
                    query="오늘 한국 증시 전체 시황을 뉴스·매크로·섹터·외국인/기관 수급 관점에서 종합 분석",
                    timeframe_days=7,
                )
            )
        )
        payload = {
            "date": date_str,
            "research": result.model_dump(),
            "disclaimer": DISCLAIMER,
            "elapsed": round(time.time() - t0, 2),
        }
        try:
            from firebase_admin import firestore

            db.collection(_BRIEFING_COLLECTION).document(date_str).set(
                {"payload": payload, "created_at": firestore.SERVER_TIMESTAMP}
            )
        except Exception as e:
            logger.warning(f"브리핑 캐시 저장 실패: {e}")
        logger.info(f"브리핑 생성 완료 ({date_str}, {payload['elapsed']}s)")
        return payload
    except Exception as e:
        logger.error(f"브리핑 생성 실패: {type(e).__name__}: {e}")
        return None


def iter_briefing_users(db: Any, limit: Optional[int] = None):
    """일일 브리핑 opt-in 사용자 순회 (인덱스 equality 쿼리)."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    q = db.collection("users").where(
        filter=FieldFilter("notification_preferences.daily_briefing_enabled", "==", True)
    )
    n = 0
    for doc in q.stream():
        yield doc
        n += 1
        if limit and n >= limit:
            break


def render_briefing_email(payload: dict) -> tuple[str, str, str]:
    """브리핑 payload → (subject, html, text). LEGAL: 면책 포함, 추천 금지."""
    research = payload.get("research") or {}
    date_str = payload.get("date", _kst_today())
    sentiment = research.get("market_sentiment") or "신중"
    summary = (research.get("summary") or "").strip()
    news = research.get("relevant_news") or []
    macro = research.get("macro_context") or {}
    sectors = research.get("sector_status") or []
    base = _app_base_url()

    color = _SENTIMENT_COLOR.get(sentiment, "#6b7280")
    subject = f"[Axis] {date_str} 오늘의 시장 브리핑 — {sentiment}"

    # 뉴스 상위 5 (relevance 내림차순)
    news_sorted = sorted(news, key=lambda x: x.get("relevance_score", 0) or 0, reverse=True)[:5]
    news_html = "".join(
        f"<li style='margin:4px 0;color:#374151;'>{n.get('headline','')} "
        f"<span style='color:#9ca3af;font-size:12px;'>({n.get('source','')})</span></li>"
        for n in news_sorted
    )
    risks = (macro.get("key_risks") or [])[:4]
    opps = (macro.get("key_opportunities") or [])[:4]
    sectors_html = "".join(
        f"<li style='margin:3px 0;color:#374151;'><b>{s.get('name','')}</b> "
        f"<span style='color:#6b7280;'>{s.get('status','')}</span></li>"
        for s in sectors[:5]
    )

    def _section(title: str, body: str) -> str:
        if not body:
            return ""
        return (
            f"<div style='margin:14px 0;'>"
            f"<div style='font-size:14px;font-weight:700;color:#111827;margin-bottom:4px;'>{title}</div>"
            f"{body}</div>"
        )

    risks_html = "".join(f"<li style='color:#374151;margin:2px 0;'>{r}</li>" for r in risks)
    opps_html = "".join(f"<li style='color:#374151;margin:2px 0;'>{o}</li>" for o in opps)

    disclaimer = payload.get("disclaimer") or _disclaimer()
    html = (
        f"<div style='font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;"
        f"max-width:560px;margin:0 auto;padding:8px;'>"
        f"<div style='font-size:13px;color:#9ca3af;'>{date_str} 시장 브리핑</div>"
        f"<h2 style='font-size:18px;color:#111827;margin:4px 0 10px;'>오늘의 시장 심리 "
        f"<span style='color:{color};'>{sentiment}</span></h2>"
        + (f"<p style='font-size:14px;color:#374151;line-height:1.7;'>{summary}</p>" if summary else "")
        + _section("주요 뉴스", f"<ul style='margin:0;padding-left:18px;font-size:13px;'>{news_html}</ul>" if news_html else "")
        + _section("관찰 리스크", f"<ul style='margin:0;padding-left:18px;font-size:13px;'>{risks_html}</ul>" if risks_html else "")
        + _section("관찰 기회", f"<ul style='margin:0;padding-left:18px;font-size:13px;'>{opps_html}</ul>" if opps_html else "")
        + _section("섹터 동향", f"<ul style='margin:0;padding-left:18px;font-size:13px;'>{sectors_html}</ul>" if sectors_html else "")
        + f"<a href='{base}' style='display:inline-block;margin-top:12px;font-size:13px;"
        f"color:#2563eb;text-decoration:none;'>Axis에서 더 보기 →</a>"
        f"<p style='font-size:12px;color:#9ca3af;line-height:1.6;"
        f"border-top:1px solid #f3f4f6;margin-top:16px;padding-top:12px;'>📌 {disclaimer}</p>"
        f"<p style='font-size:11px;color:#cbd5e1;margin-top:8px;'>"
        f"알림 설정은 Axis 앱 → 알림 설정에서 변경할 수 있습니다.</p>"
        f"</div>"
    )

    text_parts = [f"{date_str} 시장 브리핑 — 시장 심리: {sentiment}", ""]
    if summary:
        text_parts.append(summary)
    if news_sorted:
        text_parts.append("\n[주요 뉴스]")
        text_parts += [f"- {n.get('headline','')} ({n.get('source','')})" for n in news_sorted]
    if risks:
        text_parts.append("\n[관찰 리스크]")
        text_parts += [f"- {r}" for r in risks]
    text_parts.append(f"\n📌 {disclaimer}")
    text = "\n".join(text_parts)
    return subject, html, text


def run_briefing(dry_run: bool = False, limit: Optional[int] = None) -> dict[str, Any]:
    """일일 시황 브리핑 발송 실행 (하루 1회, 중복 발송 방지)."""
    t0 = time.time()
    from screener.db.firebase_client import get_db
    from screener.services import mailer

    configured = mailer.is_configured()
    if not configured and not dry_run:
        logger.warning("Mailgun 미설정 — 브리핑 발송 조기 종료")
        return {"users": 0, "emails_sent": 0, "skipped": "mailgun_unconfigured",
                "elapsed_sec": round(time.time() - t0, 1)}

    db = get_db()
    date_str = _kst_today()
    payload = ensure_briefing(db, date_str)
    if not payload:
        logger.warning("브리핑 payload 확보 실패 — 종료")
        return {"users": 0, "emails_sent": 0, "skipped": "no_briefing",
                "elapsed_sec": round(time.time() - t0, 1)}

    subject, html, text = render_briefing_email(payload)
    users_n = sent_n = 0

    for udoc in iter_briefing_users(db, limit=limit):
        uid = udoc.id
        udata = udoc.to_dict() or {}
        users_n += 1

        # 하루 1회 — 이미 오늘 발송했으면 skip (재실행·재시도 대비)
        state_ref = db.collection("users").document(uid).collection("notify_state").document("briefing")
        try:
            sdoc = state_ref.get()
            if sdoc.exists and (sdoc.to_dict() or {}).get("last_sent_date") == date_str:
                continue
        except Exception:
            pass

        email = recipient_email(db, uid, udata)
        ok = False
        if dry_run:
            ok = True
            logger.info(f"[브리핑·dry] uid={uid} 수신={email or '(없음)'}")
        elif email:
            ok = mailer.send_email(email, subject, html, text)
        else:
            logger.warning(f"수신 이메일 없음 uid={uid} — 브리핑 skip")

        if ok:
            sent_n += 1
            if not dry_run:
                try:
                    state_ref.set({"last_sent_date": date_str, "updated_at": time.time()})
                except Exception as e:
                    logger.warning(f"브리핑 state 저장 실패 uid={uid}: {e}")

    summary = {
        "mode": "briefing",
        "date": date_str,
        "users": users_n,
        "emails_sent": sent_n,
        "dry_run": dry_run,
        "mailgun_configured": configured,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    logger.info("=" * 56)
    logger.info("일일 브리핑 발송 완료")
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
    logger.info("=" * 56)
    return summary


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────


def run_notify(dry_run: bool = False, limit: Optional[int] = None) -> dict[str, Any]:
    """진입선 도달 알림 발송 실행."""
    t0 = time.time()
    from screener.db.firebase_client import get_db
    from screener.services import mailer

    configured = mailer.is_configured()
    if not configured and not dry_run:
        logger.warning(
            "Mailgun 미설정(MAILGUN_API_KEY/DOMAIN/FROM) — 발송 불가로 조기 종료. "
            "시크릿 등록 후 재실행하세요(미발송 분은 다음 실행 시 발송)."
        )
        return {"users": 0, "emails_sent": 0, "skipped": "mailgun_unconfigured",
                "elapsed_sec": round(time.time() - t0, 1)}

    db = get_db()
    price_map = build_price_map()
    if not price_map:
        logger.warning("가격 맵이 비어있음 — 종료")
        return {"users": 0, "emails_sent": 0, "skipped": "empty_price_map",
                "elapsed_sec": round(time.time() - t0, 1)}

    pro_only = _pro_only()
    users_n = sent_n = trig_n = 0

    for udoc in iter_optin_users(db, limit=limit):
        uid = udoc.id
        udata = udoc.to_dict() or {}
        users_n += 1

        if pro_only and (udata.get("tier") or "free").lower() != "pro":
            continue

        entry_map = load_entry_points(db, uid)
        if not entry_map:
            continue

        state_ref = _state_doc(db, uid)
        try:
            sdoc = state_ref.get()
            armed = (sdoc.to_dict() or {}).get("armed", {}) if sdoc.exists else {}
        except Exception as e:
            logger.warning(f"notify_state 조회 실패 uid={uid}: {e}")
            armed = {}

        triggers, armed_after, pending_arm = evaluate_user(
            db, uid, entry_map, price_map, armed
        )

        state_changed = armed_after != armed  # 재무장 반영분

        if triggers:
            trig_n += len(triggers)
            email = recipient_email(db, uid, udata)
            subject, html, text = render_email(triggers)
            logger.info(
                f"[알림] uid={uid} 종목={len(triggers)} 수신={email or '(없음)'} dry_run={dry_run}"
            )
            ok = False
            if dry_run:
                ok = True
            elif email:
                ok = mailer.send_email(email, subject, html, text)
            else:
                logger.warning(f"수신 이메일 없음 uid={uid} — 발송 skip")

            if ok and not dry_run:
                sent_n += 1
                for ticker, tier_name, close in pending_arm:
                    armed_after.setdefault(ticker, {})[tier_name] = close
                state_changed = True
            elif ok and dry_run:
                sent_n += 1  # dry-run 가상 카운트

        if state_changed and not dry_run:
            try:
                state_ref.set({"armed": armed_after, "updated_at": time.time()})
            except Exception as e:
                logger.warning(f"notify_state 저장 실패 uid={uid}: {e}")

    summary = {
        "users": users_n,
        "triggers": trig_n,
        "emails_sent": sent_n,
        "dry_run": dry_run,
        "mailgun_configured": configured,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    logger.info("=" * 56)
    logger.info("진입선 도달 알림 완료")
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
    logger.info("=" * 56)
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="알림 발송 (이메일/Mailgun)")
    parser.add_argument(
        "--mode", choices=["entry", "briefing"], default="entry",
        help="entry=진입선 도달 알림(장중 30분), briefing=일일 시황 브리핑(아침 1회)",
    )
    parser.add_argument("--dry-run", action="store_true", help="발송·상태쓰기 skip (판정만)")
    parser.add_argument("--limit", type=int, default=None, help="처리 사용자 수 제한(테스트)")
    args = parser.parse_args(argv)

    if args.mode == "briefing":
        run_briefing(dry_run=args.dry_run, limit=args.limit)
    else:
        run_notify(dry_run=args.dry_run, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
