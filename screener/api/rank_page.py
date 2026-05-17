"""공개 SEO 랜딩 페이지 — /rank/<date>.

검색엔진 크롤링용 서버사이드 렌더링. 가입·로그인 없이 접근 가능.
"""

from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from screener.api.routes import _data_store


router = APIRouter()

KST = timezone(timedelta(hours=9))


def _today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


@router.get("/rank", response_class=HTMLResponse)
async def rank_root():
    return RedirectResponse(f"/rank/{_today_kst()}", status_code=302)


@router.get("/rank/today", response_class=HTMLResponse)
async def rank_today():
    return RedirectResponse(f"/rank/{_today_kst()}", status_code=302)


@router.get("/rank/{date}", response_class=HTMLResponse)
async def rank_page(date: str):
    """해당 날짜 기준 TOP 종목 리포트 페이지."""
    df = _data_store.get("df")
    if df is None or df.empty:
        return HTMLResponse(_empty_html(date), status_code=200)

    sections = []
    # 1) 종합 점수 TOP 10
    if "buy_score" in df.columns:
        top = df.nlargest(10, "buy_score")
        top = top[top["buy_score"] > 0]
        sections.append(("💎 종합 점수 TOP 10", "buy_score", "점", top))

    # 2) 급등 예보
    if "pre_surge_score" in df.columns:
        top = df[df["pre_surge_score"] >= 3].nlargest(10, "pre_surge_score")
        if not top.empty:
            sections.append(("🚀 급등 예보 시그널 TOP", "pre_surge_score", "/5", top))

    # 3) 돌파 임박
    if "breakout_score" in df.columns:
        top = df[df["breakout_score"] >= 2].nlargest(10, "breakout_score")
        if not top.empty:
            sections.append(("🎯 52주 신고가 돌파 임박", "breakout_score", "/4", top))

    # 4) 오늘의 급등주 (등락률 상위)
    if "change_pct" in df.columns:
        top = df.nlargest(10, "change_pct")
        top = top[top["change_pct"] > 3]
        if not top.empty:
            sections.append(("🔥 오늘 급등 종목", "change_pct", "%", top))

    # 5) 외국인·기관 동반 매수
    if "dual_buy" in df.columns and "foreign_net" in df.columns:
        top = df[df["dual_buy"] == True].nlargest(10, "foreign_net")  # noqa: E712
        if not top.empty:
            sections.append(("🤝 외국인·기관 동반 매수", "foreign_net", "원", top))

    html = _render_html(date, sections, df)
    return HTMLResponse(html, headers={
        "Cache-Control": "public, max-age=600",  # 10분 캐시 (CDN 친화적)
    })


def _fmt_num(v, unit: str) -> str:
    try:
        n = float(v)
    except Exception:
        return "-"
    if unit == "점":
        return f"{n:.0f}점"
    if unit == "%":
        sign = "+" if n > 0 else ""
        return f"{sign}{n:.2f}%"
    if unit == "/5" or unit == "/4":
        return f"{int(n)}{unit}"
    if unit == "원":
        if abs(n) >= 1e8:
            return f"{n / 1e8:+.1f}억"
        if abs(n) >= 1e4:
            return f"{n / 1e4:+.0f}만"
        return f"{n:+.0f}"
    return str(n)


def _fmt_price(v, market: str) -> str:
    try:
        n = float(v)
    except Exception:
        return "-"
    if any(x in str(market).upper() for x in ("US", "NASDAQ", "NYSE")):
        return f"${n:,.2f}"
    return f"{n:,.0f}원"


