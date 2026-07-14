"""교육 콘텐츠 생성기 — 마케팅 콘텐츠 공장(스레드).

0→1 신뢰 축적용 '교육 글'. 종목 콜이 아니라 **판단하는 법**을 가르쳐 브랜드
정체성("추천 안 함 · 판단은 당신 몫")을 콘텐츠로 증명한다. 저장·재공유가 잘 되는
유형이라 팔로워 0에서도 도달이 열리는 통로.

두 시리즈:
  - psychology(투자 심리 함정): 손실회피·FOMO·확증편향 등 행동편향
  - metric(지표 읽는 법): RSI·PER·수급·거래량 등 지표를 '신호'가 아닌 '관찰'로 읽기

하이브리드: 개념을 가르치되, '오늘 화제 종목'의 **실제 수치 하나**를 삽화로 얹어
구체성을 준다. 단 그 종목은 개념의 예시일 뿐 — 종목 자체에 대한 평가·전망·추천은
절대 하지 않는다(법적 안전선).

개념 사실은 토픽 뱅크의 teach에 **미리 시드**한다 — 검증 브랜드라 교육 내용이 틀리면
안 되므로 LLM이 금융 사실을 창작하지 않게 근거를 준다.

LEGAL: 추천/매수·매도/목표가/단정 금지. 면책은 본문이 아니라 프로필 bio 상시 고지.
"""

from __future__ import annotations

import random
from typing import Optional

from loguru import logger

from agents.base import BaseAgent
from agents.instant import build_instant_snapshot, resolve_ticker
from agents.marketer import (
    ThreadsPost,
    _as_of_label,
    assemble_post,
    guard_post,
    pick_hot_tickers,
)
from agents.threads_style import LLM_BUDGET, VOICE_RULES, finalize_thread
from agents.instant import _snapshot_facts  # noqa: E402  (내부 팩트 포매터 재활용)
from utils.claude_client import MODEL_SONNET

# ──────────────────────────────────────────────
# 토픽 뱅크 (개념 사실을 시드 — 창작 금지의 근거)
# ──────────────────────────────────────────────

