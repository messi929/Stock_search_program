"""pytest 공통 설정 — integration 마커 opt-in.

기본(pytest tests/)은 단위 테스트만 실행 — `@pytest.mark.integration` 테스트는 자동 skip.
실 외부 API 검증은 `pytest --run-integration` 추가 시에만 실행 (비용 발생).
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="실 Claude API + Firestore 호출이 필요한 통합 테스트 실행 (비용 발생)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return  # 통합 테스트도 모두 실행
    skip_integration = pytest.mark.skip(
        reason="실 API 의존 — `pytest --run-integration` 추가 필요"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