def _render_section(title: str, value_col: str, unit: str, rows) -> str:
    items = []
    for _, r in rows.iterrows():
        ticker = escape(str(r.get("ticker", "")))
        name = escape(str(r.get("name", "") or ticker))
        market = str(r.get("market", "") or "")
        price = _fmt_price(r.get("close", 0), market)
        chg = float(r.get("change_pct", 0) or 0)
        chg_cls = "up" if chg > 0 else ("down" if chg < 0 else "")
        chg_s = f"{'+' if chg > 0 else ''}{chg:.2f}%"
        val = _fmt_num(r.get(value_col, 0), unit)
        items.append(f"""
        <li>
          <div class="r-rank"></div>
          <div class="r-info">
            <a class="r-name" href="/?ticker={ticker}">{name}</a>
            <span class="r-code">{ticker}</span>
            <span class="r-market">{escape(market)}</span>
          </div>
          <div class="r-price">{price}</div>
          <div class="r-chg {chg_cls}">{chg_s}</div>
          <div class="r-val">{val}</div>
        </li>""")
    return f"""
    <section class="rk-section">
      <h2>{escape(title)}</h2>
      <ol class="r-list">{''.join(items)}</ol>
    </section>"""


def _render_html(date: str, sections: list, df) -> str:
    title = f"{date} 종합 점수 TOP 종목 — Stock Screener Pro"
    description = f"{date} 기준 한국 주식 종합 점수 TOP 10, 급등 예보, 돌파 임박, 외국인·기관 동반순매수 종목을 한눈에. 3,500+ 종목 실시간 분석."
    body_sections = "".join(_render_section(t, v, u, r) for t, v, u, r in sections)
    total = len(df) if df is not None else 0

    # JSON-LD 구조화 데이터 (기사형)
    jsonld = f"""<script type="application/ld+json">{{
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "{title}",
      "datePublished": "{date}",
      "author": {{"@type": "Organization", "name": "Stock Screener Pro"}},
      "description": "{description}"
    }}</script>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="/rank/{date}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="article">
<meta property="og:locale" content="ko_KR">
<meta property="og:image" content="/og/rank.svg?date={escape(date)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(description)}">
<meta name="twitter:image" content="/og/rank.svg?date={escape(date)}">
{jsonld}
<style>
:root{{--bg:#0b0e14;--bg2:#141822;--bg3:#1c2130;--border:#2a2f3e;--text:#e4e8f0;--text2:#a8b0c2;--text3:#6b7380;--blue:#3182f6;--green:#03b26c;--red:#f04452;--gold:#f59f00;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}}
a{{color:var(--blue);text-decoration:none;}}
.container{{max-width:980px;margin:0 auto;padding:24px 20px;}}
header.top{{background:var(--bg2);border-bottom:1px solid var(--border);padding:14px 20px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;}}
header.top h1{{font-size:18px;font-weight:800;}}
header.top h1 span{{color:var(--blue);}}
header.top .cta{{padding:7px 18px;background:var(--blue);color:#fff;border-radius:20px;font-size:13px;font-weight:700;white-space:nowrap;}}
.hero{{padding:28px 0 18px;text-align:center;border-bottom:1px solid var(--border);margin-bottom:24px;}}
.hero .date{{display:inline-block;padding:4px 14px;background:rgba(49,130,246,.12);color:var(--blue);border-radius:14px;font-size:13px;font-weight:700;margin-bottom:12px;}}
.hero h1{{font-size:32px;font-weight:900;line-height:1.3;margin-bottom:10px;letter-spacing:-.5px;}}
.hero p{{color:var(--text2);font-size:14px;max-width:640px;margin:0 auto;}}
.hero .stats{{display:flex;justify-content:center;gap:18px;margin-top:18px;font-size:12px;color:var(--text3);flex-wrap:wrap;}}
.hero .stats strong{{color:var(--text);font-weight:700;}}
.rk-section{{margin-bottom:30px;background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:18px 20px;}}
.rk-section h2{{font-size:18px;font-weight:800;margin-bottom:14px;letter-spacing:-.3px;}}
.r-list{{list-style:none;counter-reset:rank;}}
.r-list li{{display:grid;grid-template-columns:32px minmax(160px,1fr) auto auto auto;gap:12px;align-items:center;padding:10px 4px;border-bottom:1px solid var(--border);counter-increment:rank;font-size:13px;}}
.r-list li:last-child{{border-bottom:none;}}
.r-list li .r-rank::before{{content:counter(rank);display:inline-flex;width:26px;height:26px;background:var(--bg3);color:var(--text2);border-radius:50%;font-size:12px;font-weight:700;align-items:center;justify-content:center;}}
.r-list li:nth-child(1) .r-rank::before{{background:linear-gradient(135deg,#fbbf24,#f59e0b);color:#000;}}
.r-list li:nth-child(2) .r-rank::before{{background:linear-gradient(135deg,#cbd5e1,#94a3b8);color:#000;}}
.r-list li:nth-child(3) .r-rank::before{{background:linear-gradient(135deg,#d97706,#92400e);color:#fff;}}
.r-info{{min-width:0;}}
.r-name{{font-weight:800;color:#fff;font-size:14px;}}
.r-name:hover{{color:var(--blue);}}
.r-code{{font-size:11px;color:var(--text3);margin-left:6px;}}
.r-market{{font-size:10px;color:var(--text3);background:var(--bg3);padding:1px 6px;border-radius:8px;margin-left:4px;}}
.r-price{{font-size:13px;font-weight:700;color:#fff;text-align:right;min-width:70px;}}
.r-chg{{font-size:12px;font-weight:700;text-align:right;min-width:60px;}}
.r-chg.up{{color:var(--red);}}.r-chg.down{{color:var(--blue);}}
.r-val{{font-size:12px;font-weight:700;color:var(--gold);text-align:right;min-width:60px;}}
.cta-section{{background:linear-gradient(135deg,rgba(49,130,246,.08),rgba(3,178,108,.04));border:1px solid rgba(49,130,246,.3);border-radius:12px;padding:28px 24px;text-align:center;margin:30px 0;}}
.cta-section h3{{font-size:20px;font-weight:800;margin-bottom:8px;}}
.cta-section p{{color:var(--text2);font-size:13px;margin-bottom:18px;}}
.cta-section .btn{{display:inline-block;padding:11px 28px;background:var(--blue);color:#fff;border-radius:24px;font-weight:700;font-size:14px;}}
footer{{padding:22px 0;border-top:1px solid var(--border);margin-top:28px;text-align:center;font-size:11px;color:var(--text3);}}
footer a{{color:var(--text3);margin:0 6px;}}
footer .disclaim{{max-width:640px;margin:10px auto 0;padding:10px 14px;background:var(--bg3);border-radius:8px;font-size:10px;line-height:1.6;}}
@media(max-width:640px){{
  .hero h1{{font-size:22px;}}
  .r-list li{{grid-template-columns:24px 1fr auto;gap:8px;}}
  .r-list li .r-price{{grid-column:2/3;grid-row:2;font-size:12px;text-align:left;}}
  .r-list li .r-chg{{grid-column:3/4;grid-row:1;}}
  .r-list li .r-val{{grid-column:3/4;grid-row:2;}}
}}
</style>
</head>
<body>
<header class="top">
  <h1>Stock <span>Screener</span> Pro</h1>
  <a class="cta" href="/">🔍 전체 종목 탐색</a>
</header>
<div class="container">
  <div class="hero">
    <div class="date">📅 {escape(date)}</div>
    <h1>오늘의 종합 점수 상위 종목</h1>
    <p>기술적·모멘텀·수급·가치 지표를 종합한 정량 스코어 기반 TOP 리스트입니다. 매수 권유가 아닌 참고 정보입니다.</p>
    <div class="stats">
      <span><strong>{total:,}</strong> 종목 실시간 분석</span>
      <span>·</span>
      <span>매일 09:30/16:00 업데이트</span>
      <span>·</span>
      <span>한국·미국 주식</span>
    </div>
  </div>

  {body_sections}

  <div class="cta-section">
    <h3>📈 매일 갱신되는 종합 점수 리스트</h3>
    <p>회원가입 후 7일간 Pro 기능 무료. 관심종목 저장·백테스트·포트폴리오 분석까지.</p>
    <a class="btn" href="/">무료로 시작하기 →</a>
  </div>
</div>
<footer>
  <div><a href="/">홈</a> · <a href="/pricing">요금제</a> · <a href="/terms">이용약관</a> · <a href="/privacy">개인정보</a> · <a href="/refund">환불정책</a></div>
  <div class="disclaim">본 페이지는 투자 자문이 아니며 투자 참고 자료입니다. 투자 결정과 결과는 본인 책임입니다. 과거 데이터는 미래 성과를 보장하지 않습니다.</div>
</footer>
</body>
</html>"""


