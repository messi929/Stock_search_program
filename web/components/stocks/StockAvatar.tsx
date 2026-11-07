import { cn } from "@/lib/utils";

// 색은 순위가 아니라 종목 코드에서 정한다. 같은 종목은 어느 화면에서든 같은 색이다.
const TINTS = [
  "bg-tint-1/15 text-tint-1",
  "bg-tint-2/15 text-tint-2",
  "bg-tint-3/15 text-tint-3",
  "bg-tint-4/15 text-tint-4",
  "bg-tint-5/15 text-tint-5",
  "bg-tint-6/15 text-tint-6",
];

function tintOf(ticker: string): string {
  let hash = 0;
  for (const ch of ticker) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  return TINTS[hash % TINTS.length];
}

/** 종목 첫 글자 아바타. 이름이 항상 옆에 있으므로 스크린리더에서는 숨긴다. */
export function StockAvatar({
  ticker,
  name,
  className,
}: {
  ticker: string;
  name?: string | null;
  className?: string;
}) {
  const initial = Array.from((name || ticker).trim())[0]?.toUpperCase() ?? "?";
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-bold",
        tintOf(ticker),
        className,
      )}
    >
      {initial}
    </span>
  );
}
