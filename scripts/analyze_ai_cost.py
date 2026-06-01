"""실측: Firestore에 쌓인 Axis AI 사용량/비용 집계 (read-only).

users/{uid}/ai_usage/{YYYY-MM-DD} + ai_usage_anonymous/{date} 를 합산해
에이전트별 호출수·토큰·비용(KRW), 분석 1건당 평균 단가를 산출한다.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

key_path = os.environ.get("FIREBASE_KEY_PATH", "")
if not firebase_admin._apps:
    if key_path and os.path.exists(key_path):
        firebase_admin.initialize_app(credentials.Certificate(key_path))
    else:
        firebase_admin.initialize_app()

db = firestore.client()

# 집계 버킷
agent_calls: dict[str, int] = defaultdict(int)
agent_in: dict[str, int] = defaultdict(int)
agent_out: dict[str, int] = defaultdict(int)
agent_cr: dict[str, int] = defaultdict(int)
agent_cw: dict[str, int] = defaultdict(int)
agent_krw: dict[str, float] = defaultdict(float)
total_krw = 0.0
doc_count = 0
user_count = 0


def _ingest(data: dict):
    """Firestore가 'agents.<name>.<field>' 평면 키로 저장 → 점 파싱."""
    global total_krw, doc_count
    doc_count += 1
    for k, v in data.items():
        parts = k.split(".")
        if len(parts) == 3 and parts[0] == "agents":
            _, name, field = parts
            if field == "calls":
                agent_calls[name] += int(v or 0)
            elif field == "input_tokens":
                agent_in[name] += int(v or 0)
            elif field == "output_tokens":
                agent_out[name] += int(v or 0)
            elif field == "cache_read_tokens":
                agent_cr[name] += int(v or 0)
            elif field == "cache_creation_tokens":
                agent_cw[name] += int(v or 0)
            elif field == "krw":
                agent_krw[name] += float(v or 0)
        elif k == "total.krw":
            total_krw += float(v or 0)


# 1) 사용자별 ai_usage
for u in db.collection("users").stream():
    sub = list(u.reference.collection("ai_usage").stream())
    if sub:
        user_count += 1
    for d in sub:
        _ingest(d.to_dict() or {})

# 2) 익명
for d in db.collection("ai_usage_anonymous").stream():
    _ingest(d.to_dict() or {})

print("=" * 60)
print(f"집계 문서 수: {doc_count}  /  ai_usage 보유 사용자 수: {user_count}")
print(f"총 누적 비용: {total_krw:,.0f}원")
print("=" * 60)
print(f"{'agent':<18}{'calls':>8}{'krw':>12}{'krw/call':>10}{'avg_out':>9}")
print("-" * 60)
for name in sorted(agent_calls, key=lambda n: -agent_krw[n]):
    c = agent_calls[name]
    krw = agent_krw[name]
    avg = krw / c if c else 0
    avg_out = agent_out[name] / c if c else 0
    print(f"{name:<18}{c:>8}{krw:>12,.0f}{avg:>10,.1f}{avg_out:>9,.0f}")

print("-" * 60)
strat = agent_calls.get("strategist", 0)
if strat:
    print(f"\n딥다이브 1건(=strategist {strat}회) 당 평균 총비용: "
          f"{total_krw / strat:,.1f}원")
else:
    print("\n(strategist 호출 기록 없음 - 딥다이브 단가 산출 불가)")