# key: 다양성 추적용 고유 슬러그 / title: 글감 제목 / teach: 정확한 핵심 개념(시드)
# example_fit: 이 개념을 잘 보여주는 스냅샷 수치 유형(하이브리드 삽화 힌트)
_TOPICS: tuple[dict[str, str], ...] = (
    # ── 투자 심리 함정 (psychology) ──
    {
        "series": "psychology",
        "key": "loss_aversion",
        "title": "손실회피 — 수익은 짧게, 손실은 길게",
        "teach": (
            "사람은 같은 크기라도 손실의 고통을 이득의 기쁨보다 약 2배로 느낀다(카너먼·트버스키). "
            "그래서 오른 종목은 '더 빠지기 전에' 서둘러 익절하고, 물린 종목은 '본전 오면 팔자'며 "
            "오래 버틴다 — 수익은 짧게 끊고 손실은 길게 안는 처분효과. "
            "되짚을 질문: 지금 '판단'으로 들고 있나, '본전 심리'로 버티나."
        ),
        "example_fit": "최근 큰 등락률(%) 또는 52주 고가 대비 위치",
    },
    {
        "series": "psychology",
        "key": "fomo",
        "title": "FOMO — 남들이 사니까 나도",
        "teach": (
            "급등을 목격하면 '나만 놓친다'는 조바심에 이미 많이 오른 자리에서 추격 매수하게 된다. "
            "정작 근거는 '남들이 산다'뿐. 뒤늦게 들어가 고점 부근을 떠안는 전형적 패턴. "
            "되짚을 질문: 왜 사는지 남 얘기 말고 '숫자로' 말할 수 있나."
        ),
        "example_fit": "거래량비(평균 대비 몇 배) 또는 큰 상승률(%)",
    },
    {
        "series": "psychology",
        "key": "confirmation_bias",
        "title": "확증편향 — 내 종목 호재만 검색",
        "teach": (
            "일단 사고 나면 그 종목의 호재만 눈에 들어오고 악재는 무시하게 된다(확증편향). "
            "반대 근거를 일부러 찾아봐야 균형이 잡힌다. "
            "되짚을 질문: 내가 든 종목의 '약점'을 세 가지 댈 수 있나."
        ),
        "example_fit": "강점·약점이 갈리는 수치 조합(예: 상승률과 외국인 수급 방향이 엇갈릴 때)",
    },
    {
        "series": "psychology",
        "key": "anchoring",
        "title": "앵커링 — 매수가에 갇힌 마음",
        "teach": (
            "내 매수가나 전고점 같은 특정 숫자에 마음이 고정되면 그 숫자를 기준으로 싸다/비싸다를 "
            "판단하게 된다(앵커링). 정작 시장은 내 매수가를 모른다. "
            "되짚을 질문: 매수가를 지우고 봐도 지금 살 만한 자리인가."
        ),
        "example_fit": "52주 고가 대비 위치(%) 또는 현재가와 이동평균선의 관계",
    },
    {
        "series": "psychology",
        "key": "sunk_cost",
        "title": "매몰비용 — '여기서 팔면 손해 확정'",
        "teach": (
            "이미 물린 손실이 아까워 '지금 팔면 손해 확정'이라며 나쁜 판단을 이어간다. "
            "이미 쓴 돈(매몰비용)은 앞으로의 결정에서 빼야 한다. "
            "되짚을 질문: 이 종목을 오늘 처음 본다면, 그래도 살까."
        ),
        "example_fit": "약세를 보여주는 수치(하락률, 52주 저가 근접 등)",
    },
    {
        "series": "psychology",
        "key": "recency_bias",
        "title": "최신편향 — 최근 흐름이 계속될 거란 착각",
        "teach": (
            "최근 오르면 계속 오를 것 같고 최근 빠지면 계속 빠질 것 같다(최신편향). "
            "뇌는 가까운 기억에 큰 가중치를 준다. 짧은 흐름을 추세로 착각하기 쉽다. "
            "되짚을 질문: 최근 며칠이 아니라 더 긴 흐름을 봤나."
        ),
        "example_fit": "짧은 기간 급등락률(%) 또는 연속 상승 일수",
    },
    {
        "series": "psychology",
        "key": "overconfidence",
        "title": "과잉확신 — 몇 번 맞히면 실력이라 착각",
        "teach": (
            "몇 번 맞히면 그게 실력이라 착각해 베팅 크기를 키운다(과잉확신). "
            "운과 실력을 구분 못 하면 한 번의 큰 실수로 그동안의 수익이 되돌아온다. "
            "되짚을 질문: 내 판단이 틀렸을 때의 계획이 있나."
        ),
        "example_fit": "변동성이 큰 수치(높은 거래량비, 큰 등락률)",
    },
    # ── 지표 읽는 법 (metric) ──
    {
        "series": "metric",
        "key": "rsi",
        "title": "RSI 70 넘으면 무조건 팔아야 할까",
        "teach": (
            "RSI(14)는 최근 상승·하락 압력을 0~100으로 나타낸 지표로, 흔히 70 이상 과열·30 이하 "
            "과매도로 본다. 하지만 강한 추세에선 70을 넘고도 계속 오르고 30 아래서 더 빠지기도 한다. "
            "70/30은 '매매 신호'가 아니라 '지금 한쪽으로 쏠렸다'는 관찰일 뿐. "
            "핵심: 과열은 경계 신호이지 반전의 약속이 아니다."
        ),
        "example_fit": "RSI(14) 값",
    },
    {
        "series": "metric",
        "key": "per_cyclical",
        "title": "PER 낮으면 싼 걸까 — 경기민감주 함정",
        "teach": (
            "PER은 주가를 주당순이익으로 나눈 값이라 낮으면 싸 보인다. 그런데 반도체·조선·화학 같은 "
            "경기민감주는 이익이 정점일 때 PER이 가장 낮게, 바닥일 때 높게 보인다. "
            "그래서 호황 끝물의 '저PER'은 함정일 수 있다. "
            "핵심: PER 숫자 하나보다 '이익이 사이클 어디쯤인가'를 먼저 묻는다."
        ),
        "example_fit": "PER 값(특히 반도체·화학·조선 등 경기민감 섹터일 때)",
    },
    {
        "series": "metric",
        "key": "foreign_flow",
        "title": "외국인 순매수 5일 연속, 어떻게 읽나",
        "teach": (
            "외국인·기관의 연속 순매수/순매도는 수급의 방향을 보여준다. 다만 연속일수 자체가 "
            "상승을 보장하진 않는다 — 규모와 함께 봐야 하고, 지수 리밸런싱 같은 기계적 매매도 섞인다. "
            "핵심: '며칠'만 세지 말고 '얼마나(규모)'를 함께 본다."
        ),
        "example_fit": "외국인 연속 순매수 일수",
    },
    {
        "series": "metric",
        "key": "volume",
        "title": "거래량이 터졌다는 게 무슨 의미인가",
        "teach": (
            "거래량은 그 가격 움직임에 대한 '동의의 크기'다. 거래량이 실린 상승·하락은 신뢰도가 높고, "
            "거래량 없는 움직임은 쉽게 되돌려진다. 급등했는데 거래량이 안 실렸다면 의심할 만하다. "
            "핵심: 가격만 보지 말고 '얼마나 많은 손이 동의했나'를 본다."
        ),
        "example_fit": "거래량비(평균 대비 몇 배)",
    },
    {
        "series": "metric",
        "key": "moving_average",
        "title": "골든크로스는 '매수 신호'가 아니다",
        "teach": (
            "이동평균선은 최근 N일 평균가다. 단기선이 장기선 위에 놓인 정배열이나 골든크로스는 "
            "'추세가 위'라는 사실 관찰이다. 하지만 후행 지표라 이미 오른 뒤 나타나고, 횡보장에선 "
            "잦은 헛신호를 준다. "
            "핵심: 골든크로스는 '사실'이지 '사라는 신호'가 아니다."
        ),
        "example_fit": "현재가와 20일선/60일선의 관계, 이격(%)",
    },
    {
        "series": "metric",
        "key": "pbr",
        "title": "PBR 1배 아래면 무조건 싼가",
        "teach": (
            "PBR은 주가를 주당순자산으로 나눈 값으로, 1배면 시가총액이 장부상 순자산과 같다는 뜻이다. "
            "낮으면 자산 대비 싸 보이지만 업종마다 정상 범위가 다르고(은행은 낮고 IT는 높다) 자산의 "
            "질도 봐야 한다. "
            "핵심: 'PBR 0.8'만으로 싸다 하지 말고 업종·자산의 질과 함께 본다."
        ),
        "example_fit": "PBR 값",
    },
    {
        "series": "metric",
        "key": "roe",
        "title": "높은 ROE가 실력인지 빚인지",
        "teach": (
            "ROE는 자기자본으로 얼마의 이익을 냈는지(자본 효율)를 본다. 높을수록 좋아 보이지만 "
            "빚을 많이 써도 ROE는 올라간다 — 부채비율과 함께 봐야 진짜 실력이 보인다. "
            "핵심: 높은 ROE가 효율에서 나온 건지 레버리지에서 나온 건지 구분한다."
        ),
        "example_fit": "ROE 값",
    },
    {
        "series": "metric",
        "key": "high_low_52w",
        "title": "52주 고가·저가, 위치의 심리학",
        "teach": (
            "52주 고가·저가 대비 위치는 지금 주가가 '어디쯤'인지를 보여준다. 고가 근처는 강한 심리를, "
            "저가 근처는 약한 심리를 반영하지만 그 자체가 방향을 정하진 않는다 — 신고가가 계속 가기도 "
            "하고 신저가가 더 빠지기도 한다. "
            "핵심: 위치는 방향이 아니라 '심리의 온도'다."
        ),
        "example_fit": "52주 고가 대비(%) 위치",
    },
    {
        "series": "metric",
        "key": "volatility",
        "title": "변동성이 크다 = 나쁘다? 아니다",
        "teach": (
            "변동성(예: 20일)은 가격이 얼마나 출렁이는지를 나타낸다. 크다고 나쁜 게 아니라 '위아래 폭이 "
            "넓다'는 뜻 — 기회도 손실도 함께 커진다. 변동성이 급격히 커지면 시장이 불안하다는 신호일 수 있다. "
            "핵심: 변동성은 방향이 아니라 '진폭'을 말한다."
        ),
        "example_fit": "20일 변동성 또는 큰 등락률(%)",
    },
)

