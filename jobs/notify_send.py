"""진입선 도달 알림 발송 Job (이메일 / Mailgun).

장중 30분 주기 실행. opt-in 사용자의 관심종목 진입선(관찰 구간 tier_1/2/3)과
현재가(stocks.close)를 비교해 **새로 도달한 구간만** 이메일로 발송한다.
중복 발송은 users/{uid}/notify_state/entry_points 의 armed 맵으로 방지하고,
가격이 구간 위로 충분히(REARM_PCT) 회복하면 재무장해 다음 하락 시 다시 알린다.

LEGAL: "추천"·"매수가"·"목표가"·"매수/매도 신호" 금지.
       진입선은 사용자가 저장한 '관찰 구간'이며, 본 알림은 도달 사실의 정보 제공일 뿐.
       모든 메일 하단에 면책 문구(agents.base.DISCLAIMER) 포함.

실행 예:
  python -m jobs.notify_send                 # 실제 발송
  python -m jobs.notify_send --dry-run       # 발송·상태쓰기 skip (판정만)
  python -m jobs.notify_send --limit 50      # 처리 사용자 수 제한(테스트)

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

    parser = argparse.ArgumentParser(description="진입선 도달 알림 발송 (이메일/Mailgun)")
    parser.add_argument("--dry-run", action="store_true", help="발송·상태쓰기 skip (판정만)")
    parser.add_argument("--limit", type=int, default=None, help="처리 사용자 수 제한(테스트)")
    args = parser.parse_args(argv)

    run_notify(dry_run=args.dry_run, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
