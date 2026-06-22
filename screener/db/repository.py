"""Firestore 데이터 저장/조회 — 종목, 테마, 히스토리, 동기화 메타데이터.

컬렉션 구조:
  stocks/{ticker}       — 종목 마스터 + 일일 시세 + 펀더멘탈 + 기술지표
  themes/{theme_id}     — 테마 정보 + 소속 종목
  theme_groups/{group}  — 테마 상위 그룹
  history/{ticker}      — 최근 60일 OHLCV (배열)
  sync_metadata/status  — 데이터 소스별 마지막 동기화 시각
"""

import math
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from google.cloud.firestore_v1.base_query import FieldFilter
from loguru import logger

from screener.db.firebase_client import get_db

# Firestore 배치 쓰기 한도
_BATCH_LIMIT = 490  # 안전 마진 (공식 한도 500)


# ──────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────

def _safe_val(v):
    """NaN/Inf → 0 변환 (Firestore는 NaN 저장 불가)."""
    if v is None:
        return 0
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return 0
    return v


# 펀더멘탈 필드 — 0이면 Firestore에 저장하지 않음 (다른 수집에서 덮어쓰기 방지)
_FUNDAMENTAL_FIELDS = {"per", "pbr", "div_yield", "roe", "eps", "div_years", "div_growth"}


def _row_to_doc(row: dict, skip_zero_fundamentals: bool = True) -> dict:
    """DataFrame row → Firestore 문서 (NaN 제거).

    skip_zero_fundamentals=True: 펀더멘탈 필드가 0이면 제외 (기존 값 보존)
    """
    doc = {}
    for k, v in row.items():
        v = _safe_val(v)
        # 펀더멘탈 필드가 0이면 Firestore에 저장하지 않아 기존 값 유지
        if skip_zero_fundamentals and k in _FUNDAMENTAL_FIELDS and v == 0:
            continue
        doc[k] = v
    return doc


# ──────────────────────────────────────────────
# 종목 저장/조회
# ──────────────────────────────────────────────

def save_stocks(df: pd.DataFrame, source: str = "kr"):
    """종목 DataFrame → Firestore stocks 컬렉션에 배치 저장.

    변경분만 저장: 기존 데이터와 비교하여 값이 바뀐 필드만 업데이트.
    Firestore 쓰기 할당량 절약을 위해 merge=True 사용.

    Args:
        df: 종목 DataFrame (ticker 컬럼 필수)
        source: 데이터 소스 태그 (kr, us, etf)
    """
    db = get_db()
    col = db.collection("stocks")
    now = datetime.now().isoformat()

    records = df.to_dict("records")
    total = len(records)
    written = 0
    skipped = 0

    # 기존 데이터 로드 (변경 비교용) — 소규모 배치이면 개별 비교, 대량이면 전체 쓰기
    existing_cache = {}
    if total <= 200:
        # 소량: 개별 문서 확인으로 변경분만 저장
        try:
            tickers_to_check = [str(r.get("ticker", "")) for r in records if r.get("ticker")]
            for ticker in tickers_to_check:
                doc = col.document(ticker).get()
                if doc.exists:
                    existing_cache[ticker] = doc.to_dict()
        except Exception:
            existing_cache = {}  # 실패 시 전체 쓰기

    for i in range(0, total, _BATCH_LIMIT):
        batch = db.batch()
        chunk = records[i:i + _BATCH_LIMIT]
        batch_count = 0
        for row in chunk:
            ticker = str(row.get("ticker", ""))
            if not ticker:
                continue
            doc = _row_to_doc(row)
            doc["source"] = source
            doc["updated_at"] = now

            # 변경 비교: 핵심 필드가 동일하면 스킵
            if ticker in existing_cache:
                old = existing_cache[ticker]
                changed = False
                for key, val in doc.items():
                    if key in ("updated_at",):
                        continue
                    old_val = old.get(key)
                    if old_val != val:
                        changed = True
                        break
                if not changed:
                    skipped += 1
                    continue

            batch.set(col.document(ticker), doc, merge=True)
            batch_count += 1

        if batch_count > 0:
            import time as _time
            for attempt in range(3):
                try:
                    batch.commit(timeout=30)
                    break
                except Exception as e:
                    if "429" in str(e) or "exceeded" in str(e).lower():
                        wait = (attempt + 1) * 5
                        logger.warning(f"Firestore 429 — {wait}초 대기 후 재시도 ({attempt+1}/3)")
                        _time.sleep(wait)
                    else:
                        logger.warning(f"stocks 배치 저장 실패: {e}")
                        break
        written += batch_count
        if (written + skipped) % 1000 == 0 or (written + skipped) >= total:
            logger.info(f"  Firestore stocks 저장: {written}쓰기 + {skipped}스킵 / {total}")

    logger.info(f"Firestore stocks 저장 완료: {written}쓰기, {skipped}스킵 (source={source})")


