"""마케팅 콘텐츠 생성기 — 스레드(Threads)용 종목 글 자동 초안.

4단계 하네스 (JEON 결정 2026-06-27, best-of-3):
  ① 앵글 파인더 (Haiku)  — 스냅샷에서 '단 하나의 긴장/모순/관점'을 뽑는다.
                            숫자 나열 병의 근본 치료. so-what을 먼저 고정.
  ② 작가 best-of-N (Sonnet) — 앵글 + 독자우선 프롬프트로 후보 N개 동시 생성.
  ③ 편집/심판 (Sonnet+thinking) — 루브릭 6축 채점 → 최고 후보를 골라 약점까지
                            고쳐 최종본 출력. (작가와 system 분리 = 고무도장 방지)
  ④ 결정론적 가드 (LLM 무관) — 법적 필터 + 자기언급/내부용어 가드 + 길이/숫자 재확인.

품질 원칙 (JEON 피드백 2026-06-27):
  - 실수치를 숫자 그대로 인용(≥2개). 숫자 없는 두루뭉술 차단.
  - **글의 주어는 독자의 관심사지 우리 서비스가 아니다.** 'Axis는~', '스냅샷 기준',
    '검증까지가 기본' 같은 자기언급·내부용어·셀링멘트 전면 금지(③+④ 이중 방어).
  - "AI한테 물어봤더니" 류 프레이밍 금지 — 글의 주어는 'AI'가 아니라 '수치'.
  - 브랜드 POV: 펌핑하지 않는다. 양쪽을 냉정하게 본다.

0→1 마케팅 목적. 관리자가 콘솔에서 검수·수정 후 복사(또는 자동 발행)한다.

LEGAL: 추천/매수·매도/목표가/매수가/손절가 절대 금지. 관찰·참고·중립 해석만.
면책은 계정 프로필(bio)에 상시 고지하므로 본문에는 넣지 않는다(JEON 결정 2026-06-27).
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.instant import build_instant_snapshot, resolve_ticker, _snapshot_facts
from utils.claude_client import MODEL_HAIKU, MODEL_SONNET

# 마케팅 글 = 서비스의 얼굴 → 품질 우선 기본 Sonnet. 비용 절감 시 MARKETER_MODEL=haiku.
MARKETER_MODEL = MODEL_HAIKU if os.getenv("MARKETER_MODEL", "").lower() == "haiku" else MODEL_SONNET
# 앵글 파인더는 항상 저비용 Haiku(긴장 1개 추출은 가벼운 작업).
ANGLE_MODEL = MODEL_HAIKU

# best-of-N: 작가가 동시에 만들 후보 수. 편집 단계가 최고를 골라 다듬는다.
WRITER_CANDIDATES = max(1, int(os.getenv("MARKETER_CANDIDATES", "3") or "3"))

# 헛글 방지 가드: 글에 인용할 실수치가 이만큼 미만이면 생성 자체를 건너뛴다.
MIN_NUMERIC_FACTS = 2

THREADS_MAX = 500  # Threads 글자 수 제한
# 면책은 본문이 아니라 계정 프로필(bio)에 상시 고지한다(JEON 결정 2026-06-27).


# ──────────────────────────────────────────────
# 포맷 정의 — 0→1 콘텐츠 엔진
# 'trust'(데이터 검증) 포맷은 폐기됨(JEON 결정 2026-06-27): 훅이 본문을 부정하고
# 정적 SNS 글로 '스냅샷은 낡는다'를 주장하는 자기모순 + '신선도'는 약한 차별점.
# 포맷 guide는 ③ 작가 단계의 '톤/강조점' 힌트일 뿐, 긴장 추출은 ① 앵글이 담당.
# ──────────────────────────────────────────────

FORMATS: dict[str, dict[str, str]] = {
    "contrarian": {
        "label": "양쪽관점 (반대로 보면)",
        "guide": (
            "메인 포맷. '다들 좋다는데, 숫자로 보면 이런 약점도' 톤. 강세 서사에 대한 "
            "냉정한 반대 수치(과열·고평가·수급 피로)를 **숫자를 짚어가며** 제시한다. "
            "펌핑판에서 독자를 손실에서 구하는 게 목적 — 공포조장·단정 금지, "
            "중립 프레이밍('이 수치는 관찰이 필요')."
        ),
    },
    "curiosity": {
        "label": "호기심 (모순 수치)",
        "guide": (
            "서로 충돌하거나 의외인 수치 조합을 **숫자 그대로** 던지며 시작한다. "
            "예: '거래량이 평소의 3.1배 터졌다. 그런데 외국인은 5일째 순매도.' "
            "그 모순 자체로 호기심을 남기고 마무리한다 — 억지 결론·홍보 멘트로 닫지 말 것."
        ),
    },
    "cta": {
        "label": "댓글 모집 (종목 남겨주세요)",
        "guide": (
            "이 종목의 가장 후킹되는 수치 하나를 짧게 던진 뒤, '궁금한 종목 댓글로 "
            "남겨주시면 강점·약점 수치를 양쪽 다 정리해 드린다'고 초대한다. "
            "추천이 아니라 '판단용 자료 제공'임을 분명히. 댓글을 부르는 한 문장으로 마무리."
        ),
    },
    "technical": {
        "label": "차트 기술 관점 (가격대)",
        "guide": (
            "이 종목의 '차트/기술 신호'를 **구체적 가격(원/달러)으로** 읽는다. facts의 "
            "'## 기술적 분석'에 있는 현재가·이동평균선 가격(20일선/60일선)·52주 고가/저가를 "
            "**숫자 그대로 짚으며**, 추세(정배열·골든/데드크로스)·거래량·변동성이 지금 어떤 "
            "국면인지 관찰한다. 이격 %만 말하지 말고 '20일선 OO원' 식 실제 가격을 함께 쓴다. "
            "예: '현재 195,000원, 20일선 189,000원 위. 52주 고가 210,000원까지 -7%, "
            "거래량은 식어가는 중.' "
            "⚠️ 절대 금지: 목표가·매수가·손절가 등 '가격 처방'과 '여기서 사라/팔라'. 관찰된 "
            "가격 '수준'만 중립 사실로('189,000원이 가까운 지지/저항으로 관찰' 식). "
            "결론(사라/팔라)은 빼되 '차트가 지금 어디에 서 있나'를 또렷이 남긴다."
        ),
    },
}

DEFAULT_FORMATS = ("contrarian", "curiosity", "cta", "technical")


# ──────────────────────────────────────────────
# 시스템 프롬프트 (단계별 역할 분리)
# ──────────────────────────────────────────────

# 작가·편집이 공유하는 불변 규칙(법적·구체성·독자시점). 두 system 앞에 붙인다.
_CORE_RULES = """# 1순위 — 구체성 (어기면 글은 폐기)
- 스냅샷의 **실제 숫자를 최소 2개 이상 그대로 인용**한다.
  예: "RSI 72", "외국인 8일 연속 순매수", "거래량 평소의 2.3배", "PER 14.1", "52주 고가 대비 -8%"
