import type { ComponentType } from "react";
import { Link } from "react-router";
import { cn } from "@/lib/classNames";

export type OverviewStatDetail = {
  label: string;
  value: string;
  href?: string;
};

export type OverviewStatView = {
  icon: ComponentType<{ className?: string }>;
  title: string;
  value: string;
  details?: OverviewStatDetail[];
  detailsColumns?: 2;
};

type Props = {
  view: OverviewStatView;
};

/** 渲染概览中的汇总指标。 */
export function OverviewStatCard({ view }: Props) {
  const Icon = view.icon;

  return (
    <div className="flex h-full w-full min-w-0 flex-col justify-between rounded-xl border border-border/55 bg-card px-4 py-4 transition-colors hover:border-border/90 hover:bg-card/80 sm:px-5">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="truncate font-medium">{view.title}</span>
        <Icon className="size-3.5 shrink-0 text-foreground/45" />
      </div>
      <p className="mt-2 truncate font-mono text-2xl font-medium tracking-tight tabular-nums text-card-foreground">
        {view.value}
      </p>
      {view.details?.length ? (
        <dl
          className={cn(
            "mt-3 grid grid-cols-2 gap-x-4 gap-y-1 pt-1 text-xs",
            view.detailsColumns === 2 && "grid-cols-2",
          )}
        >
          {view.details.map((detail) => (
            <div
              key={detail.label}
              className="flex min-w-0 items-baseline justify-between gap-1.5"
            >
              <dt className="truncate text-muted-foreground">{detail.label}</dt>
              <dd className="shrink-0 font-medium tabular-nums text-foreground">
                {detail.href ? (
                  <Link
                    className="underline decoration-dotted underline-offset-4 hover:text-primary"
                    to={detail.href}
                    aria-label={`${detail.label} ${detail.value}`}
                  >
                    {detail.value}
                  </Link>
                ) : (
                  detail.value
                )}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