def load_stocks(source: Optional[str] = None) -> pd.DataFrame:
    """Firestore stocks 컬렉션 → DataFrame.

    Args:
        source: None이면 전체, "kr"/"us"/"etf"이면 해당 소스만
    """
    db = get_db()
    col = db.collection("stocks")

    if source:
        docs = col.where(filter=FieldFilter("source", "==", source)).stream()
    else:
        docs = col.stream()

    rows = []
    for doc in docs:
        data = doc.to_dict()
        data["ticker"] = doc.id
        rows.append(data)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 수집기 인코딩 손상으로 일부 문자열 필드(관측: sector)에 U+FFFD(복원 불가 mojibake)가
    # 섞여 Firestore에 적재된 경우가 있다. 서빙 단에서 손상 문자열은 빈 값으로 정화해
    # 사용자에게 한글 깨짐이 노출되지 않게 한다. (근본 복원은 collector 재수집 소관.)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(
                lambda v: "" if isinstance(v, str) and "�" in v else v
            )
    logger.info(f"Firestore stocks 로드: {len(df)}건 (source={source or 'all'})")
    return df


def load_stocks_updated_at(source: str = "kr") -> Optional[datetime]:
    """특정 소스의 마지막 업데이트 시각."""
    meta = get_sync_metadata()
    key = f"stocks_{source}_updated_at"
    ts = meta.get(key)
    if ts:
        return datetime.fromisoformat(ts)
    return None


# ──────────────────────────────────────────────
# 테마 저장/조회
# ──────────────────────────────────────────────

