"use client";

/**
 * 어려운 투자 용어에 붙이는 풀이 팝오버.
 * 데스크톱은 hover, 모바일은 탭으로 연다. 키보드는 Enter/Space.
 */
import { Popover } from "@base-ui/react/popover";
import type { ReactNode } from "react";

import { GLOSSARY, type GlossaryId } from "@/lib/glossary";
import { cn } from "@/lib/utils";

export function Term({
  id,
  children,
  className,
}: {
  id: GlossaryId;
  children?: ReactNode;
  className?: string;
}) {
  const entry = GLOSSARY[id];
  return (
    <Popover.Root>
      <Popover.Trigger
        openOnHover
        delay={120}
        aria-label={`${entry.label} 뜻 보기`}
        className={cn(
          "cursor-help rounded-sm underline decoration-muted-foreground/50 decoration-dotted underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-ring",
          className,
        )}
      >
        {children ?? entry.label}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="top" sideOffset={8} collisionPadding={12} className="z-50">
          <Popover.Popup className="max-w-72 rounded-xl border bg-popover p-3 text-left text-sm font-normal text-popover-foreground shadow-lg outline-none transition-opacity data-[ending-style]:opacity-0 data-[starting-style]:opacity-0">
            <p className="font-semibold">{entry.label}</p>
            <p className="mt-1 leading-relaxed text-muted-foreground">{entry.plain}</p>
            {entry.tip ? (
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{entry.tip}</p>
            ) : null}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
