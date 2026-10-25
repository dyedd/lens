import type { ComponentType } from "react";

export type OverviewStatView = {
  icon: ComponentType<{ className?: string }>;
  title: string;
  value: string;
};

type Props = {
  views: OverviewStatView[];
};

/** 渲染概览中的总量指标卡片。 */
export function OverviewStatCard({ views }: Props) {
  const view = views[0];
  if (!view) return null;
  const Icon = view.icon;

  return (
    <div className="flex w-full min-w-0 flex-col rounded-md bg-muted/35 px-3 py-3.5 md:px-4 md:py-4">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-4 text-foreground/55" />
        <span>{view.title}</span>
      </div>
      <p className="mt-2 truncate text-base font-semibold tabular-nums text-foreground md:text-lg">
        {view.value}
      </p>
    </div>
  );
}