- 숫자에는 의미를 붙인다. 예: "RSI 72 — 과열권", "PER 14는 업종 평균보다 낮은 편"
- 금지된 헛소리: "뭔가 움직임이 있다", "심상치 않다", "관찰할 만한 수치들" 등 숫자 없는 두루뭉술.

# 날짜 표기 (중요 — 발행이 생성 당일이 아닐 수 있음)
- 등락·수급 등 '시점 있는' 수치에 **"오늘/금일/지금/현재/오늘자"** 같은 상대 표현 절대 금지.
  발행이 며칠 뒤일 수 있어 '오늘'은 거짓이 된다.
- 주어진 기준일이 있으면 그 날짜로 쓴다. 예: "삼성전자, 6월 26일 -5.3%", "6월 26일 종가 기준 RSI 49".
  날짜는 글에 한 번만 밝히면 충분(매 문장 반복 금지).
- 기준일이 주어지지 않으면 시점어 없이 수치만 제시한다. 예: "삼성전자 -5.3%, 외국인 7일 연속 순매수".

# 2순위 — 독자 시점 (가장 자주 어기는 규칙)
- **글의 주어는 '독자의 관심사'다. '우리 서비스'가 아니다.**
- 절대 금지(자기언급·홍보): "Axis는~", "우리는~", "이 도구/서비스는~",
  "~에서 끝내지 않는다", "검증까지가 기본", "~를 제공한다" 등 서비스 자랑 문장.
- 절대 금지(내부 용어): "스냅샷", "오늘 스냅샷 기준", "데이터 기준", "~ 구간에 있다"(번역투).
  독자는 '스냅샷'이 뭔지 모른다. 그냥 "삼성전자 오늘 -5.3%"라고 쓴다.
- 절대 금지(AI 프레이밍): "AI한테 물어봤더니 / AI가 분석했더니". 글의 주어는 '수치'다.
- 광고/챗봇 말투·과장 금지. 사람이 직접 차트 보며 쓴 듯 담백하게.

# 3순위 — 관점(so-what)
- 숫자를 나열하지 말고 **하나의 긴장(모순·의외·관점)으로 수렴**시킨다.
- 브랜드 톤: 펌핑하지 않는다. 양쪽을 냉정하게 본다.

# 마무리 — '앞으로 볼 것'(필수, 이 글의 페이로드)
- 긴장만 끌어올리고 결론 없이 끝내지 말 것. 그게 호응이 죽는 가장 큰 원인이다.
  독자가 "그래서 앞으로 뭘 보면 되나"의 **답(방향)**을 가져가게 한다.
- watchpoints에 **'앞으로 볼 것' 관찰 포인트 1~3개**를 담는다. 각 항목은 조건부·관찰형:
  · 수급/추세 조건 — "외국인 순매수가 10일 넘게 이어지는지", "거래량이 다시 평균을 넘는지"
  · 가격 관찰 수준(지지/저항) — "68,000원(60일선)이 지지로 유지되는지" (관찰 수준이지 매수가 아님)
  · 이벤트/실적 조건 — "다음 실적에서 메모리 가격 피크 신호가 나오는지"
- 이 블록이 곧 '방향성'이다 — 결론(사라/팔라)을 강요하지 않으면서 독자에게 '다음 행동의 기준'을 준다.
- ⚠️ 절대 금지: "여기서 사라/담아라/익절", 목표가·매수가·손절가, "오른다/내린다" 단정.
  방향은 오직 '무엇을 관찰하면 갈림길이 보이나'로만 — 가격은 '관찰 지지/저항 수준'으로.

# 기술적 분석 활용
- facts에 '## 기술적 분석' 섹션(이동평균 정배열·골든/데드크로스·거래량 추세·매집·변동성 등)이
  있으면 적극 활용한다. PER/PBR 같은 밸류 한 줄보다 추세·수급·거래량의 '움직임'이 더 후킹된다.
- 단, 기술 용어를 '매수 신호/시그널'로 번역하지 말 것. "골든크로스 발생"은 사실 관찰로 쓰고
  단정(오른다)으로 잇지 않는다.

# 경기민감(사이클) 종목 — 단일 PER 함정 (반도체·화학·철강·정유·조선·해운 등)
- facts에 '## 사이클 주의' 섹션이 있으면 반드시 반영한다.
- 이런 업종은 이익이 크게 출렁여 단일 PER/PBR이 신호를 거꾸로 준다:
  호황 이익 피크엔 PER이 낮게(저평가 착시), 불황 바닥엔 높게 보인다.
