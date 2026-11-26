import type { ReactNode } from "react";
import { cn } from "@/lib/classNames";

export type FilterPillOption<T extends string> = {
  value: T;
  label: ReactNode;
  count?: number;
};

type FilterPillGroupProps<T extends string> = {
  value: T;
  options: FilterPillOption<T>[];
  onValueChange: (value: T) => void;
  ariaLabel?: string;
  className?: string;
};

/** Quiet inline filter tabs without nested pill boxes. */
export function FilterPillGroup<T extends string>({
  value,
  options,
  onValueChange,
  ariaLabel,
  className,
}: FilterPillGroupProps<T>) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn("inline-flex flex-wrap items-center gap-1", className)}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onValueChange(option.value)}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium whitespace-nowrap transition-colors",
              active
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
            )}
          >
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
