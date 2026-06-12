/**
 * OG 이미지(next/og)용 한글 폰트 런타임 로더.
 *
 * @vercel/og(satori) 기본 폰트엔 한글 글리프가 없어 한글이 □□□로 깨진다.
 * 문서 제약: woff2 미지원(ttf/otf/woff만), 번들 500KB 한도 → 전체 한글 폰트 번들 불가.
 * 따라서 렌더할 텍스트에 필요한 글자만 Google Fonts에서 text-subset ttf로 받아온다.
 * 실패 시 null 반환 → 호출부는 폰트 없이 렌더(최악의 경우 기존과 동일, 더 나빠지지 않음).
 */

// css2 응답에서 ttf/otf/woff URL만 캡처(woff2 제외 — satori 미지원).
const FONT_SRC_RE =
  /src:\s*url\((https:\/\/[^)]+)\)\s*format\(['"]?(truetype|opentype|woff)['"]?\)/;

/**
 * 주어진 텍스트에 필요한 글리프만 담은 Noto Sans KR(700) ttf를 받아온다.
 * @param text 카드에 렌더되는 모든 문자열을 합친 것(중복 무관 — 서브셋이 알아서 처리)
 */
export async function loadKoreanFont(text: string): Promise<ArrayBuffer | null> {
  try {
    const family = "Noto+Sans+KR:wght@700";
    const url = `https://fonts.googleapis.com/css2?family=${family}&text=${encodeURIComponent(
      text
    )}`;
    // User-Agent를 지정하지 않으면 Google이 레거시 포맷(ttf)을 내려준다(woff2 회피).
    const cssRes = await fetch(url);
    if (!cssRes.ok) return null;
    const css = await cssRes.text();
    const m = css.match(FONT_SRC_RE);
    if (!m) return null;
    const fontRes = await fetch(m[1]);
    if (!fontRes.ok) return null;
    return await fontRes.arrayBuffer();
  } catch {
    return null;
  }
}