def _empty_html(date: str) -> str:
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>{escape(date)} — 데이터 준비 중</title><meta http-equiv="refresh" content="30"></head><body style="background:#0b0e14;color:#e4e8f0;font-family:sans-serif;text-align:center;padding:80px 20px;">
<h1>📊 데이터 로딩 중</h1>
<p style="color:#a8b0c2;margin-top:10px;">시장 데이터를 준비하고 있습니다. 30초 후 자동 새로고침됩니다.</p>
<p style="margin-top:20px;"><a href="/" style="color:#3182f6;">홈으로 이동</a></p>
</body></html>"""


@router.get("/backtest-report", response_class=HTMLResponse)
async def backtest_report():
    """백테스트 시그널별 적중률 공개 리포트 (SEO)."""
    # routes.py의 백테스트 캐시 재사용
    try:
        from screener.api.routes import _cache_get
        data = _cache_get("backtest") or {}
    except Exception:
        data = {}

    title = "시그널 백테스트 리포트 — 정량 시그널 적중률"
    description = "급등 예보, 돌파 임박, 종합 점수 등 각 시그널의 20일 보유 시 적중률·평균수익·샤프·알파 전체 기간 백테스트 결과. 한국 주식 3,500+ 종목 대상."

    signals = data.get("signals") or {}
    score_tracking = data.get("score_tracking") or {}

    signal_labels = {
        "golden_cross": "골든크로스", "accumulation": "거래량 매집",
        "rsi_oversold": "RSI 과매도", "ma_squeeze_breakout": "이평 수렴 돌파",
        "volume_trend": "거래량 추세", "pre_surge": "급등 예보",
        "breakout": "52주 돌파", "dual_buy": "외국인·기관 동반매수",
    }
    score_labels = {
        "buy_70plus": "종합 매수점수 70+", "buy_50plus": "종합 매수점수 50+",
        "pre_surge": "급등 예보 4+", "breakout": "돌파 3+", "dual_buy": "동반 매수",
    }

    def _window20(v):
        if v.get("windows"):
            w = v["windows"].get("20") or v["windows"].get(20) or {}
            return w
        return {"hit_rate": v.get("hit_rate", 0), "avg_return": v.get("avg_return", 0), "sample_count": v.get("sample_count", 0)}

    def _card(key: str, v: dict, label_map: dict) -> str:
        w = _window20(v) if "windows" in v or "hit_rate" in v else {}
        hr = float(w.get("hit_rate", 0) or 0)
        ar = float(w.get("avg_return", 0) or w.get("20d_avg_return", 0) or 0)
        sc = int(w.get("sample_count", 0) or v.get("sample_count", 0) or 0)
        alpha = float(v.get("alpha", 0) or 0)
        name = label_map.get(key, v.get("label", key))
        cls = "up" if hr >= 60 else ("down" if hr < 45 else "")
        ar_cls = "up" if ar > 0 else "down"
        bar_w = max(0, min(hr, 100))
        alpha_badge = f'<span class="alpha {"pos" if alpha > 0 else "neg"}">{"+" if alpha > 0 else ""}{alpha:.1f}% α</span>' if alpha else ""
        return f"""
        <div class="bt-c">
          <div class="bt-h">{escape(name)} {alpha_badge}</div>
          <div class="bt-hr {cls}">{hr:.1f}%</div>
          <div class="bt-bar"><div class="bt-fill {cls}" style="width:{bar_w}%"></div></div>
          <div class="bt-sub">무작위 기준 50% 대비 {"+" if hr >= 50 else ""}{(hr - 50):.1f}%p</div>
          <div class="bt-row"><span>평균수익</span><span class="{ar_cls}">{"+" if ar > 0 else ""}{ar:.2f}%</span></div>
          <div class="bt-row"><span>샘플</span><span>{sc:,}건</span></div>
        </div>"""

    sig_cards = "".join(_card(k, v, signal_labels) for k, v in signals.items())
    score_cards = "".join(_card(k, v, score_labels) for k, v in score_tracking.items())

    sections = ""
    if score_cards:
        sections += f'<section><h2>💎 점수별 성과 추적 (20일 보유 기준)</h2><div class="bt-grid">{score_cards}</div></section>'
    if sig_cards:
        sections += f'<section><h2>🎯 시그널별 성과 (20일 보유 기준)</h2><div class="bt-grid">{sig_cards}</div></section>'
    if not sections:
        sections = '<section><h2>⏳ 백테스트 준비 중</h2><p style="color:#a8b0c2;">리포트가 곧 준비됩니다. 잠시 후 다시 방문해주세요.</p></section>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="/backtest-report">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="article">
<meta property="og:image" content="/og/backtest.svg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="/og/backtest.svg">
<style>
:root{{--bg:#0b0e14;--bg2:#141822;--bg3:#1c2130;--border:#2a2f3e;--text:#e4e8f0;--text2:#a8b0c2;--text3:#6b7380;--blue:#3182f6;--green:#03b26c;--red:#f04452;--gold:#f59f00;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Pretendard',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}}
a{{color:var(--blue);text-decoration:none;}}
header.top{{background:var(--bg2);border-bottom:1px solid var(--border);padding:14px 20px;display:flex;justify-content:space-between;align-items:center;}}
header.top h1{{font-size:18px;font-weight:800;}}
header.top h1 span{{color:var(--blue);}}
header.top .cta{{padding:7px 18px;background:var(--blue);color:#fff;border-radius:20px;font-size:13px;font-weight:700;}}
.wrap{{max-width:1040px;margin:0 auto;padding:24px 20px;}}
.hero{{padding:28px 0 20px;text-align:center;border-bottom:1px solid var(--border);margin-bottom:26px;}}
.hero h1{{font-size:28px;font-weight:900;line-height:1.3;margin-bottom:10px;letter-spacing:-.3px;}}
.hero p{{color:var(--text2);font-size:14px;max-width:720px;margin:0 auto;}}
section{{margin-bottom:34px;}}
section h2{{font-size:18px;font-weight:800;margin-bottom:16px;letter-spacing:-.2px;}}
.bt-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;}}
.bt-c{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;}}
.bt-h{{font-size:13px;color:var(--text2);font-weight:700;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;}}
.bt-hr{{font-size:28px;font-weight:900;margin-bottom:4px;}}
.bt-hr.up{{color:var(--green);}}.bt-hr.down{{color:var(--red);}}
.bt-bar{{height:6px;background:var(--bg);border-radius:3px;overflow:hidden;position:relative;margin-bottom:6px;}}
.bt-bar::before{{content:'';position:absolute;left:50%;top:-1px;bottom:-1px;width:1px;background:rgba(255,255,255,.3);z-index:1;}}
.bt-fill{{height:100%;background:var(--gold);}}
.bt-fill.up{{background:var(--green);}}.bt-fill.down{{background:var(--red);}}
.bt-sub{{font-size:10px;color:var(--text3);text-align:center;margin-bottom:8px;}}
.bt-row{{display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-top:1px solid var(--border);}}
.bt-row .up{{color:var(--green);font-weight:700;}}.bt-row .down{{color:var(--red);font-weight:700;}}
.alpha{{font-size:10px;padding:2px 6px;border-radius:6px;font-weight:700;}}
.alpha.pos{{background:rgba(3,178,108,.12);color:var(--green);}}
.alpha.neg{{background:rgba(240,68,82,.12);color:var(--red);}}
.cta-s{{background:linear-gradient(135deg,rgba(49,130,246,.08),rgba(3,178,108,.04));border:1px solid rgba(49,130,246,.3);border-radius:12px;padding:28px 24px;text-align:center;margin:30px 0;}}
.cta-s h3{{font-size:20px;font-weight:800;margin-bottom:8px;}}
.cta-s .btn{{display:inline-block;padding:11px 28px;background:var(--blue);color:#fff;border-radius:24px;font-weight:700;font-size:14px;}}
footer{{padding:20px 0;border-top:1px solid var(--border);margin-top:28px;text-align:center;font-size:11px;color:var(--text3);}}
footer a{{color:var(--text3);margin:0 6px;}}
.disclaim{{max-width:640px;margin:10px auto 0;padding:10px 14px;background:var(--bg3);border-radius:8px;font-size:10px;line-height:1.6;}}
</style>
</head><body>
<header class="top"><h1>Stock <span>Screener</span> Pro</h1><a class="cta" href="/">🔍 탐색 시작</a></header>
<div class="wrap">
  <div class="hero">
    <h1>📊 시그널 백테스트 리포트</h1>
    <p>각 AI 시그널을 과거 데이터에 적용했을 때 <strong>20일 보유 후</strong> 성과. 한국 주식 3,500+ 종목 전체 기간 대상. 무작위 기준 50%를 넘는 시그널이 유효합니다.</p>
  </div>
  {sections}
  <div class="cta-s">
    <h3>📈 내 관심종목 + 시그널 적중률 실시간 확인</h3>
    <p>회원가입 후 7일간 Pro 기능 무료. 직접 시그널 조합 백테스트 실행 가능.</p>
    <a class="btn" href="/">무료로 시작하기 →</a>
  </div>
</div>
<footer>
  <div><a href="/">홈</a> · <a href="/rank">오늘의 추천</a> · <a href="/pricing">요금제</a> · <a href="/terms">이용약관</a> · <a href="/privacy">개인정보</a></div>
  <div class="disclaim">과거 백테스트 결과는 미래 성과를 보장하지 않으며, 본 자료는 투자 자문이 아닙니다. 투자 결정은 본인 책임입니다.</div>
</footer>
</body></html>""", headers={"Cache-Control": "public, max-age=1800"})


