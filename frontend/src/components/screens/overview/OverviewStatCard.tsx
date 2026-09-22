import type { ComponentType } from "react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/classNames";

export type OverviewStatView = {
  icon: ComponentType<{ className?: string }>;
  title: string;
  value: string;
};

const ROTATE_MS = 5_000;

type Props = {
  views: OverviewStatView[];
  cycleLabel: string;
};

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return reduced;
}

/** Render one overview metric family; auto-rotates, click also cycles. */
export function OverviewStatCard({ views, cycleLabel }: Props) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const canCycle = views.length > 1;
  const autoRotate = canCycle && !paused && !reducedMotion;
  const viewCount = views.length;

  useEffect(() => {
    if (!autoRotate || viewCount < 2) return undefined;
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % viewCount);
    }, ROTATE_MS);
    return () => window.clearInterval(timer);
  }, [autoRotate, viewCount]);

  const view = views[index % Math.max(viewCount, 1)];
  if (!view) return null;
  const Icon = view.icon;

  return (
    <button
      type="button"
      disabled={!canCycle}
      aria-label={canCycle ? `${view.title}，${cycleLabel}` : view.title}
      onClick={() => setIndex((current) => (current + 1) % viewCount)}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className={cn(
        "flex w-full min-w-0 flex-col rounded-md bg-muted/35 px-3 py-3.5 text-left md:px-4 md:py-4",
        canCycle &&
          "cursor-pointer transition-colors hover:bg-muted/50 focus-visible:ring-[1px] focus-visible:ring-primary/40 focus-visible:outline-none",
      )}
    >
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-4 text-foreground/55" />
        <span>{view.title}</span>
      </div>
      <p className="mt-2 truncate text-base font-semibold tabular-nums text-foreground md:text-lg">
        {view.value}
      </p>
      {canCycle ? (
        <span
          className="mt-auto flex items-center gap-1 pt-3"
          aria-hidden="true"
        >
          {views.map((item, itemIndex) => (
            <span
              key={item.title}
              className={cn(
                "size-1 rounded-full",
                itemIndex === index % viewCount
                  ? "bg-foreground/45"
                  : "bg-foreground/15",
              )}
            />
          ))}
        </span>
      ) : null}
    </button>
  );
}
