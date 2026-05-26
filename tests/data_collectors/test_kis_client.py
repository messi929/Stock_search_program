"""KIS REST 클라이언트 단위 테스트 (mock httpx 기반).

⚠️ 라이브 호출은 scripts/check_kis_smoke.py 참고. 여기는 mock만.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.data_collectors.kis_client import (
    KIS_PAPER_BASE,
    KIS_REAL_BASE,
    KisClient,
    _CachedToken,
    mask_kis_secrets_in_str,
)


# ──────────────────────────────────────────────
# 1. 키 마스킹
# ──────────────────────────────────────────────


def test_mask_app_key():
    s = "appkey=PSR6WkhkNOJD0tEyfUkp7OZ7XtVCNhqdmfhP failed"
    assert "PSR6Wkhk" not in mask_kis_secrets_in_str(s)
    assert "PS***" in mask_kis_secrets_in_str(s)


def test_mask_app_secret():
    secret = "wk6zlY75ONil7N4Nhp0hS7dNuV4kvVEgRXH75m9Xr78sbhQVzXQ5cHF7hAVRMZwlepQKzc8X4zO5VkDmAxwhQgsD90BmuW85gAXk2KHK0KKYJ3zAUkxzOedSoa6bxjc2ISbjD4neon2zOjrJWAv67OEFw9devYipF1ZXPNK9XMD4M"
    s = f"secret={secret}"
    masked = mask_kis_secrets_in_str(s)
    assert secret not in masked
    assert "***" in masked


def test_mask_bearer():
    s = "authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.abc.def"
    assert "Bearer ***" in mask_kis_secrets_in_str(s)
    assert "eyJ0" not in mask_kis_secrets_in_str(s)


# ──────────────────────────────────────────────
# 2. _CachedToken.is_valid
# ──────────────────────────────────────────────


def test_cached_token_valid():
    now = time.time()
    t = _CachedToken(
        access_token="abc",
        issued_at=now - 100,
        expires_at=now + 3600,
        env="real",
        app_key_fingerprint="PSR6Wk",
    )
    assert t.is_valid("real", "PSR6WkhkNOJD0tEyfUkp7OZ7XtVCNhqdmfhP", now=now) is True


def test_cached_token_expired():
    now = time.time()
    t = _CachedToken(
        access_token="abc",
        issued_at=now - 86400,
        expires_at=now - 60,
        env="real",
        app_key_fingerprint="PSR6Wk",
    )
    assert t.is_valid("real", "PSR6WkhkNOJD0tEyfUkp7OZ7XtVCNhqdmfhP", now=now) is False


def test_cached_token_env_mismatch():
    now = time.time()
    t = _CachedToken(
        access_token="abc",
        issued_at=now,
        expires_at=now + 3600,
        env="paper",
        app_key_fingerprint="PSR6Wk",
    )
    # real 환경인데 캐시는 paper 토큰 → 무효
    assert t.is_valid("real", "PSR6WkhkNOJD0tEyfUkp7OZ7XtVCNhqdmfhP", now=now) is False


def test_cached_token_key_rotated():
    now = time.time()
    t = _CachedToken(
        access_token="abc",
        issued_at=now,
        expires_at=now + 3600,
        env="real",
        app_key_fingerprint="OLDKEY",
    )
    # app_key가 회전됨 → 무효
    assert t.is_valid("real", "PSR6WkhkNOJD0tEyfUkp7OZ7XtVCNhqdmfhP", now=now) is False


# ──────────────────────────────────────────────
# 3. KisClient 초기화 / env 분기
# ──────────────────────────────────────────────


def test_env_real(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KIS_ENV", "real")
    monkeypatch.setenv("KIS_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_APP_SECRET", "S" * 180)
    c = KisClient(token_cache_path=tmp_path / "tok.json", sleep_sec=0)
    assert c.env == "real"
    assert c.base_url == KIS_REAL_BASE


def test_env_paper(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("KIS_PAPER_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_PAPER_APP_SECRET", "S" * 180)
    c = KisClient(token_cache_path=tmp_path / "tok.json", sleep_sec=0)
    assert c.env == "paper"
    assert c.base_url == KIS_PAPER_BASE


def test_env_invalid(monkeypatch):
    monkeypatch.setenv("KIS_ENV", "invalid")
    with pytest.raises(ValueError, match="real|paper"):
        KisClient()


# ──────────────────────────────────────────────
# 4. get_access_token — 메모리/파일 캐시 + 신규 발급
# ──────────────────────────────────────────────


def _make_client(tmp_path: Path, monkeypatch) -> KisClient:
    monkeypatch.setenv("KIS_ENV", "real")
    monkeypatch.setenv("KIS_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_APP_SECRET", "S" * 180)
    http = MagicMock()
    return KisClient(
        token_cache_path=tmp_path / "tok.json",
        sleep_sec=0,
        http_client=http,
    )


def test_token_fresh_issue(tmp_path: Path, monkeypatch):
    c = _make_client(tmp_path, monkeypatch)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"access_token": "TOK_ABC", "expires_in": 86400}
    c._http.post.return_value = resp

    token = c.get_access_token()
    assert token == "TOK_ABC"
    assert c.stats.token_issues == 1
    assert c.stats.successful_calls == 1
    # 파일 캐시 저장 확인
    assert c._token_cache_path.exists()
    cached_data = json.loads(c._token_cache_path.read_text(encoding="utf-8"))
    assert cached_data["access_token"] == "TOK_ABC"
    assert cached_data["env"] == "real"


def test_token_memory_cache_hit(tmp_path: Path, monkeypatch):
    c = _make_client(tmp_path, monkeypatch)
    c._access_token = "MEM_TOK"
    c._token_expires_at = time.time() + 3600

    token = c.get_access_token()
    assert token == "MEM_TOK"
    assert c.stats.token_cache_hits == 1
    assert c.stats.token_issues == 0
    c._http.post.assert_not_called()


def test_token_file_cache_hit(tmp_path: Path, monkeypatch):
    c = _make_client(tmp_path, monkeypatch)
    # 파일 캐시 미리 작성
    now = time.time()
    c._token_cache_path.write_text(
        json.dumps(
            {
                "access_token": "FILE_TOK",
                "issued_at": now - 100,
                "expires_at": now + 3600,
                "env": "real",
                "app_key_fingerprint": c.app_key[:6],
            }
        ),
        encoding="utf-8",
    )

    token = c.get_access_token()
    assert token == "FILE_TOK"
    assert c.stats.token_cache_hits == 1
    assert c.stats.token_issues == 0
    c._http.post.assert_not_called()


def test_token_file_cache_expired_triggers_reissue(tmp_path: Path, monkeypatch):
    c = _make_client(tmp_path, monkeypatch)
    # 만료된 파일 캐시
    c._token_cache_path.write_text(
        json.dumps(
            {
                "access_token": "OLD_TOK",
                "issued_at": time.time() - 86400,
                "expires_at": time.time() - 60,
                "env": "real",
                "app_key_fingerprint": c.app_key[:6],
            }
        ),
        encoding="utf-8",
    )
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"access_token": "NEW_TOK", "expires_in": 86400}
    c._http.post.return_value = resp

    token = c.get_access_token()
    assert token == "NEW_TOK"
    assert c.stats.token_issues == 1


# ──────────────────────────────────────────────
# 5. 시세 호출
# ──────────────────────────────────────────────


def test_get_current_price_ok(tmp_path: Path, monkeypatch):
    c = _make_client(tmp_path, monkeypatch)
    c._access_token = "TOK"
    c._token_expires_at = time.time() + 3600

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "rt_cd": "0",
        "msg_cd": "MCA00000",
        "msg1": "정상",
        "output": {
            "stck_prpr": "73000",
            "prdy_vrss": "500",
            "prdy_ctrt": "0.69",
            "acml_vol": "10000000",
        },
    }
    c._http.get.return_value = resp

    out = c.get_current_price("5930")  # zfill 검증
    assert out["stck_prpr"] == "73000"
    # 호출 시 ticker 6자리 padding 확인
    args, kwargs = c._http.get.call_args
    assert kwargs["params"]["FID_INPUT_ISCD"] == "005930"
    assert kwargs["headers"]["tr_id"] == "FHKST01010100"


def test_get_current_price_rt_cd_fail(tmp_path: Path, monkeypatch):
    c = _make_client(tmp_path, monkeypatch)
    c._access_token = "TOK"
    c._token_expires_at = time.time() + 3600

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "rt_cd": "1",
        "msg_cd": "ERR",
        "msg1": "에러",
        "output": {},
    }
    c._http.get.return_value = resp

    out = c.get_current_price("005930")
    assert out == {}
    assert c.stats.failed_calls == 1


def test_get_daily_chart(tmp_path: Path, monkeypatch):
    c = _make_client(tmp_path, monkeypatch)
    c._access_token = "TOK"
    c._token_expires_at = time.time() + 3600

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "rt_cd": "0",
        "output1": {},
        "output2": [
            {"stck_bsop_date": "20260524", "stck_clpr": "73000", "acml_vol": "1000"},
            {"stck_bsop_date": "20260523", "stck_clpr": "72500", "acml_vol": "950"},
        ],
    }
    c._http.get.return_value = resp

    bars = c.get_daily_chart("005930", period="D")
    assert len(bars) == 2
    assert bars[0]["stck_bsop_date"] == "20260524"

    args, kwargs = c._http.get.call_args
    assert kwargs["headers"]["tr_id"] == "FHKST03010100"
    assert kwargs["params"]["FID_PERIOD_DIV_CODE"] == "D"
    assert kwargs["params"]["FID_ORG_ADJ_PRC"] == "0"  # 수정주가
    # 기본 날짜 자동 채움 검증
    assert kwargs["params"]["FID_INPUT_DATE_1"]
    assert kwargs["params"]["FID_INPUT_DATE_2"]