# 테마 상위 그룹 매핑 (키워드 기반)
THEME_GROUP_MAP = {
    "AI·반도체": [
        "인공지능", "AI", "반도체", "시스템반도체", "메모리반도체",
        "GPU", "HBM", "NPU", "파운드리", "반도체장비", "반도체소재",
        "챗봇", "딥러닝", "머신러닝", "빅데이터", "클라우드",
        "데이터센터", "엣지컴퓨팅", "자연어처리", "CXL", "MLCC",
        "디지털트윈", "3D 프린", "LED", "OLED", "PCB",
        "디스플레이", "deepfake", "딥페이크", "온디바이스",
        "퓨리오사", "양자", "퀀텀", "컴퓨팅", "음성인식",
        "냉각시스템", "액침냉각", "초전도체", "전자파",
        "갤럭시", "아이폰", "폴더블", "스마트폰", "모바일솔루션",
        "무선충전", "페라이트",
    ],
    "2차전지·에너지": [
        "2차전지", "배터리", "리튬", "양극재", "음극재", "전해질",
        "분리막", "전고체", "에너지저장", "ESS", "태양광", "풍력",
        "수소", "연료전지", "신재생에너지", "원자력", "SMR", "전력",
        "LNG", "LPG", "가스관", "석유", "셰일", "Shale",
        "탄소나노튜브", "CNT", "전선", "전력설비", "폐배터리",
        "탈 플라스틱", "친환경", "온실가스", "CCUS", "탄소",
        "그린", "태양전지", "도시가스", "석유화학", "윤활유",
        "풍력에너지", "핵융합", "스마트그리드", "요소수",
    ],
    "바이오·헬스케어": [
        "바이오", "제약", "신약", "임상", "진단", "의료기기",
        "헬스케어", "CMO", "CDMO", "mRNA", "항암", "세포치료",
        "유전자", "원격의료", "디지털헬스", "코로나", "백신",
        "치매", "치료", "줄기세포", "Healthcare", "화이자",
        "PFIZER", "모더나", "MODERNA", "펜데믹", "전염병",
        "의약품", "건강", "의료", "병원", "아프리카돼지열병", "ASF",
        "손소독", "마스크", "방역", "탈모", "보톡스", "보툴리눔",
        "비만", "마이크로바이옴", "오가노이드", "면역",
        "제대혈", "미용기기", "마이코플라스마", "폐렴",
        "제약업", "구제역", "광우병", "의료AI", "치아",
        "임플란트", "면역항암", "비만치료",
    ],
    "자동차·모빌리티": [
        "전기차", "자율주행", "자동차부품", "2차전지소재",
        "자동차", "UAM", "드론", "Drone", "로봇", "모빌리티",
        "라이다", "카메라모듈", "타이어", "스마트카", "SMART CAR",
        "항공", "LCC", "우주", "SpaceX", "스페이스",
        "리비안", "RIVIAN", "자전거", "전기자전거",
        "렌터카", "항공기부품", "누리호", "인공위성",
        "로봇", "협동로봇", "산업용",
    ],
    "IT·소프트웨어": [
        "소프트웨어", "플랫폼", "핀테크", "보안", "사이버보안",
        "SaaS", "블록체인", "메타버스", "가상현실", "증강현실",
        "게임", "웹툰", "콘텐츠", "OTT", "디지털트윈",
        "NFT", "SI(", "클라우드", "CCTV", "DVR",
        "네트워크", "인터넷", "SNS", "소셜네트워크", "키오스크", "KIOSK",
        "온라인", "IT ", "플랫폼", "앱", "쿠팡", "coupang",
        "카카오", "kakao", "토스", "toss", "야놀자",
        "컬리", "kurly", "USIM", "정보기술",
        "데이터", "프롭테크", "디지털", "두나무", "Dunamu",
        "전자결제", "간편결제", "코인", "암호화폐", "가상화폐",
        "전자상거래", "비트코인", "이더리움", "삼성페이", "애플페이",
        "STO", "토큰", "스테이블코인", "모바일게임",
        "광통신", "광케이블", "통신장비", "5G(", "보안주",
    ],
    "금융·부동산": [
        "은행", "증권", "보험", "카드", "금융", "부동산",
        "리츠", "REITs", "자산운용", "핀테크", "SPAC", "지주회사",
        "자산", "코리아 밸류업", "Value-up", "투자",
        "생명보험", "손해보험", "종합상사", "지주사", "창투사",
        "밸류업", "지역화폐",
    ],
    "소비재·유통": [
        "화장품", "뷰티", "의류", "패션", "식품", "음료",
        "프랜차이즈", "유통", "이커머스", "면세점", "럭셔리",
        "캐릭터", "소비", "가구", "인테리어", "홈쇼핑", "호텔",
        "리조트", "관광", "레저", "여행", "면세", "카지노",
        "애완", "반려", "아이스크림", "맥주", "주류",
        "스포츠", "골프", "생활", "담배", "편의점",
        "배달", "외식", "커피", "제과", "농업", "축산",
        "수산", "해양", "낚시", "등산", "웨딩",
        "교육", "학원", "출판", "문구", "완구",
        "가전", "전자제품", "백화점", "소매유통",
        "김밥", "음식료", "불매", "엔젤산업", "마리화나", "대마",
        "낙태", "피임", "건강기능식품", "비료", "사료",
        "육계", "콩", "대두", "겨울", "여름",
        "골판지", "모듈러주택", "음원", "음반", "주류업",
        "주정", "에탄올", "김밥", "냉동",
    ],
    "산업·소재": [
        "철강", "화학", "정유", "조선", "건설", "시멘트",
        "기계", "항공우주", "방위산업", "방산", "K-방산",
        "소재", "희토류", "비철금속", "귀금속", "강관",
        "광물", "자원개발", "플라즈마", "폐기물", "환경",
        "원자재", "GTX", "철도", "인프라", "SOC",
        "DMZ", "섬유", "유리", "시계", "그래핀",
        "플랜트", "엔지니어링", "산업가스", "페인트",
        "포장재", "컨테이너", "제지", "목재", "알루미늄",
        "구리", "아연", "니켈", "코발트", "텅스텐",
        "사파이어", "세라믹", "도료", "Steel", "아스콘",
        "아스팔트", "피팅", "밸브", "건설기계", "공작기계",
        "조선기자재", "화학섬유", "조림", "수자원",
        "해저터널", "지하도로", "조림사업",
    ],
    "통신·미디어": [
        "5G", "6G", "통신", "미디어", "광고", "엔터테인먼트",
        "K-POP", "한류", "방송", "영화", "음악",
        "엔터", "드라마", "아이돌", "연예", "MCN",
        "이동통신",
    ],
    "정책·테마": [
        "정책", "규제", "탄소중립", "그린뉴딜", "디지털뉴딜",
        "스마트팩토리", "스마트시티", "스마트팜", "스마트홈",
        "인구절벽", "고령화", "저출산", "국방", "안보",
        "남북", "통일", "평화", "대선", "총선",
        "예산", "신규사업", "창업", "벤처", "중소기업",
        "지역", "지방", "근무", "재택", "테마파크",
        "올림픽", "월드컵", "엑스포", "만박", "EXPO",
        "황사", "미세먼지", "폭염", "태풍", "재난",
        "해운", "물류", "택배", "무역", "수출",
        "상반기", "하반기", "신규상장", "대장주",
        "환율", "금리", "인플레이션", "디플레이션",
        "한전", "공기업", "공공", "규제완화",
        "출산장려", "재건", "우크라이나", "중국기업",
        "공기청정", "제습기", "일자리", "취업",
        "재개발", "모듈러", "불매", "수혜",
        "남북경협", "재택근무", "스마트워크",
    ],
}