# 시리즈 라벨(검수 화면/포맷 표기용)
_SERIES_LABEL = {
    "psychology": "투자 심리 함정",
    "metric": "지표 읽는 법",
}


# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

_SYSTEM = f"""당신은 한국 주식 스레드(Threads) 계정의 화자입니다.
투자 개념 하나를 골라, 한국 투자자가 1분 안에 읽고 '아, 그래서 이렇게 봐야 하는구나'를
가져가는 **교육 글**을 씁니다. 종목을 평가하는 글이 절대 아닙니다.

{VOICE_RULES}

## 교육 내용의 정확성 (검증 브랜드의 생명선)
- 개념 설명은 **반드시 주어진 '가르칠 핵심(teach)' 안에서만** 한다. teach에 없는 수치·정의·
  인물·이론은 창작하지 않는다. 애매하면 단정 말고 관찰형으로.
- 쉬운 말로 풀되 사실을 왜곡하지 않는다. 어려운 용어는 한 번 풀어 설명한다.

## 하이브리드 — 실제 수치 삽화 (선택)
- '예시 종목 수치'가 주어지면, 그 중 개념을 가장 잘 보여주는 **수치 딱 하나**를 삽화로 얹어
  구체성을 준다. 예: "예를 들어 삼성전자가 6월 26일 RSI 72처럼 과열권에 있을 때…"
- ⚠️ 그 종목은 **개념의 예시일 뿐**이다. 그 종목을 평가·전망·추천하지 않는다.
  "이 종목이 좋다/나쁘다/오른다/사라" 절대 금지. 오직 '개념을 보여주는 사례'로만 쓴다.
- 예시 수치가 없거나 개념과 안 맞으면 **억지로 넣지 말고** 개념만으로 담백하게 쓴다.
- 시점 있는 수치엔 '오늘/지금/현재' 대신 주어진 기준일을 쓴다(한 번만).

## 구성 (스레드에서 읽히는 형태)
- hook(첫 줄): 독자가 겪는 상황이나 오해를 콕 찌르는 한 줄(예: "'PER 9배면 싸다'고 생각했지?").
- body: 개념을 3~5줄로 쉽게. '무슨 오해 → 실제로는 → 그래서 이렇게 보라' 흐름.
- 마지막 줄: 독자가 스스로 판단하도록 되짚는 질문 한 줄(teach의 '되짚을 질문/핵심'을 활용).
- watchpoints: **반드시 비운다([])**. 교육 글의 마무리는 '되짚는 질문'이지 종목 관찰 포인트가 아니다.
- 전체가 {LLM_BUDGET}자 이내(Threads 글 1개 한도 500자)."""


