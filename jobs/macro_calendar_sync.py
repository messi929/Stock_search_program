"""매크로 일정 자동 갱신 Job (FOMC·금통위·CPI·고용·GDP).

실행 시나리오 (Cloud Run Job + Cloud Scheduler):
  - 매주 월요일 05:00 KST
  - 공식 출처에서 일정을 받아 Firestore config/macro_calendar 를 갱신
  - 서비스(regime_detector._load_calendar)는 이 문서를 6시간 캐시로 읽는다

실패 처리:
  - 출처 하나가 실패해도 나머지는 반영하고, 그 유형의 기존 일정은 유지한다.
  - 하나라도 실패하면 exit 1 → 잡 실패로 드러난다 (조용히 낡는 것 방지).
  - 오늘 이후 FOMC가 하나도 없으면(모든 출처 실패 + 기존 일정 만료) exit 2.

사용 예:
  python -m jobs.macro_calendar_sync --dry-run       # 수집·변경 내역만 출력
  python -m jobs.macro_calendar_sync --write-file    # data/macro_calendar.json도 갱신(로컬)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from utils.data_collectors.macro_calendar_sync import fetch_all, merge_events
from utils.data_collectors.regime_detector import (
    CALENDAR_FILE,
    REMOTE_CALENDAR_COLLECTION,
    REMOTE_CALENDAR_DOC,
    _fetch_remote_calendar,
)


def _load_base() -> dict[str, Any]:
    """병합 기준: Firestore 문서, 없으면 이미지의 JSON 파일."""
    remote = _fetch_remote_calendar()
    if remote:
        return remote
    with open(CALENDAR_FILE, encoding="utf-8") as f:
        return json.load(f)


def run(dry_run: bool = False, write_file: bool = False) -> int:
    now = datetime.now(timezone.utc)
    today = datetime.now().date()

    base = _load_base()
    results = fetch_all(today)
    events, changes = merge_events(base.get("events", []), results)

    failed = {r.type: r.error for r in results if not r.ok}
    for t, ch in changes.items():
        logger.info(f"[macro-cal] {t} 변경: 추가 {ch['added']} / 삭제 {ch['removed']}")
    if not changes:
        logger.info("[macro-cal] 변경 없음")

    meta = dict(base.get("_meta") or {})
    meta.update(
        {
            "synced_at": now.isoformat(),
            "sources": {
                r.type: ({"ok": True, "count": len(r.events), "window": list(r.window)} if r.ok
                         else {"ok": False, "error": r.error})
                for r in results
            },
            "policy": "jobs/macro_calendar_sync.py 매주 자동 갱신 (출처 실패 시 기존 일정 유지)",
        }
    )
    doc = {"_meta": meta, "events": events}

    if dry_run:
        logger.info(f"[macro-cal] dry-run — 저장 생략 (총 {len(events)}건)")
    else:
        from screener.db.firebase_client import get_db

        get_db().collection(REMOTE_CALENDAR_COLLECTION).document(REMOTE_CALENDAR_DOC).set(doc)
        logger.info(f"[macro-cal] Firestore 저장 완료 ({len(events)}건)")

    if write_file:
        _write_json(doc)
        logger.info(f"[macro-cal] {CALENDAR_FILE} 갱신")

    upcoming_fomc = [e for e in events if e.get("type") == "FOMC" and e["date"] >= today.isoformat()]
    if not upcoming_fomc:
        logger.error("[macro-cal] 오늘 이후 FOMC 일정이 없음 — 캘린더가 비어 감")
        return 2
    if failed:
        logger.error(f"[macro-cal] 실패한 출처 {len(failed)}개: {failed}")
        return 1
    return 0


def _write_json(doc: dict[str, Any]) -> None:
    """한 줄에 일정 하나씩 — 사람이 diff로 검토하기 쉽게."""
    meta_str = json.dumps(doc["_meta"], ensure_ascii=False, indent=2).replace("\n", "\n  ")
    lines = ["{", f'  "_meta": {meta_str},', '  "events": [']
    evs = doc["events"]
    for i, e in enumerate(evs):
        lines.append("    " + json.dumps(e, ensure_ascii=False) + ("," if i < len(evs) - 1 else ""))
    lines += ["  ]", "}", ""]
    CALENDAR_FILE.write_text("\n".join(lines), encoding="utf-8")
    json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))  # 깨진 JSON이면 여기서 실패


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="매크로 일정 자동 갱신")
    p.add_argument("--dry-run", action="store_true", help="Firestore 저장 생략")
    p.add_argument("--write-file", action="store_true", help="data/macro_calendar.json도 갱신")
    a = p.parse_args(argv)
    return run(dry_run=a.dry_run, write_file=a.write_file)


if __name__ == "__main__":
    sys.exit(main())