def _classify_theme(theme_name: str) -> str:
    """테마명 → 상위 그룹 분류.

    키워드 매칭 시 짧은 키워드(2자 이하)는 단어 경계를 고려.
    """
    import re
    name = theme_name
    name_lower = name.lower()

    for group, keywords in THEME_GROUP_MAP.items():
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if len(kw_lower) <= 2:
                # 짧은 키워드: 단어 경계 또는 괄호 안에서만 매칭
                # "AI" → "AI 서비스", "온디바이스 AI" 매칭, "재난" 비매칭
                pattern = r'(?:^|[\s(/,])' + re.escape(kw_lower) + r'(?:$|[\s)/,])'
                if re.search(pattern, name_lower):
                    return group
            else:
                if kw_lower in name_lower:
                    return group
    return "기타"


def save_themes(themes: dict, stock_themes: dict):
    """테마 데이터 Firestore 저장.

    Args:
        themes: {theme_no: theme_name}
        stock_themes: {ticker: [theme_name, ...]}
    """
    db = get_db()
    now = datetime.now().isoformat()

    # 1) 테마 문서 저장 (그룹 분류 포함)
    col = db.collection("themes")
    records = list(themes.items())
    for i in range(0, len(records), _BATCH_LIMIT):
        batch = db.batch()
        for no, name in records[i:i + _BATCH_LIMIT]:
            group = _classify_theme(name)
            batch.set(col.document(str(no)), {
                "name": name,
                "group": group,
                "updated_at": now,
            }, merge=True)
        batch.commit(timeout=10)

    # 2) 종목-테마 매핑은 stocks 문서에 merge
    stock_col = db.collection("stocks")
    tickers = list(stock_themes.items())
    for i in range(0, len(tickers), _BATCH_LIMIT):
        batch = db.batch()
        for ticker, theme_list in tickers[i:i + _BATCH_LIMIT]:
            batch.set(stock_col.document(ticker), {
                "themes": ", ".join(theme_list),
                "theme_list": theme_list,
            }, merge=True)
        batch.commit(timeout=10)

    # 3) 테마 그룹 요약 저장
    group_col = db.collection("theme_groups")
    group_themes = {}
    for no, name in themes.items():
        g = _classify_theme(name)
        if g not in group_themes:
            group_themes[g] = []
        group_themes[g].append({"no": no, "name": name})

    b = db.batch()
    for group, items in group_themes.items():
        b.set(group_col.document(group), {
            "name": group,
            "themes": items,
            "count": len(items),
            "updated_at": now,
        })
    b.commit(timeout=10)

    logger.info(f"Firestore 테마 저장: {len(themes)}테마, {len(stock_themes)}종목, {len(group_themes)}그룹")


def load_themes() -> tuple[dict, dict, dict]:
    """Firestore에서 테마 데이터 로드.

    Returns:
        themes: {theme_no: theme_name}
        stock_themes: {ticker: [theme_name, ...]}
        theme_groups: {group_name: [{"no": ..., "name": ...}, ...]}
    """
    db = get_db()

    # 테마 목록
    themes = {}
    for doc in db.collection("themes").stream():
        data = doc.to_dict()
        themes[doc.id] = data.get("name", "")

    # 종목-테마 매핑 (stocks 컬렉션에서)
    stock_themes = {}
    for doc in db.collection("stocks").where(
        filter=FieldFilter("theme_list", "!=", [])
    ).select(["theme_list"]).stream():
        data = doc.to_dict()
        tl = data.get("theme_list", [])
        if tl:
            stock_themes[doc.id] = tl

    # 테마 그룹
    theme_groups = {}
    for doc in db.collection("theme_groups").stream():
        data = doc.to_dict()
        theme_groups[doc.id] = data.get("themes", [])

    logger.info(f"Firestore 테마 로드: {len(themes)}테마, {len(stock_themes)}종목")
    return themes, stock_themes, theme_groups


