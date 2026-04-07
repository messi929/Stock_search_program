"""종목탐색기 설정.

RUN_MODE:
  - "server": 중앙 서버 (크롤링 + Firestore + API 서빙)
  - "client": 데스크톱 앱 (원격 서버에 접속만)
"""

import json
import os
import sys
from pathlib import Path

# 프로젝트 루트
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).parent.parent

SCREENER_ROOT = PROJECT_ROOT / "screener" if (PROJECT_ROOT / "screener").exists() else Path(__file__).parent


# ──────────────────────────────────────────────
# 실행 모드 (server / client)
# ──────────────────────────────────────────────

def _load_client_config() -> dict:
    """client_config.json 로드 (exe 옆 또는 프로젝트 루트)."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "client_config.json")
    candidates.append(PROJECT_ROOT / "client_config.json")
    for p in candidates:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return {}


_client_cfg = _load_client_config()

# server: 크롤링+DB+API 전부 실행 | client: 원격 서버 접속만
RUN_MODE = os.environ.get("RUN_MODE", _client_cfg.get("run_mode", "client"))

# client 모드에서 접속할 중앙 서버 URL
SERVER_URL = os.environ.get("SERVER_URL", _client_cfg.get("server_url", "http://localhost:8501"))

# 서버 관리자 키 (refresh 등 관리 API 보호)
ADMIN_KEY = os.environ.get("ADMIN_KEY", _client_cfg.get("admin_key", ""))

# 데이터 수집 모드:
#   "full"     — 크롤링 + Firestore 쓰기 (기존 동작, 로컬 개발)
#   "readonly" — Firestore 읽기만 (Cloud Run 서빙 전용, 크롤링 없음)
COLLECT_MODE = os.environ.get("COLLECT_MODE", _client_cfg.get("collect_mode", "full"))


# ──────────────────────────────────────────────
# 서버 모드 전용 설정
# ──────────────────────────────────────────────

# 데이터 캐시
CACHE_DIR = SCREENER_ROOT / "cache"
if RUN_MODE == "server":
    CACHE_DIR.mkdir(exist_ok=True)

HISTORY_DAYS = 250  # 52주(약 250거래일) — MA/RSI/52주고저 정확도 보장
REFRESH_INTERVAL_MIN = 30

# 급등주 기준
SURGE_CHANGE_PCT = 5.0
SURGE_VOLUME_RATIO = 3.0
SURGE_MIN_SCORE = 2

# 급등 예보 최소 점수 (0~5 중 N개 이상 충족)
PRE_SURGE_MIN_SCORE = 4  # 기존 3→4로 강화

# 시가총액 단위: 억원
DEFAULT_MARKET_CAP_MIN = 500
DEFAULT_MARKET_CAP_MAX = 999999

# 거래대금 최소 (원)
MIN_TRADING_VALUE = 10_0000_0000  # 10억원
