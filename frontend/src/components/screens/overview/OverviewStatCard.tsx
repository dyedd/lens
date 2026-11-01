import type { ComponentType } from "react";
import { Link } from "react-router";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
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
  description?: string;
};

type Props = {
  view: OverviewStatView;
};

/** 渲染概览中的汇总指标。 */
export function OverviewStatCard({ view }: Props) {
  const Icon = view.icon;

  return (
    <div
      className={cn(
        "flex h-full w-full min-w-0 flex-col rounded-md bg-muted/35 px-3 py-3.5 md:px-4 md:py-4",
        view.detailsColumns === 2 && "col-span-2 sm:col-span-1",
      )}
    >
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-4 text-foreground/55" />
        {view.description ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="cursor-help underline decoration-dotted underline-offset-4"
              >
                {view.title}
              </button>
            </TooltipTrigger>
            <TooltipContent>{view.description}</TooltipContent>
          </Tooltip>
        ) : (
          <span>{view.title}</span>
        )}
      </div>
      <p className="mt-2 truncate text-base font-semibold tabular-nums text-foreground md:text-lg">
        {view.value}
      </p>
      {view.details?.length ? (
        <dl
          className={cn(
            "mt-3 grid gap-x-3 gap-y-1 text-xs",
            view.detailsColumns === 2 && "grid-cols-2",
          )}
        >
          {view.details.map((detail) => (
            <div
              key={detail.label}
              className="flex min-w-0 items-baseline justify-between gap-1"
            >
              <dt
                className="truncate text-muted-foreground"
                title={detail.label}
              >
                {detail.label}
              </dt>
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
