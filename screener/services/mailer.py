"""Mailgun 메일 발송 유틸.

환경변수:
  MAILGUN_API_KEY     — Mailgun API 키
  MAILGUN_DOMAIN      — 인증된 도메인 (예: mg.yourdomain.com)
  MAILGUN_FROM        — 발신자 (예: "StockFinder <noreply@mg.yourdomain.com>")
  MAILGUN_REGION      — us(기본) 또는 eu
"""

import os

import httpx
from loguru import logger


MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "")
MAILGUN_FROM = os.environ.get(
    "MAILGUN_FROM",
    f"StockFinder <noreply@{MAILGUN_DOMAIN}>" if MAILGUN_DOMAIN else "",
)
MAILGUN_REGION = os.environ.get("MAILGUN_REGION", "us").lower()


def is_configured() -> bool:
    return bool(MAILGUN_API_KEY and MAILGUN_DOMAIN and MAILGUN_FROM)


def _endpoint() -> str:
    host = "api.eu.mailgun.net" if MAILGUN_REGION == "eu" else "api.mailgun.net"
    return f"https://{host}/v3/{MAILGUN_DOMAIN}/messages"


def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    """Mailgun 메일 발송. 성공 시 True."""
    if not is_configured():
        logger.warning("Mailgun 미설정 — 발송 생략")
        return False
    data = {"from": MAILGUN_FROM, "to": to, "subject": subject, "html": html}
    if text:
        data["text"] = text
    try:
        resp = httpx.post(
            _endpoint(),
            auth=("api", MAILGUN_API_KEY),
            data=data,
            timeout=15.0,
        )
        if resp.status_code == 200:
            return True
        logger.warning(f"Mailgun 발송 실패 {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"Mailgun 요청 에러: {e}")
        return False