# ──────────────────────────────────────────────
# 히스토리 저장/조회
# ──────────────────────────────────────────────

def save_history(df: pd.DataFrame):
    """히스토리 DataFrame → Firestore 저장 (종목별 배열)."""
    if df.empty:
        return

    db = get_db()
    col = db.collection("history")
    now = datetime.now().isoformat()

    grouped = df.groupby("ticker")
    tickers = list(grouped.groups.keys())

    import time as _time

    saved = 0
    for i in range(0, len(tickers), _BATCH_LIMIT):
        batch = db.batch()
        chunk = tickers[i:i + _BATCH_LIMIT]
        for ticker in chunk:
            group = grouped.get_group(ticker).sort_values("date")
            records = []
            for _, row in group.iterrows():
                records.append({
                    "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
                    "open": _safe_val(float(row["open"])),
                    "high": _safe_val(float(row["high"])),
                    "low": _safe_val(float(row["low"])),
                    "close": _safe_val(float(row["close"])),
                    "volume": _safe_val(int(row["volume"])),
                })
            batch.set(col.document(ticker), {
                "data": records,
                "updated_at": now,
            })

        # 429 에러 대비: 재시도 + 딜레이
        for attempt in range(3):
            try:
                batch.commit(timeout=30)
                saved += len(chunk)
                break
            except Exception as e:
                if "429" in str(e) or "exceeded" in str(e).lower():
                    wait = (attempt + 1) * 5
                    logger.warning(f"Firestore 429 — {wait}초 대기 후 재시도 ({attempt+1}/3)")
                    _time.sleep(wait)
                else:
                    logger.warning(f"히스토리 배치 저장 실패: {e}")
                    break

        # 배치 간 딜레이 (429 방지)
        if i + _BATCH_LIMIT < len(tickers):
            _time.sleep(1)

    logger.info(f"Firestore 히스토리 저장: {saved}/{len(tickers)}종목")


def load_history() -> pd.DataFrame:
    """Firestore에서 히스토리 로드 → DataFrame."""
    db = get_db()
    all_rows = []

    for doc in db.collection("history").stream():
        ticker = doc.id
        data = doc.to_dict()
        for row in data.get("data", []):
            all_rows.append({
                "ticker": ticker,
                "date": pd.Timestamp(row["date"]),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            })

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    logger.info(f"Firestore 히스토리 로드: {len(df)}행")
    return df