class EducationAgent(BaseAgent):
    """Sonnet 기반 교육 콘텐츠 생성기.

    간판 신뢰 콘텐츠 + 개념 정확성이 중요해 Sonnet 사용(1일 1편, ~30원). teach 시드로
    환각을 억제하지만, 금융 개념이 미묘하게 틀리면 브랜드에 치명적이라 품질을 택한다.
    """

    def __init__(self, claude=None):
        super().__init__(
            agent_name="education",
            model=MODEL_SONNET,
            system_prompt=_SYSTEM,
            claude=claude,
        )

    async def run(self, input_data=None):  # noqa: D401
        raise NotImplementedError("EducationAgent은 generate()를 사용하세요")

    async def generate(
        self,
        uid: str = "",
        series: Optional[list[str]] = None,
        avoid_keys: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """교육 글 1편 생성. 실패 시 None.

        series: ['psychology','metric'] 중 켤 시리즈(기본=둘 다).
        avoid_keys: 최근 다룬 토픽 key(중복 회피).
        """
        topic = pick_topic(series=series, avoid_keys=avoid_keys)
        if not topic:
            logger.warning("[education] 켜진 시리즈에 토픽이 없음 — 생성 중단")
            return None

        example_block, example_ticker = _build_example_block(topic, exclude=avoid_keys)

        user_msg = (
            f"# 가르칠 개념\n제목: {topic['title']}\n시리즈: {_SERIES_LABEL[topic['series']]}\n\n"
            f"# 가르칠 핵심 (teach — 이 안에서만 설명, 창작 금지)\n{topic['teach']}\n\n"
            f"# 이 개념을 잘 보여주는 수치 유형(삽화 힌트)\n{topic['example_fit']}\n"
            f"{example_block}\n"
            f"위 개념으로 교육 스레드 글 한 편을 작성하세요. 예시 종목이 있으면 개념의 삽화로만 "
            f"수치 하나를 얹되 그 종목을 평가·추천하지 마세요. 없으면 개념만으로 담백하게."
        )

        try:
            post, _meta = await self.call_claude_json(
                user_message=user_msg,
                schema=ThreadsPost,
                max_tokens=1200,  # 반말 전환으로 문장이 길어짐 — 잘리면 구조화 JSON이 깨진다
                uid=uid,
                structured_output=True,
            )
        except Exception as e:
            logger.warning(f"[education] 생성 실패 {topic['key']}: {e}")
            return None

        # 교육 글은 종목 관찰 포인트가 없다 → watchpoints 강제 비움(모델이 채워도 무시).
        post.watchpoints = []
        text = assemble_post(post)

        # ④ 결정론적 가드 — 자기언급·사족·존댓말 혼입 + **미확인 수치**(teach·삽화에 없는 숫자).
        # 교육 글은 개념이 미묘하게 틀리면 브랜드에 치명적이라 수치 창작을 특히 경계한다.
        warnings = guard_post(text, user_msg)
        if warnings:
            logger.warning(f"[education] 가드 경고: {warnings}")

        # 홍보는 가드를 통과한 뒤 별도 파트로 붙인다(가드 대상 아님).
        parts, text, found = finalize_thread([text])
        if found:
            logger.warning(f"[education] 금지표현 필터됨: {found}")

        return {
            "kind": "education",
            "ticker": "",
            "name": topic["title"],
            "market": "",
            "is_kr": False,
            "fmt": f"edu_{topic['series']}",
            "fmt_label": f"교육 · {_SERIES_LABEL[topic['series']]}",
            "parts": parts,
            "text": text,
            "char_count": len(parts[0]),
            "filtered": found,
            "warnings": warnings,
            "source": "sonnet",
            "topic_key": topic["key"],  # 다양성 추적(중복 회피)
            "series": topic["series"],
            "example_ticker": example_ticker,  # 삽화로 인용한 종목(검수 참고)
        }


def pick_topic(
    series: Optional[list[str]] = None,
    avoid_keys: Optional[list[str]] = None,
) -> Optional[dict]:
    """켜진 시리즈에서 최근 안 쓴 토픽 하나 선정. 모두 소진됐으면 전체에서 무작위."""
    allowed = set(series) if series else {"psychology", "metric"}
    pool = [t for t in _TOPICS if t["series"] in allowed]
    if not pool:
        return None
    avoid = {str(k) for k in (avoid_keys or [])}
    fresh = [t for t in pool if t["key"] not in avoid]
    candidates = fresh or pool  # 다 소진되면 전체 순환
    return random.choice(candidates)


def _build_example_block(
    topic: dict, exclude: Optional[list[str]] = None
) -> tuple[str, str]:
    """하이브리드 삽화용 — 화제 종목 1개의 실제 수치 블록 + 종목 티커. 없으면 ("", "")."""
    try:
        tickers = pick_hot_tickers(limit=1)
        if not tickers:
            return "", ""
        ticker = resolve_ticker(tickers[0]) or tickers[0]
        snap = build_instant_snapshot(ticker)
        if not snap:
            return "", ""
        as_of = _as_of_label(snap)
        date_line = f"(기준일: {as_of})" if as_of else "(기준일 정보 없음 — 시점어 금지)"
        block = (
            "\n\n# 예시 종목 실제 수치 (개념의 삽화로만 — 이 종목을 평가·전망·추천하지 말 것) "
            f"{date_line}\n{_snapshot_facts(snap)}"
        )
        return block, snap.get("ticker", ticker)
    except Exception as e:
        logger.debug(f"[education] 예시 종목 수치 실패(개념만 진행): {e}")
        return "", ""


async def generate_education(
    uid: str = "",
    series: Optional[list[str]] = None,
    avoid_keys: Optional[list[str]] = None,
) -> Optional[dict]:
    """편의 함수 — 교육 글 1편 생성."""
    return await EducationAgent().generate(uid=uid, series=series, avoid_keys=avoid_keys)


def recent_education_keys(limit: int = 40) -> list[str]:
    """최근 교육 초안(marketing_drafts, kind=education)의 topic_key — 중복 회피용.

    Firestore 미가용/오류 시 빈 리스트(생성은 정상 진행).
    """
    try:
        from firebase_admin import firestore

        from screener.db.firebase_client import get_db

        db = get_db()
        q = (
            db.collection("marketing_drafts")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(max(1, min(limit, 200)))
        )
        keys: list[str] = []
        for doc in q.stream():
            dd = doc.to_dict() or {}
            if dd.get("kind") != "education":
                continue
            k = str(dd.get("topic_key") or "").strip()
            if k:
                keys.append(k)
        return keys
    except Exception as e:
        logger.debug(f"[education] 최근 토픽 조회 실패: {e}")
        return []