@router.get("/sitemap.xml")
async def sitemap():
    """검색엔진용 사이트맵."""
    today = _today_kst()
    base = ""  # 상대 경로 (Cloud Run URL에 상관없이)
    pages = [
        ("/", "daily", "1.0"),
        ("/rank", "daily", "0.9"),
        (f"/rank/{today}", "daily", "0.9"),
        ("/backtest-report", "daily", "0.8"),
        ("/pricing", "monthly", "0.7"),
        ("/terms", "yearly", "0.3"),
        ("/privacy", "yearly", "0.3"),
        ("/refund", "yearly", "0.3"),
    ]
    urls = "".join(
        f"<url><loc>{base}{u}</loc><changefreq>{f}</changefreq><priority>{p}</priority></url>"
        for u, f, p in pages
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>"""
    from fastapi.responses import Response
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt")
async def robots():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /rank\n"
        "Allow: /backtest-report\n"
        "Allow: /pricing\n"
        "Disallow: /admin\n"
        "Disallow: /api/admin/\n"
        "Disallow: /api/user/\n"
        "Disallow: /api/auth/\n"
        "Disallow: /api/checkout\n"
        "Disallow: /api/webhooks/\n"
        "Sitemap: /sitemap.xml\n"
    )


@router.get("/og/rank.svg")
async def og_rank_image(date: str = ""):
    """/rank 페이지 공유용 SVG 썸네일 (1200x630 OG 표준)."""
    from fastapi.responses import Response
    d = date or _today_kst()
    df = _data_store.get("df")
    top_names = []
    if df is not None and not df.empty and "buy_score" in df.columns:
        top = df.nlargest(3, "buy_score")
        top_names = [str(n) for n in top["name"].tolist()[:3] if n]

    top_line = " · ".join(top_names) if top_names else "종합 점수 상위"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b0e14"/>
      <stop offset="0.5" stop-color="#141822"/>
      <stop offset="1" stop-color="#1c2130"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#3182f6"/>
      <stop offset="1" stop-color="#03b26c"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <circle cx="1000" cy="100" r="180" fill="#3182f6" opacity="0.08"/>
  <circle cx="200" cy="500" r="220" fill="#03b26c" opacity="0.06"/>
  <text x="80" y="130" font-family="-apple-system,system-ui,sans-serif" font-size="28" font-weight="700" fill="#a8b0c2">📊 Stock Screener Pro</text>
  <text x="80" y="230" font-family="-apple-system,system-ui,sans-serif" font-size="76" font-weight="900" fill="#ffffff">{escape(d)}</text>
  <text x="80" y="310" font-family="-apple-system,system-ui,sans-serif" font-size="56" font-weight="900" fill="url(#accent)">종합 점수 TOP</text>
  <text x="80" y="420" font-family="-apple-system,system-ui,sans-serif" font-size="32" font-weight="600" fill="#e4e8f0">{escape(top_line[:80])}</text>
  <text x="80" y="480" font-family="-apple-system,system-ui,sans-serif" font-size="22" font-weight="500" fill="#6b7380">기술 · 모멘텀 · 수급 · 가치 종합 지표</text>
  <rect x="80" y="530" width="300" height="60" rx="30" fill="#3182f6"/>
  <text x="230" y="570" font-family="-apple-system,system-ui,sans-serif" font-size="24" font-weight="800" fill="#fff" text-anchor="middle">무료로 시작하기 →</text>
  <text x="1120" y="600" font-family="-apple-system,system-ui,sans-serif" font-size="18" font-weight="500" fill="#6b7380" text-anchor="end">stock-screener.run.app</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/og/backtest.svg")
async def og_backtest_image():
    from fastapi.responses import Response
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg2" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b0e14"/>
      <stop offset="1" stop-color="#1c2130"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg2)"/>
  <text x="80" y="130" font-family="-apple-system,system-ui,sans-serif" font-size="28" font-weight="700" fill="#a8b0c2">📊 Stock Screener Pro</text>
  <text x="80" y="250" font-family="-apple-system,system-ui,sans-serif" font-size="76" font-weight="900" fill="#ffffff">📊 백테스트 리포트</text>
  <text x="80" y="340" font-family="-apple-system,system-ui,sans-serif" font-size="44" font-weight="800" fill="#03b26c">AI 시그널 20일 적중률</text>
  <text x="80" y="410" font-family="-apple-system,system-ui,sans-serif" font-size="26" font-weight="500" fill="#e4e8f0">급등 예보 · 돌파 임박 · 종합 점수 · 외국인·기관 동반순매수</text>
  <text x="80" y="460" font-family="-apple-system,system-ui,sans-serif" font-size="22" font-weight="500" fill="#6b7380">무작위 기준 50% 대비 성과 공개</text>
  <rect x="80" y="520" width="300" height="60" rx="30" fill="#3182f6"/>
  <text x="230" y="560" font-family="-apple-system,system-ui,sans-serif" font-size="24" font-weight="800" fill="#fff" text-anchor="middle">리포트 확인 →</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=7200"})