def load_history_single(ticker: str) -> pd.DataFrame:
    """Firestore에서 단일 종목 히스토리 로드 → DataFrame."""
    db = get_db()
    doc = db.collection("history").document(ticker).get()
    if not doc.exists:
        return pd.DataFrame()

    data = doc.to_dict()
    rows = []
    for row in data.get("data", []):
        rows.append({
            "ticker": ticker,
            "date": pd.Timestamp(row["date"]),
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def get_history_last_date(ticker: str) -> Optional[str]:
    """특정 종목의 마지막 히스토리 날짜."""
    db = get_db()
    doc = db.collection("history").document(ticker).get()
    if doc.exists:
        data = doc.to_dict().get("data", [])
        if data:
            return data[-1]["date"]
    return None


# ──────────────────────────────────────────────
# score_history — 일별 buy_score 이력 (30일 보관)
# ──────────────────────────────────────────────

def save_score_history(date_str: str, scores: dict):
    """일별 buy_score 스냅샷 저장.

    Args:
        date_str: "2026-04-07" 형식
        scores: {ticker: {"buy_score": 72, "buy_grade": "상위", "close": 196500}, ...}
    """
    db = get_db()
    doc_ref = db.collection("score_history").document(date_str)
    doc_ref.set({"date": date_str, "scores": scores, "updated_at": datetime.now().isoformat()})
    logger.info(f"score_history 저장: {date_str} ({len(scores)}종목)")

    # 30일 이전 데이터 정리
    _cleanup_score_history(db, days=30)


def _cleanup_score_history(db, days: int = 30):
    """오래된 score_history 문서 삭제."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        old_docs = db.collection("score_history").where(
            filter=FieldFilter("date", "<", cutoff)
        ).stream()
        batch = db.batch()
        count = 0
        for doc in old_docs:
            batch.delete(doc.reference)
            count += 1
            if count >= _BATCH_LIMIT:
                batch.commit()
                batch = db.batch()
                count = 0
        if count > 0:
            batch.commit()
            logger.info(f"score_history 정리: {cutoff} 이전 삭제")
    except Exception as e:
        logger.debug(f"score_history 정리 실패: {e}")


def load_score_history(date_str: str) -> dict:
    """특정 일자 score_history 로드."""
    db = get_db()
    doc = db.collection("score_history").document(date_str).get()
    if doc.exists:
        return doc.to_dict().get("scores", {})
    return {}


# ──────────────────────────────────────────────
# supply_history — 종목별 수급 이력
# ──────────────────────────────────────────────

def save_supply_history(supply_data: dict):
    """수급 이력 저장 (종목별 최근 20일 배열).

    Args:
        supply_data: {ticker: {"foreign_net": int, "inst_net": int}, ...}
    """
    db = get_db()
    col = db.collection("supply_history")
    today = datetime.now().strftime("%Y-%m-%d")

    import time as _time

    tickers = list(supply_data.keys())
    saved = 0

    for i in range(0, len(tickers), _BATCH_LIMIT):
        batch = db.batch()
        chunk = tickers[i:i + _BATCH_LIMIT]
        for ticker in chunk:
            entry = supply_data[ticker]
            doc_ref = col.document(ticker)

            # 기존 데이터 로드 후 append
            try:
                existing = doc_ref.get()
                if existing.exists:
                    data_list = existing.to_dict().get("data", [])
                else:
                    data_list = []
            except Exception:
                data_list = []

            # 당일 데이터 중복 방지
            if data_list and data_list[-1].get("date") == today:
                data_list[-1] = {
                    "date": today,
                    "foreign_net": _safe_val(entry.get("foreign_net", 0)),
                    "inst_net": _safe_val(entry.get("inst_net", 0)),
                }
            else:
                data_list.append({
                    "date": today,
                    "foreign_net": _safe_val(entry.get("foreign_net", 0)),
                    "inst_net": _safe_val(entry.get("inst_net", 0)),
                })

            # 최근 20일만 유지
            data_list = data_list[-20:]

            batch.set(doc_ref, {"data": data_list, "updated_at": datetime.now().isoformat()})

        for attempt in range(3):
            try:
                batch.commit(timeout=30)
                saved += len(chunk)
                break
            except Exception as e:
                if "429" in str(e) or "exceeded" in str(e).lower():
                    _time.sleep((attempt + 1) * 5)
                else:
                    logger.warning(f"supply_history 배치 저장 실패: {e}")
                    break

    logger.info(f"supply_history 저장: {saved}/{len(tickers)}종목")


def load_supply_history(ticker: str) -> list[dict]:
    """단일 종목 수급 이력 로드."""
    db = get_db()
    doc = db.collection("supply_history").document(ticker).get()
    if doc.exists:
        return doc.to_dict().get("data", [])
    return []


def load_all_supply_history() -> dict:
    """전체 종목 수급 이력 로드."""
    db = get_db()
    result = {}
    for doc in db.collection("supply_history").stream():
        data = doc.to_dict()
        result[doc.id] = data.get("data", [])
    return result


# ──────────────────────────────────────────────
# 동기화 메타데이터
# ──────────────────────────────────────────────

def get_sync_metadata() -> dict:
    """동기화 상태 조회."""
    db = get_db()
    doc = db.collection("sync_metadata").document("status").get()
    if doc.exists:
        return doc.to_dict()
    return {}


def update_sync_metadata(**kwargs):
    """동기화 상태 업데이트.

    예: update_sync_metadata(stocks_kr_updated_at="2026-03-21T10:00:00",
                              fundamentals_updated_at="2026-03-21T10:05:00")
    """
    db = get_db()
    db.collection("sync_metadata").document("status").set(kwargs, merge=True)


def is_stale(key: str, max_age_hours: int = 24) -> bool:
    """특정 데이터 소스가 갱신이 필요한지 확인.

    Args:
        key: sync_metadata의 키 (예: "stocks_kr_updated_at")
        max_age_hours: 최대 허용 경과 시간
    """
    try:
        meta = get_sync_metadata()
    except Exception:
        return True
    ts = meta.get(key)
    if not ts:
        return True
    try:
        last = datetime.fromisoformat(ts)
        return datetime.now() - last > timedelta(hours=max_age_hours)
    except (ValueError, TypeError):
        return True
