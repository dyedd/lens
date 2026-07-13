"use client";

import { LayoutGrid } from "lucide-react";
import { ModelAvatar } from "@/lib/ModelIcons";
import { cn } from "@/lib/utils";

/** Renders a selectable model-family filter chip. */
export function SeriesChip({
  selected,
  label,
  sampleModel,
  onClick,
  isAll = false,
}: {
  selected: boolean;
  label: string;
  sampleModel: string;
  onClick: () => void;
  isAll?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "group flex min-w-[76px] snap-start items-center justify-center rounded-[22px] border bg-card px-4 py-4 text-center transition-all",
        selected
          ? "border-primary bg-primary/[0.05] shadow-[0_0_0_1px_rgba(37,99,235,0.08)]"
          : "border-border/70 hover:border-primary/25 hover:bg-muted/20",
      )}
    >
      <span
        className={cn(
          "flex size-11 items-center justify-center rounded-2xl border bg-background",
          selected ? "border-primary/20 bg-primary/[0.06]" : "border-border/60",
        )}
      >
        {isAll ? (
          <LayoutGrid
            size={20}
            className={selected ? "text-primary" : "text-muted-foreground"}
          />
        ) : (
          <ModelAvatar name={sampleModel} size={28} />
        )}
      </span>
    </button>
  );
}
