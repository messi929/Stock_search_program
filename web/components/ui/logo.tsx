import { cn } from "@/lib/utils";

/** Axis 로고 — 가로·세로 축 위를 지나는 상승 곡선. */
export function Logo({ className, showName = true }: { className?: string; showName?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-bold tracking-tight", className)}>
      <svg viewBox="0 0 32 32" className="size-7 shrink-0" aria-hidden="true">
        <rect width="32" height="32" rx="9" className="fill-primary" />
        <path
          d="M8 8v16h16"
          fill="none"
          className="stroke-primary-foreground/50"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M11.5 20l4.5-5 3 2.5 5-6.5"
          fill="none"
          className="stroke-primary-foreground"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {showName ? <span>Axis</span> : <span className="sr-only">Axis</span>}
    </span>
  );
}