- 따라서 "PER 9, 싸다" 식 단정 금지. "PER은 낮지만, 이게 이익 피크라면 얘기가 다르다"처럼
  **사이클 위치를 함께 묻는 관점**을 남긴다. 이게 펌핑판에서 독자를 구하는 핵심 긴장이 된다.

# 법적 안전 (어기면 서비스가 위법)
- 금지: 추천/추천합니다, 사세요, 매수·매도, 매수가/목표가/손절가 등 가격 제시,
  "매수 신호/시그널", "반드시·확실히 오른다", "유망주" 등 권유·단정
- 허용: 수치의 중립적 해석, '관찰', '참고', '현재 ~', 질문형
- 종목명은 주어진 것만 사용(추정·창작 금지)
- 핵심: '추천하지 마라' ≠ '아무 말도 하지 마라' — 숫자는 구체적으로, 결론(사라/팔라)만 빼라.

# 문체
- 짧은 문장, 줄바꿈, 이모지 0~3개. 표/마크다운 금지.
- hook(첫 문장)은 가장 강한 수치/긴장 하나로 시작. body는 **3~5줄로 짧게**, hashtags 2~4개(한국어, # 제외).

# 길이 예산 (필수 — 어기면 발행 불가)
- **hook + body + '앞으로 볼 것'(1~3개) + 해시태그를 모두 합쳐 480자 이내**(Threads 500자 한도).
- 페이로드는 '앞으로 볼 것'이다 → body는 긴장 제시까지만 짧게 쓰고, 결론·전망 설명은
  watchpoints로 넘긴다. body가 길면 줄을 쳐내서라도 480자를 지킨다.
- 길이가 빠듯하면 watchpoints를 2개로 줄이고 각 항목을 더 압축한다(개수보다 길이 준수 우선).
- 면책은 본문에 넣지 않는다(프로필 bio 상시 고지)."""

# 앵글 아키타입 — '충돌형' 단일 재배 탈피(point 2). 앵글 파인더가 종목 데이터에
# 가장 맞는 유형 하나를 고른다. key = 출력/추적용 라벨, value = 선택 가이드.
ANGLE_ARCHETYPES: dict[str, str] = {
    "충돌": "서로 어긋나는 두 수치(가격↓ vs 수급↑, RSI 과열 vs 외국인 이탈, 정배열 vs 거래량 감소).",
    "사이클위치": "경기민감 업종에서 PER/이익의 사이클 위치가 주는 함정. '## 사이클 주의'가 있으면 1순위 후보.",
    "추세변곡": "골든/데드크로스·정배열·이평수렴·이격 등 기술 추세의 전환 또는 임박.",
    "수급반전": "외국인 연속 순매수/순매도의 지속·전환, 매집(거래량↑·가격안정) 신호의 의미.",
    "단일충격": "한 개의 극단 수치(거래량 N배, 52주 저가 대비 +X%, N일 연속 상승)로 스크롤을 멈춘다.",
    "과열피로": "RSI 과열·신고가 근접·연속 상승의 피로/되돌림 가능성을 냉정히 관찰.",
}
ARCHETYPE_KEYS: tuple[str, ...] = tuple(ANGLE_ARCHETYPES.keys())

_ARCHETYPE_MENU = "\n".join(f"  · {k}: {v}" for k, v in ANGLE_ARCHETYPES.items())

_ANGLE_SYSTEM = f"""당신은 주식 SNS 글의 '편집 앵글'을 잡는 에디터입니다.
주어진 종목 수치에서, 독자가 스크롤을 멈출 만한 '단 하나의 긴장'을 찾아냅니다.

# 앵글 유형(아키타입) — 이 종목 데이터가 가장 강하게 떠받치는 '한 가지'를 고른다
{_ARCHETYPE_MENU}

선택 원칙:
- **'충돌'로 기계적으로 수렴시키지 말 것.** 데이터가 가장 선명하게 받쳐주는 유형을 고른다.
  정배열·크로스가 뚜렷하면 '추세변곡', 거래량/연속상승이 극단이면 '단일충격',
  '## 사이클 주의'가 있으면 '사이클위치'를 우선 고려한다.
- 여러 유형이 가능하면, '최근 이미 많이 쓴 유형'을 피해 다양성을 확보한다(아래 입력 참고).

원칙:
- 숫자 나열 금지. 고른 아키타입에 맞는 '하나의 이야기'를 뽑는다.
- '## 기술적 분석' 섹션(정배열·골든/데드크로스·거래량 추세·매집·변동성)이 있으면 그 신호를
  밸류(PER/PBR)와 엮어 긴장을 만든다 — 움직임이 정적 밸류보다 강한 훅이 된다.
- '## 사이클 주의' 섹션이 있으면 그것을 긴장으로 적극 활용한다.
  예: "PER은 9로 싸 보이는데, 반도체 이익이 피크라면 그 싼 PER이 함정일 수 있다".
- archetype: 위 6종 중 고른 유형의 라벨(예: '추세변곡')을 그대로 적는다.
- tension: 그 긴장을 한 문장으로(독자가 읽을 문장이 아니라, 작가에게 줄 방향).
- key_numbers: 그 긴장을 떠받치는, 의미를 붙일 수 있는 숫자 2~3개만.
- avoid: 긴장과 무관하거나 값이 의심스러워 빼야 할 수치(예: 비정상적으로 높은 PER).
- 추천/매수·매도/가격 언급 금지. 관찰·관점만.
- tension에 '오늘/지금/현재' 같은 상대 시점어 금지(발행이 며칠 뒤일 수 있음). 날짜가 필요하면 주어진 기준일을 쓴다."""

_WRITER_SYSTEM = (
    "당신은 한국/미국 주식 정보 서비스의 SNS(스레드) 카피라이터입니다.\n"
    "주어진 '편집 앵글'과 실제 수치로, 스크롤을 멈추게 하는 짧고 구체적인 한국어 스레드 글을 씁니다.\n\n"
    + _CORE_RULES
)

_EDITOR_SYSTEM = (
    "당신은 SNS 카피의 냉정한 편집장입니다. 후보 글들을 루브릭으로 채점하고,\n"
    "가장 나은 후보를 베이스로 골라 약점까지 고쳐 '최종본 한 편'을 만듭니다.\n\n"
    "# 루브릭 (각 0~5, 합산 0~35)\n"
    "1. 후킹: 첫 줄이 스크롤을 멈추게 하나\n"
    "2. 긴장/관점: 숫자가 흩어지지 않고 '하나의 긴장'으로 수렴하나 (so-what)\n"
    "3. 구체성: 의미 부여된 숫자가 2개 이상인가\n"
    "4. 독자시점: 자기언급(Axis/우리)·내부용어(스냅샷)·셀링멘트가 0인가  ← 가장 중요\n"
    "5. 담백함: 광고티·군더더기·챗봇 말투가 없나\n"
    "6. 법적안전: 추천·가격제시(목표가/매수가/손절가)·단정이 없나\n"
    "7. 방향성(앞으로 볼 것): watchpoints가 1~3개 채워졌고, 조건부·관찰형이며 '다음에 무엇을 "
    "보면 갈림길이 보이나'의 답을 주나. 긴장만 남기고 끝나면 0점.  ← 호응의 핵심\n\n"
    "# 출력\n"
    "- 최고 후보를 베이스로 하되, 위 7축에서 깎인 점을 직접 고쳐 최종본을 낸다.\n"
    "- 4축 위반(자기언급·내부용어·셀링멘트)은 문장째 들어내고 독자 관심사로 대체한다.\n"
    "- 7축: 후보의 watchpoints가 약하거나 비었으면 facts/앵글에서 직접 1~3개를 만들어 채운다.\n"
    "  단 매수가/목표가/손절가·'사라/팔라'로 새지 않게(가격은 '관찰 지지/저항 수준'으로).\n"
    "  watchpoints 각 항목은 35자 내외로 간결히.\n"
    "- 길이(필수): hook+body+watchpoints+해시태그 합산 480자 이내. 넘치면 body를 줄이고\n"
    "  watchpoints를 2개로 압축해서라도 맞춘다(발행 한도 500자).\n"
    "- score_total은 '최종본' 기준 점수. issues_fixed에 고친 문제를 간단히 적는다.\n\n"
    + _CORE_RULES
)


# ──────────────────────────────────────────────
# 스키마
# ──────────────────────────────────────────────

class PostAngle(BaseModel):
    """① 앵글 파인더 출력 — 글 한 편의 '단 하나의 긴장'."""

    archetype: str = Field(
        default="", description="고른 앵글 유형 라벨(충돌/사이클위치/추세변곡/수급반전/단일충격/과열피로)"
    )
    tension: str = Field(description="이 종목의 단 하나의 긴장/모순/관점 (작가에게 줄 방향, 한 문장)")
    key_numbers: list[str] = Field(
        default_factory=list, description="긴장을 떠받치는 의미부여된 숫자 2~3개"
    )
    avoid: list[str] = Field(
        default_factory=list, description="넣지 말 것 (긴장과 무관/의심스러운 수치)"
    )


_WATCHPOINTS_DESC = (
    "앞으로 볼 관찰 포인트 1~3개(필수). **각 항목 35자 내외로 간결하게**(긴 괄호 부연 금지). "
    "조건부·관찰형만 — 수급/추세 조건, 가격 관찰 수준(지지/저항), 실적/이벤트 조건. "
    "예: '외국인 순매수 10일 돌파 여부', '60일선 68,000원 지지 유지'. "
    "⚠️ 매수가/목표가/손절가·'사라/팔라' 금지."
)


class ThreadsPost(BaseModel):
    """스레드 글 구조화 출력 (작가 단계)."""

    hook: str = Field(description="첫 문장 한 줄 — 스크롤을 멈추게 하는 후킹")
    body: str = Field(description="본문 3~6줄. 줄바꿈 포함. 수치 중립 해석")
    watchpoints: list[str] = Field(description=_WATCHPOINTS_DESC)  # 필수(구조화 스키마 required)
    hashtags: list[str] = Field(
        default_factory=list, description="해시태그 키워드 2~4개 (# 제외, 한국어)"
    )


class EditedPost(BaseModel):
    """③ 편집/심판 출력 — 최종본 + 메타."""

    hook: str = Field(description="최종 첫 문장")
    body: str = Field(description="최종 본문 3~6줄")
    watchpoints: list[str] = Field(description=_WATCHPOINTS_DESC)  # 필수(구조화 스키마 required)
    hashtags: list[str] = Field(default_factory=list, description="해시태그 2~4개 (# 제외)")
    score_total: int = Field(default=0, description="루브릭 7축 합산 점수(0~35, 최종본 기준)")
    issues_fixed: list[str] = Field(default_factory=list, description="고친 문제들")
    base_candidate: int = Field(default=0, description="베이스로 고른 후보 번호(0-based)")


# ──────────────────────────────────────────────
# 결정론적 가드 — 자기언급/내부용어/셀링멘트 (④)
# 법적 필터(BaseAgent.filter_forbidden)와 별개. 걸리면 1회 재편집 유발 후
# 남으면 admin 콘솔에 warnings로 노출(human-in-loop이므로 본문 강제훼손 X).
# ──────────────────────────────────────────────

_READER_FIRST_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # 한국어는 조사가 브랜드명에 바로 붙어("Axis는") \b 끝경계가 깨지므로 경계 없이 매칭.
    (re.compile(r"Axis|액시스", re.IGNORECASE), "자기언급(Axis)"),
    (re.compile(r"우리(는|가|의|\s)"), "자기언급(우리)"),
    (re.compile(r"이\s*(도구|서비스|앱|플랫폼)"), "자기언급(서비스)"),
    (re.compile(r"스냅샷"), "내부용어(스냅샷)"),
    (re.compile(r"데이터\s*기준"), "내부용어(데이터 기준)"),
    # "~에서/데서 끝내지 않는다" 류 셀링 상투구 — 앞 어미 강제 없이 광범위 매칭.
    (re.compile(r"(끝내지|그치지|멈추지)\s*않"), "셀링멘트(끝내지 않)"),
    (re.compile(r"검증까지"), "셀링멘트(검증까지)"),
    (re.compile(r"구간에\s*있다"), "번역투(구간에 있다)"),
)


def guard_reader_first(text: str) -> list[str]:
    """자기언급·내부용어·셀링멘트 검출. 발견된 라벨 리스트(비면 통과)."""
    return [label for pat, label in _READER_FIRST_PATTERNS if pat.search(text)]


def _numeric_fact_count(s: dict) -> int:
    """스냅샷에서 글에 인용 가능한 '실제 수치' 개수. 헛글 가드용."""
    keys = (
        "price", "change_pct", "rsi", "per", "pbr", "roe",
        "vs_high_52w", "vs_low_52w", "foreign_consecutive", "volume_ratio",
        # 기술 지표(1a) — 밸류 결손 종목도 기술 신호로 글을 쓸 수 있게 가드 완화.
        "vs_ma20_pct", "vs_ma60_pct", "consecutive_gains", "volume_trend",
        "volatility_20d",
    )
    n = 0
    for k in keys:
        v = s.get(k)
        if v is None:
            continue
        try:
            if float(v) != 0.0:
                n += 1
        except (TypeError, ValueError):
            continue
    return n


def _as_of_label(snapshot: dict) -> str:
    """스냅샷 데이터의 기준일 라벨('M월 D일'). updated_at 파싱 실패 시 빈 문자열.

    updated_at은 종목 행의 데이터 갱신 시각으로, 수집기가 **KST**로 저장한다(naive).
      - KR: 장마감(17:30 KST) 직후 캡처 → 그 거래일과 일치 → KST 날짜 그대로.
      - US: 미 동부 장마감 후 = 한국 새벽 캡처 → KST 날짜는 현지 세션일보다 하루 앞섬.
        America/New_York로 변환해 실제 세션일을 쓰고 '(현지)'를 붙여 혼동 방지.
    '오늘' 대신 이 일자로 표기해 발행 지연 시에도 정확하게.
    """
    raw = (snapshot or {}).get("updated_at") or ""
    if not raw:
        return ""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        kst = ZoneInfo("Asia/Seoul")
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=kst)  # naive updated_at은 KST로 간주
        if snapshot.get("is_kr"):
            d = dt.astimezone(kst)
            return f"{d.month}월 {d.day}일"
        # US: 동부 세션일로 보정 + '(현지)' 표기
        d = dt.astimezone(ZoneInfo("America/New_York"))
        return f"{d.month}월 {d.day}일(현지)"
    except Exception:
        return ""


def _date_note(as_of: str) -> str:
    """기준일 지시문 — 작가/앵글/편집 입력에 동봉해 '오늘' 대신 일자로 쓰게 한다."""
    if as_of:
        return (
            f"# 기준일 (필수)\n이 수치는 {as_of} 종가 기준이다. 등락·수급 등 시점 있는 수치는 "
            f"'오늘/지금/현재'가 아니라 '{as_of}'로 표기하라(한 번만)."
        )
    return (
        "# 기준일\n기준일 정보가 없다. 등락·수급에 '오늘/지금/현재' 등 시점어를 쓰지 말고 "
        "수치만 제시하라."
    )


def _angle_brief(angle: PostAngle) -> str:
    """앵글 → 작가/편집 입력용 한국어 브리핑."""
    head = "# 편집 앵글(이 긴장 하나로 글을 수렴시켜라)"
    if angle.archetype:
        head += f" [유형: {angle.archetype}]"
    parts = [f"{head}\n{angle.tension.strip()}"]
    if angle.key_numbers:
        parts.append("핵심 숫자(이걸 의미와 함께 써라): " + ", ".join(angle.key_numbers))
    if angle.avoid:
        parts.append("쓰지 말 것: " + ", ".join(angle.avoid))
    return "\n".join(parts)


# best-of-N 다양성: 후보마다 다른 도입 스타일 시드.
_STYLE_SEEDS = (
    "수치 충돌을 첫 줄에 한 방으로 던지는 직설형.",
    "짧은 장면/관찰로 담담하게 시작하는 서술형.",
    "독자에게 질문을 던져 끌어들이는 도발형.",
)


class MarketerAgent(BaseAgent):
    """스레드 글 생성기 — 4단계 하네스(앵글→작가 best-of-N→편집→가드)."""

    def __init__(self, claude=None):
        super().__init__(
            agent_name="marketer",
            model=MARKETER_MODEL,  # 작가·편집 기본 모델(앵글은 ANGLE_MODEL로 오버라이드)
            system_prompt=_WRITER_SYSTEM,
            claude=claude,
        )

    async def run(self, input_data: BaseModel) -> BaseModel:  # noqa: D401
        """BaseAgent 추상 메서드 충족용 — 실제 진입점은 generate()."""
        raise NotImplementedError("MarketerAgent은 generate()를 사용하세요")

    # ── ① 앵글 ─────────────────────────────
    async def _find_angle(
        self,
        facts: str,
        fmt: str,
        name: str,
        uid: str,
        avoid_archetypes: Optional[list[str]] = None,
    ) -> Optional[PostAngle]:
        guide = FORMATS[fmt]["guide"]
        avoid_line = ""
        if avoid_archetypes:
            avoid_line = (
                f"\n\n# 최근 이미 많이 쓴 앵글 유형(가능하면 피해 다양성 확보)\n"
                f"{', '.join(avoid_archetypes)} — 데이터가 다른 유형도 받쳐주면 그쪽을 골라라."
            )
        user_msg = (
            f"{facts}\n\n# 글 포맷(톤 힌트)\n{guide}{avoid_line}\n\n"
            f"위 수치에서 '{name}' 글 한 편의 단 하나의 긴장을 잡아라. "
            f"포맷 톤에 맞는 긴장으로."
        )
        try:
            angle, _ = await self.call_claude_json(
                user_message=user_msg,
                schema=PostAngle,
                system=_ANGLE_SYSTEM,
                model=ANGLE_MODEL,
                max_tokens=500,
                uid=uid,
                structured_output=True,
            )
            return angle
        except Exception as e:
            logger.warning(f"[marketer] 앵글 실패 {name}/{fmt}: {e} — 앵글 없이 진행")
            return None

    # ── ② 작가 (best-of-N) ─────────────────
    async def _write_one(
        self, facts: str, angle_brief: str, fmt: str, name: str, seed: str, uid: str
    ) -> Optional[ThreadsPost]:
        guide = FORMATS[fmt]["guide"]
        user_msg = (
            f"{facts}\n\n{angle_brief}\n\n# 글 포맷\n{guide}\n\n"
            f"# 이 후보의 스타일\n{seed}\n\n"
            f"위 앵글과 포맷에 맞춰 스레드 글 한 편을 작성하라. 종목명은 '{name}'만 사용."
        )
        try:
            post, _ = await self.call_claude_json(
                user_message=user_msg,
                schema=ThreadsPost,
                max_tokens=700,
                uid=uid,
                structured_output=True,
            )
            return post
        except Exception as e:
            logger.warning(f"[marketer] 작가 후보 실패 {name}/{fmt}: {e}")
            return None

    async def _write_candidates(
        self, facts: str, angle_brief: str, fmt: str, name: str, uid: str
    ) -> list[ThreadsPost]:
        seeds = [_STYLE_SEEDS[i % len(_STYLE_SEEDS)] for i in range(WRITER_CANDIDATES)]
        results = await asyncio.gather(
            *(self._write_one(facts, angle_brief, fmt, name, s, uid) for s in seeds),
            return_exceptions=True,
        )
        out: list[ThreadsPost] = []
        for r in results:
            if isinstance(r, ThreadsPost):
                out.append(r)
            elif isinstance(r, Exception):
                logger.warning(f"[marketer] 후보 예외: {r}")
        return out

    # ── ③ 편집/심판 ────────────────────────
    async def _edit_and_pick(
        self,
        candidates: list[ThreadsPost],
        facts: str,
        angle_brief: str,
        fmt: str,
        name: str,
        uid: str,
        repair_note: str = "",
    ) -> Optional[EditedPost]:
        listing = "\n\n".join(
            f"## 후보 {i}\n{assemble_post(c)}" for i, c in enumerate(candidates)
        )
        user_msg = (
            f"{facts}\n\n{angle_brief}\n\n"
            f"# 포맷\n{FORMATS[fmt]['guide']}\n\n"
            f"# 후보 글 ({len(candidates)}개)\n{listing}\n\n"
            f"위 후보들을 루브릭으로 채점하고, 최고를 베이스로 골라 약점까지 고쳐 "
            f"'{name}' 최종본 한 편을 출력하라. 종목명은 '{name}'만 사용."
        )
        if repair_note:
            user_msg += f"\n\n⚠️ 반드시 고칠 것: {repair_note}"
        try:
            # NOTE: 구조화출력(강제 tool_choice)과 Extended Thinking은 API상 병행 불가
            # (claude_client가 thinking을 자동 비활성화). 편집 품질은 구조화출력만으로도
            # 충분(실측 검증)하므로 thinking 대신 파싱 안정성(structured_output)을 택한다.
            edited, _ = await self.call_claude_json(
                user_message=user_msg,
                schema=EditedPost,
                max_tokens=900,
                uid=uid,
                system=_EDITOR_SYSTEM,
                structured_output=True,
            )
            return edited
        except Exception as e:
            logger.warning(f"[marketer] 편집 실패 {name}/{fmt}: {e}")
            return None

    # ── 진입점 ─────────────────────────────
    async def generate(
        self,
        ticker: str,
        fmt: str,
        uid: str = "",
        avoid_archetypes: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """단일 (종목 × 포맷) 초안 생성 — 4단계 하네스. 실패 시 None.

        avoid_archetypes: 최근 많이 쓴 앵글 유형(배치/발행 이력 기반 다양성 힌트, 비강제).
        """
        fmt = fmt if fmt in FORMATS else "contrarian"
        ticker = resolve_ticker(ticker) or ticker
        snapshot = build_instant_snapshot(ticker)
        if not snapshot or _numeric_fact_count(snapshot) < MIN_NUMERIC_FACTS:
            logger.warning(
                f"[marketer] 실수치 부족 — 생성 건너뜀 {ticker}/{fmt} "
                f"(facts={_numeric_fact_count(snapshot) if snapshot else 0}). "
                f"store 미적재 또는 데이터 결손일 수 있음."
            )
            return None

        name = snapshot.get("name") or ticker.upper()
        # 기준일을 facts에 동봉 → 앵글·작가·편집 3단계 모두 '오늘' 대신 일자로 쓰게 함.
        facts = _snapshot_facts(snapshot) + "\n\n" + _date_note(_as_of_label(snapshot))

        # 밸류에이션 밴드(1b/1c) — KR 한정, 백필된 밴드가 있으면 역사 분위수 + EPS 사이클을
        # facts에 주입(현황 단일 PER 함정을 자기 역사로 방어). 없으면 조용히 생략.
        if snapshot.get("is_kr"):
            try:
                from screener.core.fundamental_band import band_facts, cycle_assessment
                from screener.db.repository import load_fundamental_band

                band = load_fundamental_band(snapshot.get("ticker", ticker))
                bf = band_facts(band, snapshot.get("per"), snapshot.get("pbr"))
                if bf:
                    facts += "\n\n" + bf
                ca = cycle_assessment(band, snapshot.get("per"))
                if ca:
                    facts += "\n\n## 사이클 판정(밴드 기반)\n- " + ca
            except Exception as e:
                logger.debug(f"[marketer] 밴드 주입 실패 {name}: {e}")

        # ① 앵글 (실패해도 진행 — 앵글 없으면 빈 브리핑)
        angle = await self._find_angle(facts, fmt, name, uid, avoid_archetypes=avoid_archetypes)
        angle_brief = _angle_brief(angle) if angle else "# 편집 앵글\n(앵글 추출 실패 — 수치의 가장 강한 긴장 하나를 직접 잡아라)"

        # ② 작가 best-of-N
        candidates = await self._write_candidates(facts, angle_brief, fmt, name, uid)
        if not candidates:
            logger.warning(f"[marketer] 후보 0개 — 생성 실패 {name}/{fmt}")
            return None

        # ③ 편집/심판
        edited = await self._edit_and_pick(candidates, facts, angle_brief, fmt, name, uid)
        if edited is None:
            # 편집 실패 시 첫 후보를 graceful fallback으로 사용.
            best = candidates[0]
            edited = EditedPost(
                hook=best.hook, body=best.body,
                watchpoints=best.watchpoints, hashtags=best.hashtags,
            )

        text = assemble_post(_edited_to_post(edited))

        # ④ 결정론적 가드
        # 4-1. 자기언급/내부용어 + 빈 watchpoints → 한 번의 재편집으로 함께 고친다.
        warnings = guard_reader_first(text)
        repair_reasons: list[str] = []
        if warnings:
            repair_reasons.append(
                "다음 표현을 문장째 제거하고 독자 관심사로 대체: " + ", ".join(warnings)
            )
        if not (edited.watchpoints or []):
            # 종목글의 페이로드 = '앞으로 볼 것'. 비면 호응이 죽으므로 반드시 채운다.
            repair_reasons.append(
                "'앞으로 볼 것'(watchpoints)이 비었다 — facts/앵글에서 조건부·관찰형 관찰 포인트 "
                "1~3개를 반드시 채워라(수급/추세 조건, 지지/저항 관찰 수준, 실적 조건). "
                "매수가/목표가/손절가·'사라/팔라' 금지."
            )
        if len(text) > THREADS_MAX:
            # Threads 500자 하드 한도 초과 → 압축 재편집(발행 불가 방지).
            repair_reasons.append(
                f"전체 길이 {len(text)}자로 한도({THREADS_MAX}) 초과 — body를 줄이고 watchpoints를 "
                f"2개로 압축해 480자 이내로 만들어라(수치·관찰 포인트는 유지)."
            )
        if repair_reasons:
            logger.info(f"[marketer] 가드 재편집 {name}/{fmt}: {repair_reasons}")
            repaired = await self._edit_and_pick(
                candidates, facts, angle_brief, fmt, name, uid,
                repair_note=" / ".join(repair_reasons),
            )
            if repaired is not None:
                edited = repaired
                text = assemble_post(_edited_to_post(edited))
                warnings = guard_reader_first(text)
                if warnings or not (edited.watchpoints or []):
                    logger.warning(
                        f"[marketer] 재편집 후에도 잔존 {name}/{fmt}: "
                        f"reader={warnings} watchpoints_empty={not (edited.watchpoints or [])}"
                    )

        # 4-2. 법적 필터(비협상 — 하드 치환)
        text, found = BaseAgent.filter_forbidden(text)
        if found:
            logger.warning(f"[marketer] 금지표현 필터됨 {name}/{fmt}: {found}")

        # 4-3. 길이 경고
        if len(text) > THREADS_MAX:
            warnings = (warnings or []) + [f"길이초과({len(text)}>{THREADS_MAX})"]

        return {
            "ticker": snapshot.get("ticker", ticker.upper()),
            "name": name,
            "market": snapshot.get("market", ""),
            "is_kr": bool(snapshot.get("is_kr")),
            "fmt": fmt,
            "fmt_label": FORMATS[fmt]["label"],
            "text": text,
            "char_count": len(text),
            "filtered": found,
            "warnings": warnings,           # 콘솔 노출용(자기언급/길이) — human-in-loop
            "score": edited.score_total,    # 편집 자가채점(0~30)
            "candidates": len(candidates),
            "angle": angle.tension if angle else "",
            "archetype": (angle.archetype if angle else ""),  # 앵글 유형(다양성 추적/검수 노출)
            "source": "harness-v2",
        }


def _edited_to_post(e: EditedPost) -> ThreadsPost:
    return ThreadsPost(hook=e.hook, body=e.body, watchpoints=e.watchpoints, hashtags=e.hashtags)


def _watchpoints_block(items: list[str]) -> str:
    """관찰 포인트 → '앞으로 볼 것' 마무리 블록. 비면 빈 문자열."""
    pts = [p.strip().lstrip("①②③-• ").strip() for p in (items or []) if p and p.strip()]
    pts = [p for p in pts if p][:3]
    if not pts:
        return ""
    marks = ("①", "②", "③")
    lines = [f"{marks[i]} {p}" for i, p in enumerate(pts)]
    return "앞으로 볼 것\n" + "\n".join(lines)


def assemble_post(post: ThreadsPost) -> str:
    """ThreadsPost → 발행용 본문 문자열 (hook + body + 앞으로 볼 것 + hashtags).

    면책 문구는 본문에 넣지 않는다 — 계정 프로필(bio)에 상시 고지(JEON 결정 2026-06-27).
    """
    parts: list[str] = [post.hook.strip(), post.body.strip()]
    wp = _watchpoints_block(getattr(post, "watchpoints", []) or [])
    if wp:
        parts.append(wp)
    tags = [t.strip().lstrip("#") for t in (post.hashtags or []) if t and t.strip()]
    if tags:
        parts.append(" ".join(f"#{t}" for t in tags))
    text = "\n\n".join(p for p in parts if p)
    return text.strip()


async def generate_batch(
    tickers: list[str],
    formats: list[str],
    uid: str = "",
    avoid_archetypes: Optional[list[str]] = None,
) -> list[dict]:
    """여러 (종목 × 포맷) 조합을 동시 생성. 실패 항목은 제외.

    각 조합이 내부에서 4단계(앵글+작가N+편집)를 돌리므로, 조합 간 동시성은
    유지하되 LLM 호출량이 조합당 ~5콜임에 유의(저volume 마케팅이라 허용).

    avoid_archetypes: 최근 발행에서 많이 쓴 앵글 유형(다양성 힌트, 비강제). 배치 전체에
    동일 적용 — 종목별 데이터가 달라 자연 분산되고, 이력 기반 회피는 point 3가 채운다.
    """
    agent = MarketerAgent()
    pairs = [(t, f) for t in tickers for f in formats]
    results = await asyncio.gather(
        *(agent.generate(t, f, uid=uid, avoid_archetypes=avoid_archetypes) for t, f in pairs),
        return_exceptions=True,
    )
    out: list[dict] = []
    for r in results:
        if isinstance(r, dict):
            out.append(r)
        elif isinstance(r, Exception):
            logger.warning(f"[marketer] batch 항목 예외: {r}")
    return out


def pick_hot_tickers(limit: int = 3, exclude: Optional[list[str]] = None) -> list[str]:
    """스크리너 스냅샷에서 '오늘 화제 종목' 자동 선정 — 등락 절댓값 + 거래량비 상위.

    KR 대형주 위주(노이즈 적은 종목). 데이터 없으면 빈 리스트.

    exclude: 최근 이미 다룬 티커(연속성 메모리, point 3). 신선한 종목을 우선하되,
    제외 후 부족하면 랭킹 순서로 보충해 '생성 0'을 막는다(중복 방지는 베스트에포트).
    """
    try:
        from screener.api.routes import _get_combined_df

        df = _get_combined_df()
        if df is None or df.empty:
            return []
        d = df.copy()
        # KR 대형주 우선(시총 상위 300 내에서 변동성 큰 종목)
        if "market" in d.columns:
            kr = d[d["market"].isin(["KOSPI", "KOSDAQ"])]
            if not kr.empty:
                d = kr
        if "market_cap" in d.columns:
            d = d.nlargest(300, "market_cap")
        if "change_pct" not in d.columns:
            ranked = d.head(max(1, limit) * 4)["ticker"].astype(str).tolist()
        else:
            d = d.assign(_abs=d["change_pct"].abs())
            if "volume_ratio" in d.columns:
                d = d.assign(_score=d["_abs"].fillna(0) + d["volume_ratio"].fillna(0) * 2)
            else:
                d = d.assign(_score=d["_abs"].fillna(0))
            d = d.sort_values("_score", ascending=False)
            # 제외/보충을 위해 limit보다 넉넉히 후보를 뽑아둔다.
            ranked = d.head(max(1, limit) * 4)["ticker"].astype(str).tolist()

        ex = {str(t).upper() for t in (exclude or [])}
        fresh = [t for t in ranked if t.upper() not in ex]
        picked = fresh[: max(1, limit)]
        if len(picked) < max(1, limit):  # 신선 종목 부족 → 랭킹순 보충(생성 0 방지)
            picked += [t for t in ranked if t not in picked][: max(1, limit) - len(picked)]
        return picked[: max(1, limit)]
    except Exception as e:
        logger.debug(f"[marketer] hot tickers 선정 실패: {e}")
        return []


def recent_marketing_memory(limit: int = 60) -> dict:
    """최근 마케팅 글(marketing_drafts)에서 연속성 메모리 추출 — 중복 회피용(point 3).

    Returns:
      {
        "tickers": [최근 다룬 티커(중복 제거, 최신순)...],
        "archetypes": [최근 과다 사용된 앵글 유형(상위 2개)...],
      }
    Firestore 미가용/오류 시 빈 메모리(생성은 정상 진행).
    """
    empty = {"tickers": [], "archetypes": []}
    try:
        from firebase_admin import firestore

        from screener.db.firebase_client import get_db

        db = get_db()
        q = (
            db.collection("marketing_drafts")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(max(1, min(limit, 200)))
        )
        tickers: list[str] = []
        arche_counts: dict[str, int] = {}
        for doc in q.stream():
            dd = doc.to_dict() or {}
            t = str(dd.get("ticker") or "").upper()
            if t:
                tickers.append(t)
            a = str(dd.get("archetype") or "").strip()
            if a:
                arche_counts[a] = arche_counts.get(a, 0) + 1

        # 중복 티커 제거(최신순 보존)
        seen: set[str] = set()
        uniq: list[str] = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                uniq.append(t)

        # 과다 사용 유형 상위 2개만 회피(완전 차단 아님 — 데이터가 받쳐주면 작가가 무시).
        over_used = sorted(arche_counts, key=lambda k: arche_counts[k], reverse=True)[:2]
        return {"tickers": uniq, "archetypes": over_used}
    except Exception as e:
        logger.debug(f"[marketer] 연속성 메모리 조회 실패: {e}")
        return empty
