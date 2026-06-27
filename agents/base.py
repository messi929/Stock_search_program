"""Axis 에이전트 공통 베이스.

모든 에이전트는 BaseAgent를 상속하여 다음을 공유합니다:
  - ClaudeClient (utils.claude_client)
  - 면책 문구 자동 삽입 (LEGAL.md)
  - 금지 단어 후처리 검증
  - JSON 응답 파싱 헬퍼
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Callable

from loguru import logger
from pydantic import BaseModel

from utils.claude_client import ClaudeClient


# ──────────────────────────────────────────────
# LEGAL: 면책 문구 — 모든 응답에 자동 삽입 (docs/axis/LEGAL.md)
# ──────────────────────────────────────────────

DISCLAIMER = (
    "📌 본 분석은 투자 권유가 아닌 정보 제공입니다.\n"
    "   최종 투자 판단은 사용자 본인의 책임입니다.\n"
    "   Axis는 자본시장법상 투자자문업 면허가 없으며,\n"
    "   특정 종목의 매매를 권유하지 않습니다."
)

# 응답 후처리 시 검출할 금지 패턴 — 정규식으로 한국어 활용형 커버.
# 발견되면 [필터링됨]으로 치환 + 로그.
#
# 각 항목: (정규식, 표시 라벨)
# 라벨은 logger.warning + scripts/legal_check.py 결과 출력용.
FORBIDDEN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # "추천" 활용형 (단, "비추천"·"非추천" 제외)
    (
        re.compile(
            r"(?<![비非])"
            r"추천(합니다|드립니다|드려요|해요|한다|됩니다|되었|되며|받|드린|받았|드림)"
        ),
        "추천",
    ),
    # 명령형 매매 권유
    (re.compile(r"사세요"), "사세요"),
    (re.compile(r"매수하세요"), "매수하세요"),
    (re.compile(r"매도하세요"), "매도하세요"),
    # 시그널 어구 — 한국어 "신호" + 영어 차용 "시그널" 양쪽 차단
    (re.compile(r"매수\s*(신호|시그널)"), "매수 신호"),
    (re.compile(r"매도\s*(신호|시그널)"), "매도 신호"),
    (re.compile(r"진입\s*(신호|시그널)"), "진입 신호"),
    # 유망 어구
    (re.compile(r"유망(합니다|한|주\b|할 것)"), "유망"),
    # 확정 어조 ("확실히 오릅" / "반드시 매수" / "분명히 수익" 등)
    (
        re.compile(r"(확실히|반드시|분명히)\s*(오릅|오를|상승|수익|매수|이익)"),
        "확정 어조",
    ),
    # 당위 어조
    (re.compile(r"(사야|팔아야)\s*(합니다|한다)"), "당위 어조"),
)


# 호환 유지 — 외부에서 FORBIDDEN_WORDS를 import하는 코드용 (단순 단어 리스트).
# 신규 코드는 FORBIDDEN_PATTERNS 사용 권장.
FORBIDDEN_WORDS: tuple[str, ...] = (
    "추천합니다", "추천드립니다", "추천드려요",
    "추천해요", "추천한다", "추천됩니다",
    "사세요", "매수하세요", "매도하세요",
    "매수 신호", "매도 신호", "진입 신호",
    "유망합니다", "유망주", "유망한",
    "사야 합니다", "팔아야 합니다",
    "사야 한다", "팔아야 한다",
)


# ──────────────────────────────────────────────
# JSON 파싱 헬퍼
# ──────────────────────────────────────────────

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> str:
    """Claude 응답에서 JSON 본체만 추출.

    처리 케이스:
      - ```json ... ``` 코드 블록
      - ``` ... ``` 일반 블록
      - JSON 앞뒤 공백/설명 텍스트
      - 그냥 raw JSON
    """
    text = text.strip()
    text = _JSON_FENCE_RE.sub("", text).strip()

    # 첫 { 부터 마지막 } 까지만 추출 (앞뒤 설명 컷)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text


# ──────────────────────────────────────────────
# Base Agent
# ──────────────────────────────────────────────

class BaseAgent(ABC):
    """모든 에이전트의 공통 베이스."""

    def __init__(
        self,
        agent_name: str,
        model: str,
        system_prompt: str,
        claude: ClaudeClient | None = None,
    ):
        self.agent_name = agent_name
        self.model = model
        self.system_prompt = system_prompt
        self.claude = claude or ClaudeClient()

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel:
        """에이전트 실행. 하위 클래스가 입출력 타입을 구체화."""
        raise NotImplementedError

    async def call_claude(
        self,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        uid: str = "",
        prefill: str | None = None,
        system: str | None = None,
        thinking_budget: int = 0,
        output_schema: type[BaseModel] | None = None,
        model: str | None = None,
    ) -> dict:
        """Claude 호출 헬퍼. system override로 페르소나별 동적 프롬프트 가능.

        thinking_budget>0이면 Extended Thinking 활성화 (복잡 추론 품질↑).
        output_schema 지정 시 구조화 출력(강제 tool use) — content가 유효 JSON 보장.
        model 지정 시 self.model 대신 해당 모델로 호출(한 에이전트가 단계별로
        Haiku/Sonnet을 섞어 쓰는 다단계 하네스용). 미지정이면 self.model.
        """
        messages: list[dict] = [{"role": "user", "content": user_message}]
        if prefill is not None:
            messages.append({"role": "assistant", "content": prefill})

        result = await self.claude.complete(
            agent=self.agent_name,
            model=model or self.model,
            system=system if system is not None else self.system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            uid=uid,
            thinking_budget=thinking_budget,
            output_schema=output_schema,
        )

        # prefill이 있으면 응답 앞에 prefill 복원
        if prefill is not None:
            result["content"] = prefill + result["content"]
        return result

    async def call_claude_json(
        self,
        user_message: str,
        schema: type[BaseModel],
        max_tokens: int = 4096,
        uid: str = "",
        max_retries: int = 1,
        system: str | None = None,
        completeness_check: Callable[[BaseModel], list[str]] | None = None,
        thinking_budget: int = 0,
        structured_output: bool = False,
        model: str | None = None,
    ) -> tuple[BaseModel, dict]:
        """Claude 호출 + JSON 파싱 + Pydantic 검증.

        Sonnet 4.6 등 일부 모델은 assistant prefill을 지원하지 않으므로,
        prefill 없이 user message에 강한 JSON 출력 지시를 추가하여 호환성 확보.
        extract_json()이 ```json 코드 블록과 raw JSON 모두 처리.

        structured_output:
            True면 schema를 그대로 tool로 만들어 호출을 강제(강제 tool use). 모델 출력이
            항상 유효한 JSON 객체로 보장돼 파싱/검증 실패가 사실상 0이 된다 — flaky한
            페르소나의 근본 안정화책. content는 tool_use.input을 직렬화한 JSON이라 아래
            파싱 경로(extract_json+json.loads)가 그대로 성공한다. 텍스트 JSON 지시문은
            불필요하므로 생략. completeness_check는 그대로 동작(내용 충실도 보강).

        completeness_check:
            Pydantic 검증 통과 후 실행되는 선택적 콜백. 비어있거나 누락된
            필수 필드명 리스트를 반환한다 (완전하면 빈 리스트).
            스키마가 Field(default_factory=...)를 쓰면 Claude가 필드를 통째로
            빠뜨려도 검증은 통과한다 — 그 경우 사용자에게 빈 카드가 노출되므로,
            이 콜백이 비어있으면 재시도를 1회 더 유발한다. 재시도 후에도
            누락이면 graceful하게 (default 채워진) 모델을 반환.

        Returns:
            (parsed_model, raw_result) — raw_result는 usage/cached 등 메타.
        """
        json_instruction = (
            "\n\n# JSON 출력 지시 (필수)\n"
            "반드시 `{` 로 시작하여 `}` 로 끝나는 단일 JSON 객체만 출력하세요. "
            "코드 블록 펜스(```json) 금지, 설명 텍스트 금지, JSON 외 문자 절대 금지."
        )

        # 구조화 출력이면 tool 스키마가 형식을 강제하므로 텍스트 JSON 지시문 불필요.
        message = user_message if structured_output else user_message + json_instruction
        schema_for_call = schema if structured_output else None
        last_err: Exception | None = None
        for attempt in range(max_retries + 1):
            result = await self.call_claude(
                user_message=message,
                max_tokens=max_tokens,
                uid=uid,
                prefill=None,
                system=system,
                thinking_budget=thinking_budget,
                output_schema=schema_for_call,
                model=model,
            )
            json_str = extract_json(result["content"])

            # 1차: 표준 json
            data = None
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                # 2차: json-repair (LLM 응답에 흔한 escape 누락/trailing comma 복구)
                try:
                    from json_repair import repair_json
                    repaired = repair_json(json_str)
                    data = json.loads(repaired)
                    logger.info(f"[{self.agent_name}] json-repair 복구 성공")
                except Exception as repair_err:
                    last_err = e
                    logger.warning(
                        f"[{self.agent_name}] JSON 파싱 실패 (시도 {attempt + 1}/{max_retries + 1}): "
                        f"json={e} / repair={repair_err}"
                    )
                    if attempt < max_retries:
                        message = (
                            f"{message}\n\n"
                            f"⚠️ 직전 응답 JSON 파싱 실패. 모든 string value 내부의 큰 따옴표는 \\\", "
                            f"줄바꿈은 \\n으로 escape하세요. {schema.__name__} 스키마에 정확히 맞춘 JSON만 출력."
                        )
                    continue

            try:
                model = schema.model_validate(data)
            except ValueError as e:
                last_err = e
                logger.warning(f"[{self.agent_name}] Pydantic 검증 실패: {e}")
                if attempt < max_retries:
                    message = (
                        f"{message}\n\n"
                        f"⚠️ 스키마 검증 실패: {e}. {schema.__name__} 정확히 따라 재출력."
                    )
                continue

            # 검증 통과 — 완전성 체크 (default_factory로 빈 필드가 통과하는 문제 보완)
            if completeness_check is not None:
                missing = completeness_check(model)
                if missing and attempt < max_retries:
                    logger.warning(
                        f"[{self.agent_name}] 필수 필드 누락 {missing} — "
                        f"재요청 (시도 {attempt + 1}/{max_retries + 1})"
                    )
                    message = (
                        f"{message}\n\n"
                        f"⚠️ 직전 응답에서 다음 필수 필드가 비어있거나 누락됨: "
                        f"{', '.join(missing)}. {schema.__name__} 스키마의 모든 필드를 "
                        f"빠짐없이 채워 재출력하세요. 위 필드는 절대 생략 금지."
                    )
                    continue
                if missing:
                    logger.warning(
                        f"[{self.agent_name}] 재시도 후에도 필수 필드 누락 {missing} "
                        f"— graceful 반환"
                    )
            return model, result
        raise ValueError(f"[{self.agent_name}] JSON 파싱 재시도 후에도 실패: {last_err}")

    @staticmethod
    def append_disclaimer(text: str) -> str:
        """응답 끝에 면책 문구 삽입."""
        return f"{text.rstrip()}\n\n{DISCLAIMER}"

    @staticmethod
    def filter_forbidden(text: str) -> tuple[str, list[str]]:
        """금지 패턴 검출 + 치환. (필터링된 텍스트, 발견된 라벨 리스트) 반환.

        정규식 기반 — 한국어 활용형 커버. 매칭된 부분 전체를 [필터링됨]으로 치환.
        """
        found: list[str] = []
        for pattern, label in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                found.append(label)
                text = pattern.sub("[필터링됨]", text)
        return text, found
